from datetime import datetime, timedelta

import pytest

from core import cotacoes as cot
from core.config import FUSO
from core.rodizio import atribuir_grupo, conflitos_recentes, grupo_da_vez, trocar_grupo

BASE = datetime(2026, 9, 29, 8, 0, tzinfo=FUSO)


def criar_sequencia(n, ultimo_config=3):
    pedidos = []
    for i in range(n):
        g = grupo_da_vez(pedidos, ultimo_config)
        p = {"numero": str(i + 1), "ano": "2026", "status": "em_cotacao", "cotacoes": [],
             "criado_em": (BASE + timedelta(minutes=30 * i)).isoformat()}
        atribuir_grupo(p, g, g)
        pedidos.append(p)
    return pedidos


def test_sequencia_de_cinco():
    assert [p["grupo"]["numero"] for p in criar_sequencia(5)] == [1, 2, 3, 1, 2]


def test_sem_pedidos_usa_config():
    assert grupo_da_vez([], 1) == 2
    assert grupo_da_vez([], 3) == 1


def test_ordem_por_criado_em_e_nao_pelo_numero():
    pedidos = criar_sequencia(2)
    pedidos[0]["criado_em"] = (BASE + timedelta(days=1)).isoformat()  # o pedido 1 é o mais recente
    assert grupo_da_vez(pedidos) == 2  # seguinte ao G1


def test_troca_manual_exige_justificativa():
    p = {}
    with pytest.raises(ValueError):
        atribuir_grupo(p, 3, 1, "")
    atribuir_grupo(p, 3, 1, "Empresa do G1 indisponível", "Ana")
    assert p["grupo"]["manual"] is True
    assert p["historico"][-1]["acao"] == "grupo_manual"
    with pytest.raises(ValueError):
        trocar_grupo(p, 2, "  ", "Ana")
    trocar_grupo(p, 2, "Pedido do coordenador", "Ana")
    assert p["grupo"]["numero"] == 2 and p["historico"][-1]["acao"] == "grupo_trocado"


def test_cancelado_antes_da_cotacao_nao_conta():
    pedidos = criar_sequencia(2)  # G1, G2
    pedidos[1]["status"] = "cancelado"
    assert grupo_da_vez(pedidos) == 2  # G2 é devolvido ao rodízio
    pedidos[1]["cotacoes"] = [{"empresa_id": "x", "valor": 10.0}]
    assert grupo_da_vez(pedidos) == 3  # cancelado depois da cotação conta


def test_conflito_recente():
    pedidos = criar_sequencia(1)  # G1 às 08:00
    assert len(conflitos_recentes(pedidos, 1, BASE + timedelta(minutes=5))) == 1
    assert conflitos_recentes(pedidos, 1, BASE + timedelta(minutes=15)) == []
    assert conflitos_recentes(pedidos, 2, BASE + timedelta(minutes=5)) == []


# ------------------------------------------------------------------ cotações
def c(eid, valor):
    return {"empresa_id": eid, "empresa": eid.title(), "valor": valor}


def test_minimo_tres_valores_e_menor():
    p = {"cotacoes": [c("a", 900.0), c("b", 800.0)]}
    with pytest.raises(ValueError):
        cot.definir_vencedora(p, "b")
    p["cotacoes"].append(c("d", 1000.0))
    assert cot.sugerida(p["cotacoes"])["empresa_id"] == "b"
    with pytest.raises(ValueError):
        cot.definir_vencedora(p, "a")  # não é a menor e sem justificativa
    cot.definir_vencedora(p, "b")
    assert p["vencedora"]["empresa_id"] == "b"


def test_empate_exige_ligacoes_e_justificativa():
    p = {"cotacoes": [c("a", 800.0), c("b", 800.0), c("d", 1000.0)]}
    assert cot.ha_empate(p["cotacoes"])
    with pytest.raises(ValueError):
        cot.definir_vencedora(p, "a", "menor tarifa na ligação")
    lig = {"ligacoes": [
        {"empresa_id": "a", "data_hora": "29/09/2026 10:00", "pessoa": "Poliana", "resultado": "Manteve"},
    ]}
    with pytest.raises(ValueError):
        cot.definir_vencedora(p, "a", "x", lig)
    lig["ligacoes"].append({"empresa_id": "b", "data_hora": "29/09/2026 10:05", "pessoa": "Sabrina",
                            "resultado": "Reduziu R$ 10"})
    with pytest.raises(ValueError):
        cot.definir_vencedora(p, "a", "", lig)
    with pytest.raises(ValueError):
        cot.definir_vencedora(p, "d", "x", lig)
    cot.definir_vencedora(p, "b", "Reduziu o valor na ligação", lig)
    assert p["vencedora"]["empresa_id"] == "b" and p["desempate"]["ligacoes"]
