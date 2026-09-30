"""Estrutura do pedido (JSON = fonte da verdade), status e textos derivados."""
from __future__ import annotations

import copy
from datetime import date

from core.config import agora_iso
from core.formatos import formatar_cpf, parse_data

VERSAO_SCHEMA = 1

TIPOS = {
    "aerea": "Passagem Aérea",
    "terrestre": "Passagem Terrestre",
    "hospedagem": "Hospedagem",
    "outro": "Outro",
}

STATUS = {
    "em_cotacao": "Em cotação",
    "aguardando_aprovacao": "Aguardando aprovação",
    "aprovado": "Aprovado",
    "emitido": "Emitido",
    "cancelado": "Cancelado",
}

# status atual -> [(ação, rótulo do botão)]
TRANSICOES = {
    "em_cotacao": [("aguardando_aprovacao", "Aguardando aprovação"), ("cancelado", "Cancelar")],
    "aguardando_aprovacao": [
        ("aprovado", "Aprovado"),
        ("reprovado", "Reprovado"),
        ("cancelado", "Cancelar"),
    ],
    "aprovado": [("emitido", "Emitido"), ("cancelado", "Cancelar")],
    "emitido": [("cancelado", "Cancelar")],
    "cancelado": [("em_cotacao", "Reabrir (Em cotação)")],
}


def id_pedido(numero: str, ano: str) -> str:
    return f"{numero}-{ano}"


def registrar_historico(pedido: dict, quem: str, acao: str, detalhe: str = "") -> None:
    pedido.setdefault("historico", []).append(
        {"quando": agora_iso(), "quem": quem, "acao": acao, "detalhe": detalhe}
    )


def novo_pedido(dados: dict, quem: str) -> dict:
    """Monta o pedido completo a partir dos dados conferidos na tela."""
    agora = agora_iso()
    p = {
        "versao_schema": VERSAO_SCHEMA,
        "numero": dados["numero"],
        "ano": dados["ano"],
        "tipo": dados.get("tipo", "outro"),
        "status": "em_cotacao",
        "criado_em": agora,
        "criado_por": quem,
        "atualizado_em": agora,
        "atualizado_por": quem,
        "data_pedido": dados.get("data_pedido", ""),
        "situacao_conveniar": dados.get("situacao_conveniar", ""),
        "finalidade": dados.get("finalidade", ""),
        "resumo": dados.get("resumo", ""),
        "projeto": {
            "numero": "", "nome": "", "coordenador": "", "coordenador_email": "", "gestor": "", "conta_caixa": "",
            **dados.get("projeto", {}),
        },
        "solicitante": {"nome": "", "email": "", "telefone": "", **dados.get("solicitante", {})},
        "passageiros": copy.deepcopy(dados.get("passageiros", [])),
        "trechos": copy.deepcopy(dados.get("trechos", [])),
        "hospedagem": copy.deepcopy(dados.get("hospedagem")),
        "itens_conveniar": copy.deepcopy(dados.get("itens_conveniar", [])),
        "pasta": {"projeto": "", "pedido": ""},
        "grupo": None,
        "cotacoes": [],
        "desempate": None,
        "vencedora": None,
        "aprovacao": None,
        "arquivos": [],
        "historico": [],
    }
    return p


def nomes_passageiros(pedido: dict) -> str:
    nomes = [p.get("nome", "").strip() for p in pedido.get("passageiros", []) if p.get("nome")]
    return ", ".join(nomes)


def data_viagem(pedido: dict) -> date | None:
    datas = [parse_data(t.get("data")) for t in pedido.get("trechos", [])]
    hosp = pedido.get("hospedagem") or {}
    datas.append(parse_data(hosp.get("checkin")))
    datas = [d for d in datas if d]
    return min(datas) if datas else None


def cidades(pedido: dict) -> list[str]:
    saida = []
    for t in pedido.get("trechos", []):
        for k in ("origem", "destino", "origem_codigo", "destino_codigo"):
            if t.get(k):
                saida.append(t[k])
    hosp = pedido.get("hospedagem") or {}
    if hosp.get("cidade"):
        saida.append(hosp["cidade"])
    return saida


def _cidade_com_codigo(nome: str, codigo: str) -> str:
    return f"{nome} ({codigo})" if codigo else nome


def descritivo(pedido: dict) -> str:
    """Texto com o pedido inteiro, para colar em portais e mensagens."""
    linhas = [
        f"Pedido {pedido['numero']}/{pedido['ano']} – PJ {pedido['projeto'].get('numero', '')} – "
        f"{TIPOS.get(pedido.get('tipo'), 'Outro')}"
    ]
    for p in pedido.get("passageiros", []):
        partes = [f"Passageiro: {p.get('nome', '')}"]
        if p.get("cpf"):
            partes.append(f"CPF {formatar_cpf(p['cpf'])}")
        partes += [x for x in (p.get("email"), p.get("telefone")) if x]
        linhas.append(" – ".join(partes))
    for t in sorted(pedido.get("trechos", []), key=lambda t: t.get("ordem") or 0):
        rotulo = {"ida": "Ida", "volta": "Volta"}.get(t.get("sentido"), "Trecho")
        quando = " ".join(x for x in (t.get("data", ""), t.get("hora_saida", "")) if x)
        linha = (
            f"{rotulo}: {quando} – {_cidade_com_codigo(t.get('origem', ''), t.get('origem_codigo', ''))} → "
            f"{_cidade_com_codigo(t.get('destino', ''), t.get('destino_codigo', ''))}"
        )
        if t.get("hora_chegada"):
            linha += f" (chegada {t['hora_chegada']})"
        if t.get("companhia"):
            linha += f" – {t['companhia']}"
        if (t.get("pessoas") or 1) > 1:
            linha += f" – {t['pessoas']} pessoas"
        linhas.append(linha)
    bagagens = []
    for t in pedido.get("trechos", []):
        b = (t.get("bagagem") or "").strip()
        if b and b not in bagagens:
            bagagens.append(b)
    if bagagens:
        linhas.append("Bagagem: " + "; ".join(bagagens))
    h = pedido.get("hospedagem")
    if h:
        partes = [f"Hospedagem: {h.get('cidade', '')}"]
        if h.get("hotel"):
            partes.append(h["hotel"])
        partes.append(f"Check-in {h.get('checkin', '')}")
        partes.append(f"Check-out {h.get('checkout', '')}")
        n = h.get("hospedes") or 1
        partes.append(f"{n} hóspede{'s' if n > 1 else ''}")
        if h.get("quarto"):
            partes.append(f"Quarto {h['quarto']}")
        linhas.append(" – ".join(partes))
    return "\n".join(linhas)


def aplicar_status(pedido: dict, acao: str, quem: str, detalhe: str = "") -> str:
    """Aplica a transição de status. Retorna o novo status."""
    atual = pedido.get("status", "em_cotacao")
    permitidas = [a for a, _ in TRANSICOES.get(atual, [])]
    if acao not in permitidas:
        raise ValueError(f"Não é possível passar de '{STATUS.get(atual, atual)}' para '{acao}'.")
    agora = agora_iso()
    if acao in ("aprovado", "reprovado"):
        ap = pedido.get("aprovacao") or {}
        ap["resultado"] = acao
        ap["respondido_em"] = agora
        pedido["aprovacao"] = ap
    novo = "em_cotacao" if acao == "reprovado" else acao
    pedido["status"] = novo
    registrar_historico(pedido, quem, f"status_{acao}", detalhe)
    return novo
