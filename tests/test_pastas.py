from pathlib import Path

import pytest

from core import pastas
from core.config import dir_recursos
from core.siglas import TabelaSiglas


@pytest.fixture
def siglas(tmp_path):
    arq = tmp_path / "siglas.csv"
    arq.write_text((dir_recursos() / "siglas_cidades_padrao.csv").read_text(encoding="utf-8"), encoding="utf-8")
    return TabelaSiglas(arq)


def trecho(o, d, sentido="ida", ordem=1):
    return {"ordem": ordem, "sentido": sentido, "origem": o, "destino": d}


def test_siglas_ignoram_acento_caixa_e_uf(siglas):
    assert siglas.codigo("florianopolis") == "FLN"
    assert siglas.codigo("CAMPO GRANDE/MS") == "CGR"
    assert siglas.codigo("Três Lagoas") == "TJL"
    assert siglas.codigo("Jardim") is None
    assert siglas.codigo_ou_sugestao("Ivinhema") == ("IVI", False)


def test_salvar_sigla_nova(siglas):
    siglas.adicionar("Jardim", "MS", "jdm")
    assert TabelaSiglas(siglas.caminho).codigo("jardim") == "JDM"


def test_resumos(siglas):
    ida_volta = [trecho("Campo Grande", "Florianópolis"), trecho("Florianópolis", "Campo Grande", "volta", 2)]
    assert pastas.resumo_pasta("aerea", ida_volta, siglas=siglas) == "CGR - FLN"
    assert pastas.resumo_pasta("aerea", [trecho("Campo Grande", "Brasília")], siglas=siglas) == "CGR - BSB"
    tres = [trecho("Campo Grande", "Florianópolis"), trecho("Florianópolis", "Porto Alegre", ordem=2)]
    assert pastas.resumo_pasta("aerea", tres, siglas=siglas) == "CGR - FLN - POA"
    assert pastas.resumo_pasta("terrestre", [trecho("Campo Grande", "Três Lagoas")], siglas=siglas) == "CGR - TJL"
    muitos = [
        trecho("Jardim", "Três Lagoas"), trecho("Dourados", "Três Lagoas", ordem=2),
        trecho("Bonito", "Três Lagoas", ordem=3), trecho("Três Lagoas", "Jardim", "volta", 4),
    ]
    assert pastas.resumo_pasta("terrestre", muitos, siglas=siglas) == "Terrestre - TJL"
    assert pastas.resumo_pasta("hospedagem", [], {"cidade": "Campo Grande"}, siglas=siglas) == "Hospedagem - CGR"


def test_resumo_usa_confirmados(siglas):
    t = [trecho("Jardim", "Campo Grande")]
    assert pastas.resumo_pasta("terrestre", t, siglas=siglas, confirmados={"jardim": "JDM"}) == "JDM - CGR"


def test_sanitizar_e_nome_pasta():
    assert pastas.sanitizar('a/b:c*d?"e<f>g|h\\i') == "a b c d e f g h i"
    assert pastas.nome_pasta_pedido("33276", "2026", "CGR - FLN") == "Pedido 33276-2026 CGR - FLN"
    assert pastas.nome_pasta_pedido("1", "2026", "X/Y", "{numero}_{ano} {resumo}") == "1_2026 X Y"


def test_cria_pastas_e_reaproveita_pj(tmp_path):
    raiz = tmp_path / "DEP. COMPRAS E SERVIÇOS" / "#CRED 01.2026"
    raiz.mkdir(parents=True)
    pj, ped, existia = pastas.criar_pastas(raiz, "371", "Pedido 33276-2026 CGR - FLN")
    assert ped == raiz / "PJ 371" / "Pedido 33276-2026 CGR - FLN" and ped.is_dir() and not existia

    (raiz / "PJ 185 - Projeto Antigo").mkdir()
    (raiz / "PJ 1850").mkdir()
    pj, ped, _ = pastas.criar_pastas(raiz, "185", "Pedido 1-2026 CGR - BSB")
    assert pj.name == "PJ 185 - Projeto Antigo"
    assert not (raiz / "PJ 185").exists()

    _, _, existia = pastas.criar_pastas(raiz, "371", "Pedido 33276-2026 CGR - FLN")
    assert existia


def test_nunca_sobrescreve(tmp_path):
    origem = tmp_path / "Downloads" / "pedido.pdf"
    origem.parent.mkdir()
    origem.write_bytes(b"%PDF-1")
    destino = tmp_path / "pedido"
    a = pastas.copiar_sem_sobrescrever(origem, destino, "1. Pedido 33276.pdf")
    b = pastas.copiar_sem_sobrescrever(origem, destino, "1. Pedido 33276.pdf")
    c = pastas.copiar_sem_sobrescrever(origem, destino, "1. Pedido 33276.pdf")
    assert [a.name, b.name, c.name] == ["1. Pedido 33276.pdf", "1. Pedido 33276 (2).pdf", "1. Pedido 33276 (3).pdf"]
    assert origem.exists(), "o original não pode ser movido"


def test_nomes_de_arquivos():
    assert pastas.nome_doc_passageiro("FULANO DE TAL SILVA", ".PDF") == "2. Doc Fulano.pdf"
    assert pastas.nome_doc_passageiro("fulano", ".jpg") == "2. Doc Fulano.jpg"
    assert pastas.nome_proposta(2, "Decolando", 1539.02) == "G2 - Decolando - R$ 1.539,02.pdf"
    assert pastas.nome_fixo("reserva_volta") == "5.1 Reserva Volta.pdf"
    assert pastas.nome_fixo("pre_reserva") == "4. Pré-reserva.pdf"
