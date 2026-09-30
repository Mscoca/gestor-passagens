"""Nomes de pastas e arquivos, sanitização, criação de pastas e cópia sem sobrescrever."""
from __future__ import annotations

import os
import re
import shutil
from collections import Counter
from pathlib import Path

from core.formatos import formatar_moeda, normalizar, primeiro_nome
from core.siglas import TabelaSiglas

PROIBIDOS = re.compile(r'[\\/:*?"<>|]')
MODELO_PADRAO = "Pedido {numero}-{ano} {resumo}"


def sanitizar(nome: str) -> str:
    s = PROIBIDOS.sub(" ", nome or "")
    s = re.sub(r"[\x00-\x1f]", "", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(". ")
    return s


def caminho_longo(p: Path | str) -> str:
    """Prefixo \\\\?\\ para caminhos longos no Windows (acima de ~240 caracteres)."""
    s = str(Path(p).absolute())
    if os.name == "nt" and len(s) > 240 and not s.startswith("\\\\?\\"):
        return "\\\\?\\UNC\\" + s[2:] if s.startswith("\\\\") else "\\\\?\\" + s
    return s


# ------------------------------------------------------------------ pasta do projeto
def nome_pasta_projeto(numero: str) -> str:
    return f"PJ {str(numero).strip()}"


def encontrar_pasta_projeto(raiz: Path, numero: str) -> Path | None:
    """Procura 'PJ {numero}' seguido de fim, espaço ou hífen (ex.: 'PJ 185 - Algo')."""
    raiz = Path(raiz)
    if not raiz.is_dir():
        return None
    padrao = re.compile(rf"^PJ\s*{re.escape(str(numero).strip())}(?:$|[\s-])", re.I)
    candidatas = sorted(p for p in raiz.iterdir() if p.is_dir() and padrao.match(p.name))
    return candidatas[0] if candidatas else None


def pasta_projeto(raiz: Path, numero: str) -> Path:
    """Pasta do projeto existente ou o caminho da que será criada."""
    return encontrar_pasta_projeto(raiz, numero) or Path(raiz) / nome_pasta_projeto(numero)


# ------------------------------------------------------------------ resumo e pasta do pedido
def codigo_cidade(cidade: str, siglas: TabelaSiglas | None, confirmados: dict | None = None) -> str:
    if confirmados and normalizar(cidade) in confirmados:
        return confirmados[normalizar(cidade)]
    if siglas is not None:
        return siglas.codigo_ou_sugestao(cidade)[0]
    return TabelaSiglas.sugerir(cidade)


def cidades_em_ordem(trechos: list[dict]) -> list[tuple[str, str]]:
    """Cidades distintas (nome, código) na ordem em que aparecem nos trechos."""
    vistas: dict[str, tuple[str, str]] = {}
    for t in sorted(trechos, key=lambda t: t.get("ordem") or 0):
        for lado in ("origem", "destino"):
            nome = (t.get(lado) or "").strip()
            if nome and normalizar(nome) not in vistas:
                vistas[normalizar(nome)] = (nome, t.get(f"{lado}_codigo") or "")
    return list(vistas.values())


def resumo_pasta(
    tipo: str,
    trechos: list[dict],
    hospedagem: dict | None = None,
    siglas: TabelaSiglas | None = None,
    confirmados: dict | None = None,
) -> str:
    def cod(nome: str, codigo: str = "") -> str:
        return codigo or codigo_cidade(nome, siglas, confirmados)

    if tipo == "hospedagem":
        cidade = (hospedagem or {}).get("cidade", "")
        return f"Hospedagem - {cod(cidade)}" if cidade else "Hospedagem"
    cidades = cidades_em_ordem(trechos)
    if not cidades:
        return ""
    if tipo == "terrestre" and len(cidades) > 3:
        destinos = Counter(
            normalizar(t["destino"]) for t in trechos if t.get("destino") and t.get("sentido", "ida") == "ida"
        ) or Counter(normalizar(t["destino"]) for t in trechos if t.get("destino"))
        principal = destinos.most_common(1)[0][0]
        nome, codigo = next((c for c in cidades if normalizar(c[0]) == principal), cidades[-1])
        return f"Terrestre - {cod(nome, codigo)}"
    return " - ".join(cod(n, c) for n, c in cidades)


def nome_pasta_pedido(numero: str, ano: str, resumo: str, modelo: str = MODELO_PADRAO) -> str:
    valores = {"numero": numero, "ano": ano, "resumo": resumo or ""}
    nome = re.sub(r"\{(\w+)\}", lambda m: str(valores.get(m.group(1), m.group(0))), modelo or MODELO_PADRAO)
    return sanitizar(nome)


def criar_pastas(raiz: Path, projeto_numero: str, nome_pedido: str) -> tuple[Path, Path, bool]:
    """Cria (ou reaproveita) PJ e pasta do pedido. Retorna (pasta_projeto, pasta_pedido, pedido_ja_existia)."""
    raiz = Path(raiz)
    if not raiz.is_dir():
        raise FileNotFoundError(f"Pasta raiz não encontrada: {raiz}")
    pj = pasta_projeto(raiz, projeto_numero)
    os.makedirs(caminho_longo(pj), exist_ok=True)
    ped = pj / sanitizar(nome_pedido)
    existia = ped.exists()
    os.makedirs(caminho_longo(ped), exist_ok=True)
    return pj, ped, existia


# ------------------------------------------------------------------ arquivos
def nome_livre(pasta: Path, nome: str) -> Path:
    """Caminho em `pasta` que ainda não existe, acrescentando ' (2)', ' (3)'…"""
    nome = sanitizar(nome)
    alvo = Path(pasta) / nome
    if not os.path.exists(caminho_longo(alvo)):
        return alvo
    base, ext = os.path.splitext(nome)
    n = 2
    while True:
        alvo = Path(pasta) / f"{base} ({n}){ext}"
        if not os.path.exists(caminho_longo(alvo)):
            return alvo
        n += 1


def copiar_sem_sobrescrever(origem: Path | str, pasta_destino: Path, nome: str) -> Path:
    """Copia (não move) `origem` para `pasta_destino/nome`, sem nunca sobrescrever."""
    origem = Path(origem)
    if not origem.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {origem}")
    os.makedirs(caminho_longo(pasta_destino), exist_ok=True)
    alvo = nome_livre(pasta_destino, nome)
    shutil.copy2(caminho_longo(origem), caminho_longo(alvo))
    return alvo


def nome_arquivo_pedido(numero: str) -> str:
    return f"1. Pedido {numero}.pdf"


def nome_doc_passageiro(nome_passageiro: str, extensao: str = ".pdf") -> str:
    ext = extensao if extensao.startswith(".") else f".{extensao}"
    return f"2. Doc {primeiro_nome(nome_passageiro)}{ext.lower() or '.pdf'}"


def nome_proposta(grupo: int, empresa: str, valor: float, extensao: str = ".pdf") -> str:
    ext = extensao if extensao.startswith(".") else f".{extensao}"
    return sanitizar(f"G{grupo} - {empresa} - {formatar_moeda(valor)}") + ext.lower()


PASTA_COTACAO = "4. Cotação"

NOMES_FIXOS = {
    "pre_reserva": "4. Pré-reserva",
    "reserva": "5. Reserva",
    "reserva_ida": "5. Reserva Ida",
    "reserva_volta": "5.1 Reserva Volta",
}


def nome_fixo(tipo: str, extensao: str = ".pdf") -> str:
    ext = extensao if extensao.startswith(".") else f".{extensao}"
    return NOMES_FIXOS[tipo] + ext.lower()


def listar_arquivos(pasta: Path) -> list[Path]:
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return sorted((p for p in pasta.rglob("*") if p.is_file()), key=lambda p: str(p.relative_to(pasta)).lower())
