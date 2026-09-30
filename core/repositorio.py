"""Persistência: um JSON por pedido no Drive (fonte da verdade) e índice SQLite local.

O SQLite NUNCA fica no Drive: ele mora em %LOCALAPPDATA% e é reconstruído a
partir dos JSONs ao abrir o programa e no botão "Atualizar".
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from core.config import agora, dir_recursos
from core.formatos import data_iso, normalizar, somente_digitos
from core.modelo import cidades, data_viagem, id_pedido, nomes_passageiros, registrar_historico

log = logging.getLogger(__name__)

PASTA_SISTEMA = "_Sistema Passagens"
RE_DUPLICADO = re.compile(r"\(\d+\)(\.[^.]+)?$|conflict|conflito", re.I)


class DriveIndisponivel(Exception):
    pass


class ConflitoEdicao(Exception):
    pass


class PedidoJaExiste(Exception):
    pass


def gravar_json_atomico(caminho: Path, dados) -> None:
    """Escreve em arquivo.json.tmp e renomeia com os.replace (com novas tentativas no Drive)."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    for tentativa in range(5):
        try:
            os.replace(tmp, caminho)
            return
        except PermissionError:
            if tentativa == 4:
                raise
            time.sleep(0.3 * (tentativa + 1))


def ler_json(caminho: Path):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


