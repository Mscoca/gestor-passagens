import json

import pytest

from core.modelo import novo_pedido
from core.repositorio import ConflitoEdicao, DriveIndisponivel, PedidoJaExiste, Repositorio


@pytest.fixture
def repo(tmp_path):
    raiz = tmp_path / "#CRED 01.2026"
    raiz.mkdir()
    r = Repositorio(raiz, tmp_path / "local" / "indice.db")
    r.garantir_estrutura()
    return r


def pedido_exemplo(numero="33276", nome="FULANO DE TAL SILVA", cpf="12345678909"):
    p = novo_pedido(
        {
            "numero": numero, "ano": "2026", "tipo": "aerea", "resumo": "CGR - FLN",
            "projeto": {"numero": "371", "nome": "UFMS Digital", "coordenador_email": "coord@ufms.br"},
            "passageiros": [{"nome": nome, "cpf": cpf}],
            "trechos": [{"ordem": 1, "sentido": "ida", "origem": "Campo Grande", "destino": "Florianópolis",
                         "origem_codigo": "CGR", "destino_codigo": "FLN", "data": "16/11/2026"}],
        },
        "Analista",
    )
    p["pasta"] = {"projeto": "PJ 371", "pedido": f"Pedido {numero}-2026 CGR - FLN"}
    p["grupo"] = {"numero": 1}
    return p


def test_estrutura_criada(repo):
    assert repo.pasta_pedidos.is_dir()
    assert repo.caminho_empresas.exists() and repo.caminho_siglas.exists()
    assert (repo.pasta_modelos / "aprovacao.txt").exists()
    assert len(repo.carregar_empresas()) == 10


def test_grava_atomico_e_busca_pelo_passageiro(repo):
    repo.criar(pedido_exemplo(), "Analista")
    caminho = repo.caminho_json("33276", "2026")
    assert caminho.exists()
    assert not caminho.with_name(caminho.name + ".tmp").exists()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert dados["historico"][0]["acao"] == "pedido_criado"

    assert [r["numero"] for r in repo.buscar("fulano")] == ["33276"]
    assert [r["numero"] for r in repo.buscar("Florianopolis")] == ["33276"]
    assert [r["numero"] for r in repo.buscar("123.456.789-09")] == ["33276"]
    assert [r["numero"] for r in repo.buscar("33276")] == ["33276"]
    assert repo.buscar("beltrano") == []


def test_reconstruir_indice(repo):
    repo.criar(pedido_exemplo("1"), "A")
    repo.criar(pedido_exemplo("2", "BELTRANO", "52998224725"), "A")
    repo.caminho_indice.unlink()
    assert repo.reconstruir_indice() == 2
    assert [r["numero"] for r in repo.buscar("beltrano")] == ["2"]
    assert repo.ultimo_email_coordenador("371") == "coord@ufms.br"


def test_nao_duplica_pedido(repo):
    repo.criar(pedido_exemplo(), "A")
    with pytest.raises(PedidoJaExiste):
        repo.criar(pedido_exemplo(), "A")


def test_conflito_de_edicao(repo):
    p = repo.criar(pedido_exemplo(), "A")
    carregado_a = repo.carregar("33276", "2026")
    carregado_b = repo.carregar("33276", "2026")
    esperado = carregado_a["atualizado_em"]
    carregado_b["atualizado_em"] = "2000-01-01T00:00:00-04:00"  # simula gravação anterior de outro analista
    repo.salvar(carregado_b, "B", "editado", esperado=esperado)
    with pytest.raises(ConflitoEdicao):
        repo.salvar(carregado_a, "A", "editado", esperado=esperado)


def test_duplicados_do_drive(repo):
    (repo.pasta_pedidos / "33276-2026 (1).json").write_text("{}", encoding="utf-8")
    assert [p.name for p in repo.arquivos_duplicados()] == ["33276-2026 (1).json"]


def test_drive_indisponivel(tmp_path):
    r = Repositorio(tmp_path / "G_inexistente", tmp_path / "i.db")
    with pytest.raises(DriveIndisponivel):
        r.listar_pedidos()
