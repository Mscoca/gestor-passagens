"""Rodízio de grupos: cada pedido novo troca o grupo, G1 -> G2 -> G3 -> G1.

O grupo da vez é o seguinte ao do pedido cadastrado mais recentemente
(campo `criado_em`), ignorando pedidos cancelados antes da cotação.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from core.config import agora, agora_iso, parse_iso
from core.modelo import id_pedido, registrar_historico

GRUPOS = (1, 2, 3)
JANELA_CONCORRENCIA = timedelta(minutes=10)


def proximo_grupo(grupo: int | None) -> int:
    if grupo not in GRUPOS:
        return 1
    return grupo % 3 + 1


def conta_para_rodizio(pedido: dict) -> bool:
    grupo = (pedido.get("grupo") or {}).get("numero")
    if grupo not in GRUPOS or not parse_iso(pedido.get("criado_em")):
        return False
    if pedido.get("status") == "cancelado" and not pedido.get("cotacoes"):
        return False  # cancelado antes da cotação não conta
    return True


def pedido_mais_recente(pedidos: list[dict], ignorar_id: str | None = None) -> dict | None:
    validos = [
        p for p in pedidos
        if conta_para_rodizio(p) and id_pedido(p.get("numero", ""), p.get("ano", "")) != ignorar_id
    ]
    return max(validos, key=lambda p: parse_iso(p["criado_em"]), default=None)


def grupo_da_vez(pedidos: list[dict], ultimo_grupo_config: int | None = 3, ignorar_id: str | None = None) -> int:
    recente = pedido_mais_recente(pedidos, ignorar_id)
    if recente is None:
        return proximo_grupo(ultimo_grupo_config)
    return proximo_grupo(recente["grupo"]["numero"])


def atribuir_grupo(
    pedido: dict, numero: int, sugerido: int, justificativa: str = "", quem: str = ""
) -> dict:
    """Grava o grupo no pedido (no momento de Criar pasta). Troca manual exige justificativa."""
    if numero not in GRUPOS:
        raise ValueError("Grupo inválido.")
    manual = numero != sugerido
    justificativa = (justificativa or "").strip()
    if manual and not justificativa:
        raise ValueError(f"O grupo da vez é G{sugerido}. Para usar G{numero}, escreva a justificativa.")
    pedido["grupo"] = {
        "numero": numero,
        "atribuido_em": agora_iso(),
        "manual": manual,
        "justificativa": justificativa if manual else "",
        "sugerido": sugerido,
    }
    if manual:
        registrar_historico(pedido, quem, "grupo_manual", f"G{sugerido} → G{numero}: {justificativa}")
    return pedido["grupo"]


def trocar_grupo(pedido: dict, numero: int, justificativa: str, quem: str) -> None:
    """Troca manual depois de criado. Sempre exige justificativa e fica no histórico."""
    if numero not in GRUPOS:
        raise ValueError("Grupo inválido.")
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise ValueError("A troca manual de grupo exige justificativa.")
    anterior = (pedido.get("grupo") or {}).get("numero")
    grupo = dict(pedido.get("grupo") or {})
    grupo.update({"numero": numero, "manual": True, "justificativa": justificativa})
    pedido["grupo"] = grupo
    registrar_historico(pedido, quem, "grupo_trocado", f"G{anterior} → G{numero}: {justificativa}")


def conflitos_recentes(
    pedidos: list[dict], grupo: int, momento: datetime | None = None, ignorar_id: str | None = None
) -> list[dict]:
    """Pedidos criados nos últimos 10 minutos com o mesmo grupo (Drive sincronizando)."""
    momento = momento or agora()
    saida = []
    for p in pedidos:
        if id_pedido(p.get("numero", ""), p.get("ano", "")) == ignorar_id or not conta_para_rodizio(p):
            continue
        criado = parse_iso(p.get("criado_em"))
        if p["grupo"]["numero"] == grupo and criado and abs(momento - criado) <= JANELA_CONCORRENCIA:
            saida.append(p)
    return saida