class Repositorio:
    def __init__(self, raiz: Path | str, caminho_indice: Path | str):
        self.raiz = Path(raiz)
        self.caminho_indice = Path(caminho_indice)
        self._fts: bool | None = None

    # ------------------------------------------------------------ caminhos
    @property
    def pasta_sistema(self) -> Path:
        return self.raiz / PASTA_SISTEMA

    @property
    def pasta_pedidos(self) -> Path:
        return self.pasta_sistema / "pedidos"

    @property
    def caminho_empresas(self) -> Path:
        return self.pasta_sistema / "empresas.json"

    @property
    def caminho_siglas(self) -> Path:
        return self.pasta_sistema / "siglas_cidades.csv"

    @property
    def pasta_modelos(self) -> Path:
        return self.pasta_sistema / "modelos_email"

    def caminho_json(self, numero: str, ano: str) -> Path:
        return self.pasta_pedidos / f"{id_pedido(numero, ano)}.json"

    def pasta_do_pedido(self, pedido: dict) -> Path:
        pasta = pedido.get("pasta") or {}
        return self.raiz / pasta.get("projeto", "") / pasta.get("pedido", "")

    # ------------------------------------------------------------ Drive
    def drive_disponivel(self) -> bool:
        try:
            return self.raiz.is_dir()
        except OSError:
            return False

    def exigir_drive(self) -> None:
        if not self.drive_disponivel():
            raise DriveIndisponivel(
                f"A pasta raiz não está acessível:\n{self.raiz}\n\n"
                "Verifique se o Google Drive para computador está aberto e sincronizado (unidade G:)."
            )

    def garantir_estrutura(self) -> None:
        """Cria _Sistema Passagens e os arquivos padrão que ainda não existirem."""
        self.exigir_drive()
        self.pasta_pedidos.mkdir(parents=True, exist_ok=True)
        self.pasta_modelos.mkdir(parents=True, exist_ok=True)
        rec = dir_recursos()
        if not self.caminho_empresas.exists():
            shutil.copyfile(rec / "empresas_padrao.json", self.caminho_empresas)
        if not self.caminho_siglas.exists():
            shutil.copyfile(rec / "siglas_cidades_padrao.csv", self.caminho_siglas)
        for modelo in (rec / "modelos_email").glob("*.txt"):
            alvo = self.pasta_modelos / modelo.name
            if not alvo.exists():
                shutil.copyfile(modelo, alvo)

    def arquivos_duplicados(self) -> list[Path]:
        """Arquivos criados pelo Drive em conflito, ex.: '33276-2026 (1).json'."""
        if not self.drive_disponivel():
            return []
        achados = []
        for pasta in (self.pasta_sistema, self.pasta_pedidos, self.pasta_modelos):
            if pasta.is_dir():
                achados += [p for p in pasta.iterdir() if p.is_file() and RE_DUPLICADO.search(p.stem + p.suffix)]
        return sorted(achados)

    # ------------------------------------------------------------ pedidos
    def listar_pedidos(self) -> list[tuple[Path, dict]]:
        """Relê todos os JSONs da pasta de pedidos (ignora .tmp e arquivos ilegíveis)."""
        self.exigir_drive()
        saida = []
        if not self.pasta_pedidos.is_dir():
            return saida
        for caminho in sorted(self.pasta_pedidos.glob("*.json")):
            try:
                saida.append((caminho, ler_json(caminho)))
            except Exception:
                log.exception("JSON ilegível: %s", caminho.name)
        return saida

    def existe(self, numero: str, ano: str) -> bool:
        return self.caminho_json(numero, ano).exists()

    def carregar(self, numero: str, ano: str) -> dict:
        self.exigir_drive()
        return ler_json(self.caminho_json(numero, ano))

    def carregar_por_id(self, pid: str) -> dict:
        numero, _, ano = pid.partition("-")
        return self.carregar(numero, ano)

    def criar(self, pedido: dict, quem: str) -> dict:
        self.exigir_drive()
        caminho = self.caminho_json(pedido["numero"], pedido["ano"])
        if caminho.exists():
            raise PedidoJaExiste(f"O pedido {pedido['numero']}/{pedido['ano']} já está cadastrado.")
        registrar_historico(pedido, quem, "pedido_criado", pedido.get("pasta", {}).get("pedido", ""))
        gravar_json_atomico(caminho, pedido)
        self.indexar(pedido, caminho)
        log.info("Pedido criado: %s", id_pedido(pedido["numero"], pedido["ano"]))
        return pedido

    def salvar(self, pedido: dict, quem: str, acao: str, detalhe: str = "", esperado: str | None = None) -> dict:
        """Grava com controle de conflito: `esperado` é o atualizado_em lido ao abrir o pedido."""
        self.exigir_drive()
        caminho = self.caminho_json(pedido["numero"], pedido["ano"])
        if esperado is not None and caminho.exists():
            no_disco = ler_json(caminho).get("atualizado_em")
            if no_disco != esperado:
                raise ConflitoEdicao(
                    "Outro analista alterou este pedido. Ele será recarregado; refaça a sua alteração."
                )
        # microssegundos: duas gravações no mesmo segundo precisam gerar marcas diferentes
        pedido["atualizado_em"] = agora().isoformat(timespec="microseconds")
        pedido["atualizado_por"] = quem
        registrar_historico(pedido, quem, acao, detalhe)
        gravar_json_atomico(caminho, pedido)
        self.indexar(pedido, caminho)
        log.info("Pedido salvo: %s (%s)", id_pedido(pedido["numero"], pedido["ano"]), acao)
        return pedido

    # ------------------------------------------------------------ empresas
    def carregar_empresas(self) -> list[dict]:
        caminho = self.caminho_empresas if self.caminho_empresas.exists() else dir_recursos() / "empresas_padrao.json"
        return ler_json(caminho).get("empresas", [])

    def salvar_empresas(self, empresas: list[dict]) -> None:
        self.exigir_drive()
        gravar_json_atomico(self.caminho_empresas, {"versao": 1, "empresas": empresas})

    # ------------------------------------------------------------ modelos de e-mail
    def ler_modelo(self, nome: str) -> str:
        for pasta in (self.pasta_modelos, dir_recursos() / "modelos_email"):
            arq = pasta / nome
            if arq.exists():
                return arq.read_text(encoding="utf-8").rstrip("\n")
        return ""

    def salvar_modelo(self, nome: str, texto: str) -> None:
        self.exigir_drive()
        self.pasta_modelos.mkdir(parents=True, exist_ok=True)
        alvo = self.pasta_modelos / nome
        tmp = alvo.with_name(alvo.name + ".tmp")
        tmp.write_text(texto.rstrip("\n") + "\n", encoding="utf-8")
        os.replace(tmp, alvo)

    # ============================================================ índice SQLite
    @contextmanager
    def _conexao(self):
        """Conexão com commit/rollback e fechamento garantido (libera o arquivo no Windows)."""
        self.caminho_indice.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.caminho_indice)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def _tem_fts(self, con: sqlite3.Connection) -> bool:
        if self._fts is None:
            try:
                con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _teste_fts USING fts5(x)")
                con.execute("DROP TABLE _teste_fts")
                self._fts = True
            except sqlite3.OperationalError:
                self._fts = False
        return self._fts

    def _criar_tabelas(self, con: sqlite3.Connection) -> None:
        con.executescript(
            """
            DROP TABLE IF EXISTS pedido; DROP TABLE IF EXISTS passageiro;
            DROP TABLE IF EXISTS trecho; DROP TABLE IF EXISTS cotacao; DROP TABLE IF EXISTS busca;
            CREATE TABLE pedido(
                json_path TEXT PRIMARY KEY, id TEXT, numero TEXT, ano TEXT, projeto TEXT, projeto_nome TEXT,
                tipo TEXT, passageiros TEXT, resumo TEXT, data_viagem TEXT, grupo INTEGER, status TEXT,
                prazo TEXT, analista TEXT, criado_em TEXT, atualizado_em TEXT, coordenador_email TEXT,
                texto_busca TEXT);
            CREATE TABLE passageiro(json_path TEXT, nome TEXT, cpf TEXT);
            CREATE TABLE trecho(json_path TEXT, ordem INTEGER, sentido TEXT, origem TEXT, destino TEXT,
                origem_codigo TEXT, destino_codigo TEXT, data TEXT);
            CREATE TABLE cotacao(json_path TEXT, empresa_id TEXT, empresa TEXT, valor REAL);
            CREATE INDEX ix_pedido_id ON pedido(id);
            CREATE INDEX ix_pedido_projeto ON pedido(projeto);
            """
        )
        if self._tem_fts(con):
            con.execute(
                "CREATE VIRTUAL TABLE busca USING fts5(json_path UNINDEXED, texto, "
                "tokenize='unicode61 remove_diacritics 2')"
            )

    def _garantir_indice(self, con: sqlite3.Connection) -> None:
        existe = con.execute("SELECT 1 FROM sqlite_master WHERE name='pedido'").fetchone()
        if not existe:
            self._criar_tabelas(con)

    def reconstruir_indice(self) -> int:
        """Apaga e recria o índice a partir dos JSONs. Retorna a quantidade de pedidos."""
        pedidos = self.listar_pedidos()
        with self._conexao() as con:
            self._criar_tabelas(con)
            for caminho, p in pedidos:
                self._inserir(con, p, caminho)
        log.info("Índice reconstruído com %d pedidos", len(pedidos))
        return len(pedidos)

    def indexar(self, pedido: dict, caminho: Path) -> None:
        with self._conexao() as con:
            self._garantir_indice(con)
            self._inserir(con, pedido, caminho)

    def _inserir(self, con: sqlite3.Connection, p: dict, caminho: Path) -> None:
        jp = str(caminho)
        for tabela in ("pedido", "passageiro", "trecho", "cotacao"):
            con.execute(f"DELETE FROM {tabela} WHERE json_path=?", (jp,))
        if self._tem_fts(con):
            con.execute("DELETE FROM busca WHERE json_path=?", (jp,))
        projeto = p.get("projeto") or {}
        dv = data_viagem(p)
        texto = self._texto_busca(p)
        con.execute(
            "INSERT INTO pedido VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                jp, id_pedido(p.get("numero", ""), p.get("ano", "")), p.get("numero", ""), p.get("ano", ""),
                projeto.get("numero", ""), projeto.get("nome", ""), p.get("tipo", ""), nomes_passageiros(p),
                p.get("resumo", ""), dv.isoformat() if dv else "", (p.get("grupo") or {}).get("numero"),
                p.get("status", ""), data_iso((p.get("aprovacao") or {}).get("prazo_data")),
                p.get("criado_por", ""), p.get("criado_em", ""), p.get("atualizado_em", ""),
                projeto.get("coordenador_email", ""), normalizar(texto),
            ),
        )
        con.executemany(
            "INSERT INTO passageiro VALUES (?,?,?)",
            [(jp, x.get("nome", ""), x.get("cpf", "")) for x in p.get("passageiros", [])],
        )
        con.executemany(
            "INSERT INTO trecho VALUES (?,?,?,?,?,?,?,?)",
            [
                (jp, t.get("ordem"), t.get("sentido"), t.get("origem"), t.get("destino"),
                 t.get("origem_codigo"), t.get("destino_codigo"), t.get("data"))
                for t in p.get("trechos", [])
            ],
        )
        con.executemany(
            "INSERT INTO cotacao VALUES (?,?,?,?)",
            [(jp, c.get("empresa_id"), c.get("empresa"), c.get("valor")) for c in p.get("cotacoes", [])],
        )
        if self._tem_fts(con):
            con.execute("INSERT INTO busca VALUES (?,?)", (jp, texto))

    @staticmethod
    def _texto_busca(p: dict) -> str:
        projeto = p.get("projeto") or {}
        partes = [
            p.get("numero", ""), f"{p.get('numero', '')}{p.get('ano', '')}",
            f"PJ{projeto.get('numero', '')}", projeto.get("numero", ""), projeto.get("nome", ""),
            p.get("resumo", ""), p.get("finalidade", ""), (p.get("solicitante") or {}).get("nome", ""),
        ]
        for x in p.get("passageiros", []):
            partes += [x.get("nome", ""), somente_digitos(x.get("cpf", ""))]
        partes += cidades(p)
        return " ".join(s for s in partes if s)

    # ------------------------------------------------------------ consultas
    def buscar(self, termo: str = "", status: str | None = None, tipo: str | None = None) -> list[dict]:
        with self._conexao() as con:
            self._garantir_indice(con)
            where, args = [], []
            termo = (termo or "").strip()
            if termo:
                digitos = somente_digitos(termo)
                if len(digitos) == 11 and re.fullmatch(r"[\d.\-\s]+", termo):
                    tokens = [digitos]  # CPF formatado
                else:
                    tokens = [t for t in re.split(r"[^\w]+", normalizar(termo)) if t]
                if tokens and self._tem_fts(con):
                    consulta = " AND ".join(f'"{t}"*' for t in tokens)
                    where.append("p.json_path IN (SELECT json_path FROM busca WHERE busca MATCH ?)")
                    args.append(consulta)
                else:
                    for t in tokens:
                        where.append("p.texto_busca LIKE ?")
                        args.append(f"%{t}%")
            if status:
                where.append("p.status = ?")
                args.append(status)
            if tipo:
                where.append("p.tipo = ?")
                args.append(tipo)
            sql = "SELECT p.* FROM pedido p" + (" WHERE " + " AND ".join(where) if where else "")
            return [dict(r) for r in con.execute(sql, args).fetchall()]

    def ultimo_email_coordenador(self, projeto_numero: str) -> str:
        with self._conexao() as con:
            self._garantir_indice(con)
            r = con.execute(
                "SELECT coordenador_email FROM pedido WHERE projeto=? AND coordenador_email<>'' "
                "ORDER BY atualizado_em DESC LIMIT 1",
                (str(projeto_numero),),
            ).fetchone()
            return r[0] if r else ""
