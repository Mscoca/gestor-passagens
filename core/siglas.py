"""Tabela cidade -> código IATA (arquivo siglas_cidades.csv, editável)."""
from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

from core.formatos import normalizar


class TabelaSiglas:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self.linhas: list[dict] = []
        self.carregar()

    def carregar(self) -> None:
        self.linhas = []
        if not self.caminho.exists():
            return
        texto = self.caminho.read_text(encoding="utf-8-sig")
        for linha in csv.DictReader(io.StringIO(texto), delimiter=";"):
            cidade = (linha.get("cidade") or "").strip()
            codigo = (linha.get("codigo") or "").strip().upper()
            if cidade and codigo:
                self.linhas.append({"cidade": cidade, "uf": (linha.get("uf") or "").strip().upper(), "codigo": codigo})

    def codigo(self, cidade: str) -> str | None:
        """Código da cidade (ignora acento, caixa e '/UF'); None se não estiver na tabela."""
        chave = normalizar(re.sub(r"\s*[/-]\s*[A-Za-z]{2}\s*$", "", cidade or ""))
        if not chave:
            return None
        for l in self.linhas:
            if normalizar(l["cidade"]) == chave or normalizar(l["codigo"]) == chave:
                return l["codigo"]
        return None

    @staticmethod
    def sugerir(cidade: str) -> str:
        letras = re.sub(r"[^A-Z]", "", normalizar(cidade).upper())
        return letras[:3] or "XXX"

    def codigo_ou_sugestao(self, cidade: str) -> tuple[str, bool]:
        """(código, conhecido). Se não estiver na tabela, devolve a sugestão e False."""
        c = self.codigo(cidade)
        return (c, True) if c else (self.sugerir(cidade), False)

    def adicionar(self, cidade: str, uf: str, codigo: str) -> None:
        chave = normalizar(cidade)
        self.linhas = [l for l in self.linhas if normalizar(l["cidade"]) != chave]
        self.linhas.append({"cidade": cidade.strip(), "uf": (uf or "").strip().upper(), "codigo": codigo.strip().upper()})
        self.salvar()

    def salvar(self, linhas: list[dict] | None = None) -> None:
        if linhas is not None:
            self.linhas = [l for l in linhas if l.get("cidade") and l.get("codigo")]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["cidade", "uf", "codigo"], delimiter=";", lineterminator="\n")
        w.writeheader()
        for l in self.linhas:
            w.writerow({"cidade": l["cidade"], "uf": l.get("uf", ""), "codigo": l["codigo"].upper()})
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_name(self.caminho.name + ".tmp")
        tmp.write_text(buf.getvalue(), encoding="utf-8")
        os.replace(tmp, self.caminho)
