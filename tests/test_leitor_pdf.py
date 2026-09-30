from pathlib import Path

import pytest

from core.leitor_pdf import ler_pedido, ler_texto, sugestoes_da_descricao, tipo_do_produto

TEXTO_EXEMPLO = """Fundação de Apoio à Pesquisa, ao Ensino e à Cultura
Av. Eduardo Elias Zahran, 529 - Vila Santa Dorotheia - Campo Grande/MS, CEP: 79004-000
Pedido de Compra
Nº Pedido:33276/2026 Data do Pedido: 10/09/2026 - 08:13:00
Solicitante:Maria Exemplo Souza Telefone: E-mail:maria.exemplo@ufms.br
Autorização: João Coordenador Lima Data da Autorização: 17/09/2026 - 17:10:00
Situação:Aprovado Responsável: Ana Gestora Martins Data : 18/09/2026 - 19:36:00
Projeto
Nome: 3 71 - UFMS - Contrato n 111/2023 - UFMS Digital
Coordenador: João Coordenador Lima
Gestor do Projeto: Ana Gestora Martins 18/09/2026 - 19:36:00
Setor do Gestor: Projetos
Procedimento de Compra: Lei 8.666/93 e Decreto n° 8.241
Vigência: 31/10/2023 - 14/07/2028
Centro Custo: Conta Caixa: 36889
Item Descrição Quant Unidade Valor Unit. Valor Total Moeda
. Sugerido Sugerido
1 Produto/Serviço: Passagem Aérea 2 Unidade 769,51 1.539,02 Real
Descrição: Passagem Aérea - FULANO DE TAL SILVA. CPF -
12345678909 EMAIL - fulano.silva@ufms.br CONTATO - (67)
99999 0000 . Trecho: Campo Grande/MS x Florianópolis/SC x
Campo Grande/MS Ida dia 16/11/2026, 08:00:00. Volta dia
20/11/2026, 20:15:00. Com 1 bagagem despachada até 23kg.
Local de Entrega: Av. Sen. Filinto Müller, Nº 1555 - Bloco 6 Setor 2 - Complexo EAD // AGEAD UFMS, Cidade Universitária, Campo Grande,
Mato Grosso do Sul, CEP: 79070900
Tel.:(67) 3345-7460
Observação de Entrega:
Fornecedores Sugeridos:
Finalidade: ESUD | CIESUD 2026
Meta: Meta 1. Oferta dos cursos de Licenciatura em Letras Português/Espanhol, Pedagogia e História
Etapa:Etapa 3 -Atividades do 3º Ano dos cursos
23/09/2026 - 15:18 Conveniar - Gestão de Convênios e Contratos Página: 1 de 1
"""

ESPERADO = {
    "numero": "33276", "ano": "2026", "tipo": "aerea",
    "solicitante": {"nome": "Maria Exemplo Souza", "email": "maria.exemplo@ufms.br", "telefone": ""},
    "projeto": {"numero": "371", "nome": "UFMS - Contrato n 111/2023 - UFMS Digital",
                "coordenador": "João Coordenador Lima", "gestor": "Ana Gestora Martins", "conta_caixa": "36889"},
    "finalidade": "ESUD | CIESUD 2026",
    "passageiros": [{"nome": "FULANO DE TAL SILVA", "cpf": "12345678909",
                     "email": "fulano.silva@ufms.br", "telefone": "(67) 99999 0000"}],
    "trechos": [
        {"ordem": 1, "sentido": "ida", "origem": "Campo Grande", "destino": "Florianópolis",
         "data": "16/11/2026", "hora": "08:00", "pessoas": 1, "bagagem": "1 bagagem despachada até 23kg"},
        {"ordem": 2, "sentido": "volta", "origem": "Florianópolis", "destino": "Campo Grande",
         "data": "20/11/2026", "hora": "20:15", "pessoas": 1, "bagagem": "1 bagagem despachada até 23kg"},
    ],
}


def test_exemplo_retorna_json_esperado():
    r = ler_texto(TEXTO_EXEMPLO)
    for chave, valor in ESPERADO.items():
        assert r[chave] == valor, chave


def test_projeto_371_sem_espaco():
    assert ler_texto(TEXTO_EXEMPLO)["projeto"]["numero"] == "371"


def test_campos_extras_e_item():
    r = ler_texto(TEXTO_EXEMPLO)
    assert r["data_pedido"] == "10/09/2026"
    assert r["situacao"] == "Aprovado"
    assert r["cpf_invalidos"] == []
    item = r["itens"][0]
    assert item["produto"] == "Passagem Aérea"
    assert item["quantidade"] == 2
    assert item["valor_unit"] == 769.51
    assert item["valor_total"] == 1539.02
    assert item["descricao"].startswith("Passagem Aérea - FULANO DE TAL SILVA. CPF - 12345678909")
    assert "Local de Entrega" not in item["descricao"]


