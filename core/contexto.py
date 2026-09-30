"""Estado compartilhado da aplicação: configuração local, repositório e tabelas."""
from __future__ import annotations

import getpass
from pathlib import Path

from core.config import caminho_indice, carregar_config, salvar_config
from core.repositorio import Repositorio
from core.siglas import TabelaSiglas


class Contexto:
    def __init__(self, config: dict | None = None):
        self.config = config if config is not None else carregar_config()
        self.repo = Repositorio(Path(self.config["pasta_raiz"]), caminho_indice())
        self._siglas: TabelaSiglas | None = None

    def abrir_repositorio(self) -> None:
        self.repo = Repositorio(Path(self.config["pasta_raiz"]), caminho_indice())
        self._siglas = None

    def salvar_config(self) -> None:
        salvar_config(self.config)

    @property
    def analista(self) -> str:
        nome = (self.config.get("analista_nome") or "").strip()
        if nome:
            return nome
        try:
            return getpass.getuser()
        except Exception:
            return "Analista"

    @property
    def assinatura(self) -> str:
        return self.config.get("assinatura") or self.analista

    def siglas(self, recarregar: bool = False) -> TabelaSiglas:
        if self._siglas is None or recarregar:
            self._siglas = TabelaSiglas(self.repo.caminho_siglas)
            if not self._siglas.linhas:
                from core.config import dir_recursos

                padrao = TabelaSiglas(dir_recursos() / "siglas_cidades_padrao.csv")
                self._siglas.linhas = padrao.linhas
        return self._siglas

    def empresas(self, somente_ativas: bool = False) -> list[dict]:
        lista = self.repo.carregar_empresas()
        return [e for e in lista if e.get("ativa", True)] if somente_ativas else lista

    def empresas_do_grupo(self, grupo: int) -> list[dict]:
        return [e for e in self.empresas(True) if e.get("grupo") == grupo]

    def login(self, empresa_id: str) -> str:
        return (self.config.get("logins") or {}).get(empresa_id, "")
