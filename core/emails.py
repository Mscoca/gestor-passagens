"""Geração de assunto, destinatários e corpo dos e-mails (o sistema não envia e-mails)."""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote

from core.config import agora
from core.formatos import dia_mes, hora_com_h, normalizar, parse_data
from core.modelo import nomes_passageiros

LIMITE_URL_GMAIL = 7000

TIPO_EXTENSO = {"aerea": "Passagens Aéreas", "terrestre": "Passagem Terrestre", "hospedagem": "Hospedagem"}
TIPO_MINUSCULO = {"aerea": "passagens aéreas", "terrestre": "passagem terrestre", "hospedagem": "hospedagem"}

CAMPOS_DISPONIVEIS = {
    "numero": "Nº do pedido (33276)",
    "ano": "Ano do pedido (2026)",
    "projeto": "Nº do projeto (371)",
    "projeto_nome": "Nome do projeto",
    "tipo_extenso": "Passagens Aéreas / Passagem Terrestre / Hospedagem",
    "tipo_minusculo": "passagens aéreas / passagem terrestre / hospedagem",
    "finalidade": "Finalidade do pedido",
    "resumo": "Resumo da pasta (CGR - FLN)",
    "finalidade_ou_resumo": "Finalidade; se vazia, o resumo",
    "saudacao": "bom dia / boa tarde (pela hora)",
    "assinatura": "Sua assinatura (Configurações)",
    "nomes_passageiros": "Nomes dos passageiros/hóspedes",
    "qtd_passageiros": "Quantidade de passageiros",
    "solicitante": "Nome do solicitante",
    "coordenador": "Nome do coordenador",
    "bloco_especificacoes": "Especificações (trechos ou hospedagem) — cotação",
    "empresa": "Nome da empresa — cotação",
    "qtd_empresas": "Nº de empresas ativas — aprovação",
    "prazo_data_dd/mm": "Prazo de aprovação (dd/mm) — aprovação",
    "prazo_data": "Prazo de aprovação (dd/mm/aaaa) — aprovação",
    "prazo_hora": "Hora do prazo (17:00) — aprovação",
}


def saudacao(momento: datetime | None = None) -> str:
    return "bom dia" if (momento or agora()).hour < 12 else "boa tarde"


def renderizar(modelo: str, campos: dict) -> str:
    """Troca {campo} pelo valor. Campos desconhecidos ficam como estão."""
    return re.sub(r"\{([^{}\n]+)\}", lambda m: str(campos.get(m.group(1), m.group(0))), modelo)


def _juntar(itens: list[str]) -> str:
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def campos_basicos(pedido: dict, assinatura: str = "", momento: datetime | None = None) -> dict:
    tipo = pedido.get("tipo", "")
    projeto = pedido.get("projeto") or {}
    return {
        "numero": pedido.get("numero", ""),
        "ano": pedido.get("ano", ""),
        "projeto": projeto.get("numero", ""),
        "projeto_nome": projeto.get("nome", ""),
        "tipo_extenso": TIPO_EXTENSO.get(tipo, "Passagens"),
        "tipo_minusculo": TIPO_MINUSCULO.get(tipo, "passagens"),
        "finalidade": pedido.get("finalidade", ""),
        "resumo": pedido.get("resumo", ""),
        "finalidade_ou_resumo": pedido.get("finalidade") or pedido.get("resumo", ""),
        "saudacao": saudacao(momento),
        "assinatura": assinatura,
        "nomes_passageiros": nomes_passageiros(pedido),
        "qtd_passageiros": str(len(pedido.get("passageiros", []))),
        "solicitante": (pedido.get("solicitante") or {}).get("nome", ""),
        "coordenador": projeto.get("coordenador", ""),
    }


def montar_assunto(pedido: dict, modelo: str) -> str:
    return renderizar(modelo.strip(), campos_basicos(pedido)).strip()


# ------------------------------------------------------------------ blocos de especificação
def _pessoas(n: int) -> str:
    return f"{n} pessoa{'s' if n != 1 else ''}"