def test_campos_vazios_nao_quebram():
    r = ler_texto("Nº Pedido: 1/2026\nSolicitante:Fulano Telefone: E-mail:\nCentro Custo: Conta Caixa:\n")
    assert r["numero"] == "1"
    assert r["solicitante"] == {"nome": "Fulano", "email": "", "telefone": ""}
    assert r["projeto"]["conta_caixa"] == ""
    assert r["itens"] == [] and r["tipo"] == "outro"


def test_cpf_invalido_e_marcado():
    texto = TEXTO_EXEMPLO.replace("12345678909", "12345678900")
    assert ler_texto(texto)["cpf_invalidos"] == ["12345678900"]


def test_varios_itens_somam_pessoas_nos_trechos_identicos():
    item2 = (
        "2 Produto/Serviço: Passagem Aérea 2 Unidade 769,51 1.539,02 Real\n"
        "Descrição: Passagem Aérea - BELTRANA DE SOUZA. CPF - 529.982.247-25 EMAIL - bel@ufms.br\n"
        "CONTATO - (67) 98888-1111. Trecho: Campo Grande/MS x Florianópolis/SC x Campo Grande/MS\n"
        "Ida dia 16/11/2026, 08:00:00. Volta dia 20/11/2026, 20:15:00. Com 1 bagagem despachada até 23kg.\n"
    )
    texto = TEXTO_EXEMPLO.replace("Local de Entrega:", item2 + "Local de Entrega:", 1)
    r = ler_texto(texto)
    assert len(r["itens"]) == 2
    assert [p["nome"] for p in r["passageiros"]] == ["FULANO DE TAL SILVA", "BELTRANA DE SOUZA"]
    assert r["passageiros"][1]["cpf"] == "52998224725"
    assert r["passageiros"][1]["telefone"] == "(67) 98888-1111"
    assert len(r["trechos"]) == 2
    assert all(t["pessoas"] == 2 for t in r["trechos"])


def test_tipo_do_produto():
    assert tipo_do_produto("Passagem Aérea") == "aerea"
    assert tipo_do_produto("Passagem Terrestre") == "terrestre"
    assert tipo_do_produto("Passagem Rodoviária") == "terrestre"
    assert tipo_do_produto("Hospedagem") == "hospedagem"
    assert tipo_do_produto("Material de consumo") == "outro"


def test_trecho_so_ida_e_sem_bagagem():
    s = sugestoes_da_descricao(
        "Passagem Aérea - ANA PAULA. CPF - 52998224725. Trecho: Campo Grande/MS x Brasília/DF "
        "Ida dia 01/12/2026, 07:30. Sem bagagem."
    )
    assert len(s["trechos"]) == 1
    t = s["trechos"][0]
    assert (t["origem"], t["destino"], t["data"], t["hora"]) == ("Campo Grande", "Brasília", "01/12/2026", "07:30")
    assert t["bagagem"] == "Sem bagagem"


def test_trecho_tres_cidades():
    s = sugestoes_da_descricao(
        "Passagem Aérea - ANA PAULA. Trecho: Campo Grande/MS x Florianópolis/SC x Porto Alegre/RS "
        "Ida dia 01/12/2026, 07:30. Volta dia 05/12/2026, 18:00."
    )
    pernas = [(t["origem"], t["destino"], t["sentido"]) for t in s["trechos"]]
    assert pernas == [("Campo Grande", "Florianópolis", "ida"), ("Florianópolis", "Porto Alegre", "volta")]


def test_hospedagem_sugestoes():
    s = sugestoes_da_descricao(
        "Hospedagem - MARIA SILVA. CPF - 52998224725. Cidade: Dourados/MS. Check-in 10/10/2026 "
        "Check-out 12/10/2026. Quarto single.",
        "hospedagem",
    )
    h = s["hospedagem"]
    assert (h["cidade"], h["checkin"], h["checkout"]) == ("Dourados", "10/10/2026", "12/10/2026")
    assert h["quarto"].lower() == "single"
    assert s["passageiros"][0]["nome"] == "MARIA SILVA"


def _gerar_pdf(caminho: Path, texto: str) -> None:
    import pymupdf

    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_text((30, 40), texto, fontsize=7)
    doc.save(caminho)
    doc.close()


def test_ler_pedido_de_pdf_gerado(tmp_path):
    pdf = tmp_path / "pedido.pdf"
    _gerar_pdf(pdf, TEXTO_EXEMPLO)
    r = ler_pedido(pdf)
    for chave, valor in ESPERADO.items():
        assert r[chave] == valor, chave


PDFS_REAIS = sorted((Path(__file__).parent / "pdfs").glob("*.pdf"))


@pytest.mark.skipif(not PDFS_REAIS, reason="Nenhum PDF real em tests/pdfs/")
@pytest.mark.parametrize("pdf", PDFS_REAIS, ids=lambda p: p.name)
def test_pdfs_reais(pdf):
    r = ler_pedido(pdf)
    assert r["numero"].isdigit() and len(r["ano"]) == 4
    assert r["projeto"]["numero"].isdigit()
    assert r["itens"], "nenhum item encontrado"
