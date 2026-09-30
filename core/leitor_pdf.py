"""Leitura do PDF "Pedido de Compra" exportado do Conveniar.

`ler_pedido(caminho_pdf)` extrai o texto e chama `ler_texto(texto)`.
Os dados tirados da Descrição (texto livre do solicitante) são apenas
sugestões: a tela de conferência exige a confirmação do analista.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from core.formatos import (
    cpf_valido,
    espacos_simples,
    hora_hhmm,
    normalizar,
    parse_moeda,
    somente_digitos,
)

log = logging.getLogger(__name__)


class ErroLeituraPDF(Exception):
    pass


# ------------------------------------------------------------------ regex do cabeçalho
RE_NUMERO = re.compile(r"N[º°o]\s*Pedido\s*:\s*(\d+)\s*/\s*(\d{4})", re.I)
RE_DATA_PEDIDO = re.compile(r"Data do Pedido\s*:\s*(\d{2}/\d{2}/\d{4})", re.I)
RE_SOLICITANTE = re.compile(
    r"Solicitante[ \t]*:[ \t]*(.*?)[ \t]*Telefone[ \t]*:[ \t]*(.*?)[ \t]*E-?mail[ \t]*:[ \t]*(\S*)", re.I
)
RE_SOLICITANTE_NOME = re.compile(r"Solicitante\s*:\s*(.+)$", re.I | re.M)
RE_SITUACAO = re.compile(r"Situa[çc][ãa]o\s*:\s*(\S+)", re.I)
RE_PROJETO = re.compile(r"^\s*Nome\s*:\s*([\d ]+?)\s*-\s*(.+)$", re.I | re.M)
RE_COORDENADOR = re.compile(r"^\s*Coordenador\s*:\s*(.+)$", re.I | re.M)
RE_GESTOR = re.compile(
    r"^\s*Gestor do Projeto\s*:\s*(.+?)(?:\s+\d{2}/\d{2}/\d{4}.*)?$", re.I | re.M
)
RE_CONTA_CAIXA = re.compile(r"Conta Caixa\s*:\s*(\d+)", re.I)
RE_FINALIDADE = re.compile(r"^\s*Finalidade\s*:\s*(.*)$", re.I | re.M)

# ------------------------------------------------------------------ regex dos itens
RE_INICIO_ITEM = re.compile(r"^\s*(\d+)\s+Produto/Servi[çc]o\s*:", re.I)
_VALOR = r"(\d{1,3}(?:\.\d{3})*,\d{2,4})"
RE_ITEM_COMPLETO = re.compile(
    r"Produto/Servi[çc]o\s*:\s*(.+?)\s+(\d+)(?:,\d+)?\s+(\S+)\s+" + _VALOR + r"\s+" + _VALOR,
    re.I,
)
RE_ITEM_SIMPLES = re.compile(r"Produto/Servi[çc]o\s*:\s*(.+?)\s+(\d+)\s+Unidade", re.I)
PARADAS_DESCRICAO = tuple(
    normalizar(p)
    for p in (
        "Local de Entrega:",
        "Observação de Entrega:",
        "Fornecedores Sugeridos:",
        "Finalidade:",
        "Meta:",
        "Etapa:",
    )
)

# ------------------------------------------------------------------ regex da descrição
RE_CPF = re.compile(r"CPF\s*[:\-]?\s*(\d[\d.\-]{9,13}\d)", re.I)
RE_EMAIL_DESC = re.compile(r"E-?MAIL\s*[:\-]?\s*(\S+@\S+)", re.I)
RE_FONE_DESC = re.compile(r"(?:CONTATO|TELEFONE|CELULAR|FONE)\s*[:\-]?\s*([()\d\s-]{8,})", re.I)
RE_NOME_PRODUTO = re.compile(
    r"(?:Passagem\s+[\wÀ-ÿ]+|Hospedagem)\s*-\s*(.+?)(?=\.|\s*,?\s*CPF\b|$)", re.I
)
RE_SEQUENCIA_NOME = re.compile(
    r"[A-ZÀ-Ý][A-Za-zÀ-ÿ']+(?:\s+(?:d[aeo]s?|e|[A-ZÀ-Ý][A-Za-zÀ-ÿ']+))+"
)
RE_TRECHO = re.compile(r"Trecho\s*:?\s*(.+?)(?:\s+(?=Ida\b)|\.\s|\.$|$)", re.I)
_DATA_HORA = r"(\d{2}/\d{2}/\d{4})(?:\s*,?\s*(?:às|as|-)?\s*(\d{1,2}[:h]\d{2}))?"
RE_IDA = re.compile(r"Ida\s*(?:dia|em)?\s*:?\s*" + _DATA_HORA, re.I)
RE_VOLTA = re.compile(r"Volta\s*(?:dia|em)?\s*:?\s*" + _DATA_HORA, re.I)
RE_BAGAGEM = re.compile(r"([^.]*\bbagage[mn]s?\b[^.]*)", re.I)
RE_UF_FINAL = re.compile(r"\s*[/-]\s*[A-Z]{2}\s*$")
RE_RODAPE = re.compile(r"(Conveniar\s*-\s*Gest[ãa]o de Conv[êe]nios|P[áa]gina\s*:\s*\d+\s*de\s*\d+)", re.I)


# ================================================================== API
def ler_pedido(caminho_pdf: str | Path) -> dict:
    """Lê o PDF e devolve o dicionário do pedido (ver `ler_texto`)."""
    textos = extrair_textos(caminho_pdf)
    if not any(t.strip() for t in textos):
        raise ErroLeituraPDF(
            "Não foi possível ler texto do PDF. Confirme se é o Pedido de Compra exportado do Conveniar."
        )
    resultados = [ler_texto(t) for t in textos if t.strip()]
    melhor = max(resultados, key=_pontuacao)
    if not melhor.get("numero"):
        raise ErroLeituraPDF("O PDF não parece ser um Pedido de Compra do Conveniar (Nº do pedido não encontrado).")
    return melhor


def extrair_textos(caminho_pdf: str | Path) -> list[str]:
    """Extrai o texto com PyMuPDF (ordem natural e ordenada). pdfplumber só como alternativa."""
    caminho = str(caminho_pdf)
    textos: list[str] = []
    try:
        import pymupdf

        with pymupdf.open(caminho) as doc:
            textos.append(_juntar_paginas([p.get_text("text") for p in doc]))
            textos.append(_juntar_paginas([p.get_text("text", sort=True) for p in doc]))
    except Exception:
        log.exception("Falha ao ler PDF com PyMuPDF")
    if not any(t.strip() for t in textos):
        try:
            import pdfplumber

            with pdfplumber.open(caminho) as pdf:
                textos.append(_juntar_paginas([(p.extract_text() or "") for p in pdf.pages]))
        except Exception:
            log.exception("Falha ao ler PDF com pdfplumber")
    return textos


def ler_texto(texto: str) -> dict:
    """Interpreta o texto de um Pedido de Compra do Conveniar."""
    texto = _limpar_texto(texto)
    linhas = texto.splitlines()

    numero = ano = ""
    m = RE_NUMERO.search(texto)
    if m:
        numero, ano = m.group(1), m.group(2)

    sol_nome = sol_tel = sol_email = ""
    m = RE_SOLICITANTE.search(texto)
    if m:
        sol_nome, sol_tel, sol_email = (espacos_simples(g) for g in m.groups())
    else:
        sol_nome = _buscar(RE_SOLICITANTE_NOME, texto)
        m2 = re.search(r"E-?mail\s*:\s*(\S+@\S+)", texto, re.I)
        sol_email = m2.group(1) if m2 else ""

    proj_num = proj_nome = ""
    inicio_projeto = texto.find("\nProjeto")
    m = RE_PROJETO.search(texto, max(inicio_projeto, 0))
    if m:
        proj_num = re.sub(r"\s+", "", m.group(1))
        proj_nome = espacos_simples(m.group(2))

    itens = _ler_itens(linhas)
    tipo = tipo_do_produto(itens[0]["produto"]) if itens else "outro"

    passageiros: list[dict] = []
    trechos: list[dict] = []
    hospedagem = None
    cpf_invalidos: list[str] = []
    for item in itens:
        sug = sugestoes_da_descricao(item["descricao"], tipo_do_produto(item["produto"]))
        pessoas_item = max(len(sug["passageiros"]), 1)
        for p in sug["passageiros"]:
            if not _passageiro_repetido(passageiros, p):
                passageiros.append(p)
            if p["cpf"] and not cpf_valido(p["cpf"]) and p["cpf"] not in cpf_invalidos:
                cpf_invalidos.append(p["cpf"])
        for t in sug["trechos"]:
            t["pessoas"] = pessoas_item
            _mesclar_trecho(trechos, t)
        if sug["hospedagem"] and hospedagem is None:
            hospedagem = sug["hospedagem"]
    for i, t in enumerate(trechos, start=1):
        t["ordem"] = i
    if hospedagem is not None:
        hospedagem["hospedes"] = max(len(passageiros), 1)

    return {
        "numero": numero,
        "ano": ano,
        "tipo": tipo,
        "data_pedido": _buscar(RE_DATA_PEDIDO, texto),
        "situacao": _buscar(RE_SITUACAO, texto),
        "solicitante": {"nome": sol_nome, "email": sol_email, "telefone": sol_tel},
        "projeto": {
            "numero": proj_num,
            "nome": proj_nome,
            "coordenador": _buscar(RE_COORDENADOR, texto),
            "gestor": _buscar(RE_GESTOR, texto),
            "conta_caixa": _buscar(RE_CONTA_CAIXA, texto),
        },
        "finalidade": _buscar(RE_FINALIDADE, texto),
        "passageiros": passageiros,
        "trechos": trechos,
        "hospedagem": hospedagem,
        "itens": itens,
        "cpf_invalidos": cpf_invalidos,
    }


def tipo_do_produto(produto: str) -> str:
    p = normalizar(produto)
    if "aerea" in p:
        return "aerea"
    if "terrestre" in p or "rodoviari" in p:
        return "terrestre"
    if "hosped" in p or "hotel" in p:
        return "hospedagem"
    return "outro"


# ================================================================== descrição
def sugestoes_da_descricao(descricao: str, tipo: str = "aerea") -> dict:
    """Extrai (melhor esforço) passageiros, trechos e hospedagem da Descrição."""
    desc = espacos_simples(descricao)
    return {
        "passageiros": _passageiros(desc),
        "trechos": _trechos(desc) if tipo != "hospedagem" else [],
        "hospedagem": _hospedagem(desc) if tipo == "hospedagem" else None,
    }


def _passageiros(desc: str) -> list[dict]:
    cpfs = list(RE_CPF.finditer(desc))
    passageiros = []
    if not cpfs:
        m = RE_NOME_PRODUTO.search(desc)
        if m:
            passageiros.append(_montar_passageiro(m.group(1), "", desc))
        return passageiros
    inicio_segmento = 0
    for i, m_cpf in enumerate(cpfs):
        segmento = desc[inicio_segmento : m_cpf.start()]
        nome = ""
        if i == 0:
            m_nome = RE_NOME_PRODUTO.search(segmento)
            if m_nome:
                nome = m_nome.group(1)
        if not nome:
            limpo = RE_FONE_DESC.sub(" ", RE_EMAIL_DESC.sub(" ", segmento))
            sequencias = RE_SEQUENCIA_NOME.findall(limpo)
            nome = sequencias[-1] if sequencias else ""
        fim_zona = cpfs[i + 1].start() if i + 1 < len(cpfs) else len(desc)
        zona = desc[m_cpf.end() : fim_zona]
        passageiros.append(_montar_passageiro(nome, m_cpf.group(1), zona))
        inicio_segmento = m_cpf.end()
    return passageiros


def _montar_passageiro(nome: str, cpf: str, zona: str) -> dict:
    email = ""
    m = RE_EMAIL_DESC.search(zona)
    if m:
        email = m.group(1).rstrip(".,;)")
    telefone = ""
    m = RE_FONE_DESC.search(zona)
    if m:
        telefone = espacos_simples(m.group(1)).strip(" -")
    nome = espacos_simples(nome).strip(" .,-;:")
    return {"nome": nome, "cpf": somente_digitos(cpf), "email": email, "telefone": telefone}


def _limpar_cidade(parte: str) -> str:
    cidade = RE_UF_FINAL.sub("", parte.strip(" .,;"))
    return espacos_simples(cidade)


def _trechos(desc: str) -> list[dict]:
    trechos: list[dict] = []
    matches = list(RE_TRECHO.finditer(desc))
    bagagem = _bagagem(desc)
    for i, m in enumerate(matches):
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(desc)
        zona = desc[m.end() : fim]
        cidades = [_limpar_cidade(c) for c in re.split(r"\s+[xX]\s+", m.group(1))]
        cidades = [c for c in cidades if c]
        if len(cidades) < 2:
            continue
        ida = RE_IDA.search(zona)
        volta = RE_VOLTA.search(zona)
        ida_data, ida_hora = (ida.group(1), hora_hhmm(ida.group(2))) if ida else ("", "")
        volta_data, volta_hora = (volta.group(1), hora_hhmm(volta.group(2))) if volta else ("", "")
        pernas = list(zip(cidades, cidades[1:]))
        fecha_ciclo = len(cidades) > 2 and normalizar(cidades[0]) == normalizar(cidades[-1])
        for j, (origem, destino) in enumerate(pernas):
            ultima = j == len(pernas) - 1
            if j == 0:
                sentido, data, hora = "ida", ida_data, ida_hora
            elif ultima and (fecha_ciclo or volta):
                sentido, data, hora = "volta", volta_data, volta_hora
            else:
                sentido, data, hora = "ida", "", ""
            trechos.append(
                {
                    "ordem": 0,
                    "sentido": sentido,
                    "origem": origem,
                    "destino": destino,
                    "data": data,
                    "hora": hora,
                    "pessoas": 1,
                    "bagagem": bagagem,
                }
            )
    return trechos


def _bagagem(desc: str) -> str:
    if "sem bagagem" in normalizar(desc):
        return "Sem bagagem"
    m = RE_BAGAGEM.search(desc)
    if not m:
        return ""
    frase = espacos_simples(m.group(1))
    frase = re.sub(r"^(?:com|e)\s+", "", frase, flags=re.I)
    return frase


def _hospedagem(desc: str) -> dict:
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", desc)
    checkin = re.search(r"(?:check-?in|entrada)\D{0,20}(\d{2}/\d{2}/\d{4})", desc, re.I)
    checkout = re.search(r"(?:check-?out|sa[íi]da)\D{0,20}(\d{2}/\d{2}/\d{4})", desc, re.I)
    cidade = ""
    m = re.search(r"(?:Cidade|Local)\s*[:\-]\s*([A-ZÀ-Ý][\wÀ-ÿ ]+?)(?:\s*[/-]\s*[A-Z]{2}\b|[.,;]|$)", desc)
    if not m:
        m = re.search(r"\bem\s+([A-ZÀ-Ý][\wÀ-ÿ]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ý][\wÀ-ÿ]+)*)\s*/\s*[A-Z]{2}\b", desc)
    if m:
        cidade = espacos_simples(m.group(1))
    quarto = ""
    m = re.search(r"\bquarto\s*:?\s*(\w+)|\b(single|duplo|triplo|casal|individual)\b", desc, re.I)
    if m:
        quarto = m.group(1) or m.group(2)
    return {
        "cidade": cidade,
        "hotel": "",
        "checkin": checkin.group(1) if checkin else (datas[0] if datas else ""),
        "checkout": checkout.group(1) if checkout else (datas[1] if len(datas) > 1 else ""),
        "hospedes": 1,
        "quarto": quarto,
    }


# ================================================================== auxiliares
def _juntar_paginas(paginas: list[str]) -> str:
    return "\n".join(paginas)


def _limpar_texto(texto: str) -> str:
    """Remove rodapés e cabeçalhos repetidos de páginas seguintes."""
    linhas = [l.rstrip() for l in texto.replace("\r", "").splitlines()]
    cabecalho = {l.strip() for l in linhas[:3] if l.strip()}
    vistos: set[str] = set()
    saida = []
    for l in linhas:
        s = l.strip()
        if not s or RE_RODAPE.search(s):
            continue
        if s in cabecalho:
            if s in vistos:
                continue
            vistos.add(s)
        saida.append(l)
    return "\n".join(saida)


def _buscar(regex: re.Pattern, texto: str) -> str:
    m = regex.search(texto)
    return espacos_simples(m.group(1)) if m else ""


def _eh_parada(linha: str) -> bool:
    n = normalizar(linha)
    return n.startswith(PARADAS_DESCRICAO) or bool(RE_INICIO_ITEM.match(linha))


def _ler_itens(linhas: list[str]) -> list[dict]:
    inicios = [i for i, l in enumerate(linhas) if RE_INICIO_ITEM.match(l)]
    itens = []
    for k, ini in enumerate(inicios):
        fim = inicios[k + 1] if k + 1 < len(inicios) else len(linhas)
        bloco = linhas[ini:fim]
        idx_desc = next(
            (i for i, l in enumerate(bloco) if normalizar(l).startswith("descricao:")), None
        )
        cabecalho = " ".join(bloco[: idx_desc if idx_desc is not None else 1])
        descricao = ""
        if idx_desc is not None:
            partes = []
            for l in bloco[idx_desc:]:
                if partes and _eh_parada(l):
                    break
                partes.append(l)
            descricao = espacos_simples(" ".join(partes))
            descricao = re.sub(r"^Descri[çc][ãa]o\s*:\s*", "", descricao, flags=re.I)
        produto, quantidade, valor_unit, valor_total = "", 0, None, None
        m = RE_ITEM_COMPLETO.search(cabecalho)
        if m:
            produto = m.group(1)
            quantidade = int(m.group(2))
            valor_unit = parse_moeda(m.group(4))
            valor_total = parse_moeda(m.group(5))
        else:
            m = RE_ITEM_SIMPLES.search(cabecalho)
            if m:
                produto, quantidade = m.group(1), int(m.group(2))
            else:
                produto = re.sub(r"^\s*\d+\s+Produto/Servi[çc]o\s*:\s*", "", cabecalho, flags=re.I)
        itens.append(
            {
                "produto": espacos_simples(produto),
                "quantidade": quantidade,
                "valor_unit": valor_unit,
                "valor_total": valor_total,
                "descricao": descricao,
            }
        )
    return itens


def _passageiro_repetido(lista: list[dict], p: dict) -> bool:
    for q in lista:
        if p["cpf"] and p["cpf"] == q["cpf"]:
            return True
        if not p["cpf"] and normalizar(p["nome"]) == normalizar(q["nome"]):
            return True
    return False


def _mesclar_trecho(trechos: list[dict], novo: dict) -> None:
    chave = lambda t: (normalizar(t["origem"]), normalizar(t["destino"]), t["data"], t["hora"])
    for t in trechos:
        if chave(t) == chave(novo):
            t["pessoas"] += novo["pessoas"]
            return
    trechos.append(novo)


def _pontuacao(r: dict) -> int:
    pontos = sum(1 for k in ("numero", "ano", "data_pedido", "situacao", "finalidade") if r.get(k))
    pontos += sum(1 for v in r["solicitante"].values() if v)
    pontos += sum(1 for v in r["projeto"].values() if v)
    pontos += 2 * len(r["itens"]) + len(r["passageiros"]) + len(r["trechos"])
    return pontos