def _agrupar(trechos: list[dict]) -> list[dict]:
    grupos: dict[tuple, dict] = {}
    for t in trechos:
        chave = tuple(
            normalizar(t.get(k)) for k in ("data", "origem", "destino", "companhia", "hora_saida", "hora_chegada")
        )
        if chave in grupos:
            grupos[chave]["pessoas"] += int(t.get("pessoas") or 1)
        else:
            grupos[chave] = {**t, "pessoas": int(t.get("pessoas") or 1)}
    return sorted(grupos.values(), key=lambda g: (g.get("hora_saida") or "99:99", normalizar(g.get("origem"))))


def _formatar_grupo(g: dict) -> str:
    linhas = [
        f"{_pessoas(g['pessoas'])} - {dia_mes(g.get('data'))}",
        f"Trecho: {g.get('origem', '')} x {g.get('destino', '')}",
    ]
    if g.get("companhia"):
        linhas.append(f"Viação: {g['companhia']}")
    saida, chegada = hora_com_h(g.get("hora_saida")), hora_com_h(g.get("hora_chegada"))
    if saida and chegada:
        linhas.append(f"Horário: {saida} às {chegada}.")
    elif saida:
        linhas.append(f"Horário: {saida}.")
    return "\n".join(linhas)


def bloco_terrestre(trechos: list[dict]) -> str:
    """IDAS e VOLTAS por data, juntando trechos idênticos (data, origem, destino, viação e horário)."""
    secoes = []
    for sentido, titulo in (("ida", "IDAS"), ("volta", "VOLTAS")):
        doo = [t for t in trechos if (t.get("sentido") == "volta") == (sentido == "volta")]
        if not doo:
            continue
        datas = sorted({t.get("data", "") for t in doo}, key=lambda d: (parse_data(d) is None, parse_data(d) or d))
        if len(datas) == 1:
            cabecalho = f"{titulo} - {datas[0] or 'data a definir'}:"
        else:
            cabecalho = f"{titulo} - {_juntar([dia_mes(d) or 'a definir' for d in datas])}:"
        partes = [cabecalho]
        for data in datas:
            if len(datas) > 1:
                partes.append(f"DIA {dia_mes(data) or 'a definir'}")
            grupos = _agrupar([t for t in doo if t.get("data", "") == data])
            identicos = [g for g in grupos if g["pessoas"] > 1]
            individuais = [g for g in grupos if g["pessoas"] == 1]
            if identicos:
                partes.append("TRECHOS IDÊNTICOS:")
                partes += [_formatar_grupo(g) for g in identicos]
            if individuais:
                partes.append("TRECHOS INDIVIDUAIS:")
                partes += [_formatar_grupo(g) for g in individuais]
        secoes.append("\n\n".join(partes))
    return "\n\n".join(secoes)


def diarias(hospedagem: dict) -> int:
    ini, fim = parse_data(hospedagem.get("checkin")), parse_data(hospedagem.get("checkout"))
    return max((fim - ini).days, 0) if ini and fim else 0


def bloco_hospedagem(h: dict) -> str:
    n = diarias(h)
    linhas = [
        f"Cidade: {h.get('cidade', '')}",
        f"Hóspedes: {h.get('hospedes') or 1}",
        f"Check-in: {h.get('checkin', '')}",
        f"Check-out: {h.get('checkout', '')} ({n} diária{'s' if n != 1 else ''})",
        f"Quarto: {h.get('quarto', '')}",
    ]
    if h.get("hotel"):
        linhas.insert(1, f"Hotel: {h['hotel']}")
    return "\n".join(linhas)


def bloco_aereo(pedido: dict) -> str:
    linhas = []
    for t in sorted(pedido.get("trechos", []), key=lambda t: t.get("ordem") or 0):
        rotulo = "Volta" if t.get("sentido") == "volta" else "Ida"
        origem = f"{t.get('origem', '')}" + (f" ({t['origem_codigo']})" if t.get("origem_codigo") else "")
        destino = f"{t.get('destino', '')}" + (f" ({t['destino_codigo']})" if t.get("destino_codigo") else "")
        hora = f", {t['hora_saida']}" if t.get("hora_saida") else ""
        linhas.append(f"{rotulo}: {t.get('data', '')}{hora} – {origem} x {destino} – {_pessoas(int(t.get('pessoas') or 1))}")
    bag = sorted({t.get("bagagem", "") for t in pedido.get("trechos", []) if t.get("bagagem")})
    if bag:
        linhas.append("Bagagem: " + "; ".join(bag))
    return "\n".join(linhas)


