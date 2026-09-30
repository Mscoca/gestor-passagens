"""Regras das cotações: mínimo de 3 valores, menor valor e empate."""
from __future__ import annotations

from core.config import agora_iso
from core.modelo import registrar_historico

MINIMO_COTACOES = 3


def com_valor(cotacoes: list[dict]) -> list[dict]:
    return [c for c in cotacoes if isinstance(c.get("valor"), (int, float)) and c["valor"] > 0]


def pode_definir_vencedora(cotacoes: list[dict]) -> bool:
    return len(com_valor(cotacoes)) >= MINIMO_COTACOES


def menores(cotacoes: list[dict]) -> list[dict]:
    validas = com_valor(cotacoes)
    if not validas:
        return []
    minimo = min(round(c["valor"], 2) for c in validas)
    return [c for c in validas if round(c["valor"], 2) == minimo]


def ha_empate(cotacoes: list[dict]) -> bool:
    return len(menores(cotacoes)) > 1


def sugerida(cotacoes: list[dict]) -> dict | None:
    m = menores(cotacoes)
    return m[0] if len(m) == 1 else None


def validar_desempate(desempate: dict | None, empatadas: list[dict]) -> None:
    """Cada empresa empatada precisa de uma ligação registrada (data/hora, pessoa, resultado)."""
    ligacoes = {l.get("empresa_id"): l for l in (desempate or {}).get("ligacoes", [])}
    faltando = []
    for c in empatadas:
        l = ligacoes.get(c["empresa_id"])
        if not l or not all((l.get(k) or "").strip() for k in ("data_hora", "pessoa", "resultado")):
            faltando.append(c.get("empresa", c["empresa_id"]))
    if faltando:
        raise ValueError("Registre a ligação (data e hora, pessoa e resultado) para: " + ", ".join(faltando))


def definir_vencedora(
    pedido: dict, empresa_id: str, justificativa: str = "", desempate: dict | None = None, quem: str = ""
) -> None:
    cotacoes = pedido.get("cotacoes", [])
    if not pode_definir_vencedora(cotacoes):
        raise ValueError(f"Registre pelo menos {MINIMO_COTACOES} valores antes de definir a vencedora.")
    escolhida = next((c for c in com_valor(cotacoes) if c["empresa_id"] == empresa_id), None)
    if escolhida is None:
        raise ValueError("A empresa escolhida não tem valor registrado.")
    justificativa = (justificativa or "").strip()
    mais_baratas = menores(cotacoes)
    if len(mais_baratas) > 1:
        validar_desempate(desempate, mais_baratas)
        if empresa_id not in {c["empresa_id"] for c in mais_baratas}:
            raise ValueError("Em caso de empate, a vencedora deve ser uma das empresas empatadas.")
        if not justificativa:
            raise ValueError("Informe a justificativa da escolha entre as empresas empatadas.")
        pedido["desempate"] = {**(desempate or {}), "registrado_em": agora_iso()}
    elif empresa_id != mais_baratas[0]["empresa_id"] and not justificativa:
        raise ValueError("A empresa escolhida não tem o menor valor. Informe a justificativa.")
    pedido["vencedora"] = {"empresa_id": empresa_id, "empresa": escolhida.get("empresa", ""),
                           "valor": escolhida["valor"], "justificativa": justificativa}
    registrar_historico(pedido, quem, "vencedora_definida", f"{escolhida.get('empresa', empresa_id)}")