def bloco_especificacoes(pedido: dict) -> str:
    tipo = pedido.get("tipo")
    if tipo == "hospedagem" and pedido.get("hospedagem"):
        return bloco_hospedagem(pedido["hospedagem"])
    if tipo == "terrestre":
        return bloco_terrestre(pedido.get("trechos", []))
    return bloco_aereo(pedido)


# ------------------------------------------------------------------ corpos
def corpo_cotacao(pedido: dict, modelo: str, assinatura: str = "", empresa: str = "",
                  momento: datetime | None = None) -> str:
    campos = campos_basicos(pedido, assinatura, momento)
    campos.update({"bloco_especificacoes": bloco_especificacoes(pedido), "empresa": empresa})
    return renderizar(modelo, campos).strip()


def corpo_aprovacao(pedido: dict, modelo: str, prazo_data: str, prazo_hora: str, qtd_empresas: int,
                    assinatura: str = "", momento: datetime | None = None) -> str:
    campos = campos_basicos(pedido, assinatura, momento)
    campos.update({
        "qtd_empresas": str(qtd_empresas),
        "prazo_data_dd/mm": dia_mes(prazo_data),
        "prazo_data": prazo_data,
        "prazo_hora": prazo_hora,
    })
    corpo = renderizar(modelo, campos).strip()
    h = pedido.get("hospedagem")
    if pedido.get("tipo") == "hospedagem" and h:
        corpo = corpo.replace("dados da passagem", "dados da hospedagem").replace("Passageiro(a):", "Hóspede(s):")
        n = diarias(h)
        detalhes = "\n".join([
            f"Hotel: {h.get('hotel', '')}",
            f"Hóspedes: {h.get('hospedes') or 1}",
            f"Diárias: {n}",
            f"Check-in: {h.get('checkin', '')}",
            f"Check-out: {h.get('checkout', '')}",
            f"Quarto: {h.get('quarto', '')}",
        ])
        if "Obs:" in corpo:
            corpo = corpo.replace("Obs:", detalhes + "\n\nObs:", 1)
        else:
            corpo += "\n\n" + detalhes
    return corpo


def separar_emails(texto: str) -> list[str]:
    return [e.strip() for e in re.split(r"[;,\s]+", texto or "") if e.strip()]


def destinatarios_aprovacao(pedido: dict) -> list[str]:
    emails = [(pedido.get("solicitante") or {}).get("email", ""), (pedido.get("projeto") or {}).get("coordenador_email", "")]
    saida = []
    for e in emails:
        if e and e.lower() not in (x.lower() for x in saida):
            saida.append(e)
    return saida


# ------------------------------------------------------------------ Gmail
def url_gmail(conta: str, para: list[str] | str, cc: list[str] | str, assunto: str, corpo: str) -> tuple[str, bool]:
    """Monta a URL de composição do Gmail. Retorna (url, corpo_incluido).

    Se a URL passar de 7.000 caracteres, sai sem o corpo (o chamador copia o corpo).
    """
    def lista(x):
        return ",".join(x) if isinstance(x, (list, tuple)) else (x or "")

    def montar(com_corpo: bool) -> str:
        partes = ["view=cm", "fs=1"]
        if conta:
            partes.append("authuser=" + quote(conta, safe=""))
        partes += ["to=" + quote(lista(para), safe=""), "cc=" + quote(lista(cc), safe=""), "su=" + quote(assunto, safe="")]
        if com_corpo:
            partes.append("body=" + quote(corpo, safe=""))
        return "https://mail.google.com/mail/?" + "&".join(partes)

    url = montar(True)
    if len(url) <= LIMITE_URL_GMAIL:
        return url, True
    return montar(False), False
