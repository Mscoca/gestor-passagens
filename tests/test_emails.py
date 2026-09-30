from datetime import datetime
from urllib.parse import parse_qs, urlparse

from core import emails
from core.config import FUSO, dir_recursos


def modelo(nome):
    return (dir_recursos() / "modelos_email" / nome).read_text(encoding="utf-8")


def t(sentido, data, origem, destino, viacao, saida, chegada, pessoas=1):
    return {"sentido": sentido, "data": data, "origem": origem, "destino": destino, "companhia": viacao,
            "hora_saida": saida, "hora_chegada": chegada, "pessoas": pessoas}


ONZE_TRECHOS = [
    t("ida", "09/09/2026", "Jardim", "Campo Grande", "Cruzeiro do Sul", "06:30", "10:50"),
    t("ida", "09/09/2026", "Jardim", "Campo Grande", "Cruzeiro do Sul", "06:30", "10:50"),
    t("ida", "09/09/2026", "Dourados", "Campo Grande", "Viatur", "07:15", "11:30"),
    t("ida", "09/09/2026", "Ivinhema", "Campo Grande", "Andorinha", "05:00", "11:00"),
    t("ida", "09/09/2026", "Ivinhema", "Campo Grande", "Andorinha", "05:00", "11:00"),
    t("ida", "09/09/2026", "Ivinhema", "Campo Grande", "Andorinha", "05:00", "11:00"),
    t("volta", "11/09/2026", "Campo Grande", "Jardim", "Cruzeiro do Sul", "17:00", "21:20"),
    t("volta", "11/09/2026", "Campo Grande", "Jardim", "Cruzeiro do Sul", "17:00", "21:20"),
    t("volta", "12/09/2026", "Campo Grande", "Dourados", "Viatur", "14:00", "18:15"),
    t("volta", "12/09/2026", "Campo Grande", "Ivinhema", "Andorinha", "13:00", "19:00", pessoas=2),
    t("volta", "12/09/2026", "Campo Grande", "Ivinhema", "Andorinha", "13:00", "19:00"),
]


def test_bloco_terrestre_onze_trechos_agrupa_identicos():
    bloco = emails.bloco_terrestre(ONZE_TRECHOS)
    esperado_inicio = (
        "IDAS - 09/09/2026:\n\n"
        "TRECHOS IDÊNTICOS:\n\n"
        "3 pessoas - 09/09\nTrecho: Ivinhema x Campo Grande\nViação: Andorinha\nHorário: 05h00 às 11h00.\n\n"
        "2 pessoas - 09/09\nTrecho: Jardim x Campo Grande\nViação: Cruzeiro do Sul\nHorário: 06h30 às 10h50.\n\n"
        "TRECHOS INDIVIDUAIS:\n\n"
        "1 pessoa - 09/09\nTrecho: Dourados x Campo Grande\nViação: Viatur\nHorário: 07h15 às 11h30.\n\n"
        "VOLTAS - 11/09 e 12/09:\n\n"
        "DIA 11/09\n\n"
        "TRECHOS IDÊNTICOS:\n\n"
        "2 pessoas - 11/09\nTrecho: Campo Grande x Jardim\n"
    )
    assert bloco.startswith(esperado_inicio), bloco
    assert "DIA 12/09\n\nTRECHOS IDÊNTICOS:\n\n3 pessoas - 12/09\nTrecho: Campo Grande x Ivinhema" in bloco
    assert "TRECHOS INDIVIDUAIS:\n\n1 pessoa - 12/09\nTrecho: Campo Grande x Dourados" in bloco
    # 11 trechos -> 6 grupos
    assert bloco.count("Trecho:") == 6


PEDIDO = {
    "numero": "33276", "ano": "2026", "tipo": "aerea", "finalidade": "ESUD | CIESUD 2026", "resumo": "CGR - FLN",
    "projeto": {"numero": "371", "coordenador_email": "coord@ufms.br"},
    "solicitante": {"nome": "Maria", "email": "maria.exemplo@ufms.br"},
    "passageiros": [{"nome": "FULANO DE TAL SILVA"}],
    "trechos": [{"ordem": 1, "sentido": "ida", "origem": "Campo Grande", "origem_codigo": "CGR",
                 "destino": "Florianópolis", "destino_codigo": "FLN", "data": "16/11/2026", "hora_saida": "08:00",
                 "pessoas": 1, "bagagem": "1 bagagem despachada até 23kg"}],
}


def test_assunto():
    assert emails.montar_assunto(PEDIDO, modelo("assunto.txt")) == \
        "Pedido 33276 - PJ 371 | Cotação Passagens Aéreas - ESUD | CIESUD 2026"
    sem_finalidade = {**PEDIDO, "finalidade": "", "tipo": "terrestre"}
    assert emails.montar_assunto(sem_finalidade, modelo("assunto.txt")).endswith("Passagem Terrestre - CGR - FLN")


def test_saudacao():
    assert emails.saudacao(datetime(2026, 9, 29, 11, 59, tzinfo=FUSO)) == "bom dia"
    assert emails.saudacao(datetime(2026, 9, 29, 12, 0, tzinfo=FUSO)) == "boa tarde"


def test_aprovacao_dois_destinatarios_e_prazo():
    assert emails.destinatarios_aprovacao(PEDIDO) == ["maria.exemplo@ufms.br", "coord@ufms.br"]
    corpo = emails.corpo_aprovacao(PEDIDO, modelo("aprovacao.txt"), "30/09/2026", "17:00", 10, "Ana\nFAPEC",
                                   datetime(2026, 9, 29, 9, 0, tzinfo=FUSO))
    assert corpo.startswith("Prezados, bom dia.")
    assert "pedido Nº 33276/2026" in corpo
    assert "operação com 10 empresas credenciadas" in corpo
    assert "Passageiro(a): FULANO DE TAL SILVA" in corpo
    assert "Prazo para aprovação: até 30/09, 17:00, para emissão dos bilhetes." in corpo
    assert corpo.endswith("Atenciosamente,\nAna\nFAPEC")


def test_aprovacao_hospedagem():
    ped = {**PEDIDO, "tipo": "hospedagem", "hospedagem": {"cidade": "Dourados", "hotel": "Hotel X", "hospedes": 2,
                                                         "checkin": "10/10/2026", "checkout": "12/10/2026",
                                                         "quarto": "Duplo"}}
    corpo = emails.corpo_aprovacao(ped, modelo("aprovacao.txt"), "30/09/2026", "17:00", 10)
    assert "dados da hospedagem" in corpo
    assert "Hotel: Hotel X\nHóspedes: 2\nDiárias: 2\nCheck-in: 10/10/2026\nCheck-out: 12/10/2026\nQuarto: Duplo\n\nObs:" in corpo


def test_cotacao_hospedagem():
    ped = {**PEDIDO, "tipo": "hospedagem", "hospedagem": {"cidade": "Dourados", "hospedes": 1,
                                                         "checkin": "10/10/2026", "checkout": "13/10/2026",
                                                         "quarto": "Single"}}
    corpo = emails.corpo_cotacao(ped, modelo("cotacao_empresa.txt"), "Ana", momento=datetime(2026, 9, 29, 15, tzinfo=FUSO))
    assert corpo.startswith("Prezados, boa tarde!\n\nSolicito a cotação de hospedagem")
    assert "Cidade: Dourados\nHóspedes: 1\nCheck-in: 10/10/2026\nCheck-out: 13/10/2026 (3 diárias)\nQuarto: Single" in corpo


def test_url_gmail_codificada():
    url, com_corpo = emails.url_gmail("ana@fapec.org", ["a@x.com", "b@y.com"], ["atas@fapec.org"],
                                      "Pedido 33276 - PJ 371 | Cotação", "Olá & até já\nLinha 2")
    assert com_corpo
    assert url.startswith("https://mail.google.com/mail/?view=cm&fs=1&authuser=ana%40fapec.org&to=")
    assert " " not in url and "\n" not in url
    q = parse_qs(urlparse(url).query)
    assert q["to"] == ["a@x.com,b@y.com"]
    assert q["su"] == ["Pedido 33276 - PJ 371 | Cotação"]
    assert q["body"] == ["Olá & até já\nLinha 2"]


def test_url_gmail_longa_sai_sem_corpo():
    url, com_corpo = emails.url_gmail("", "a@x.com", "", "Assunto", "x" * 8000)
    assert not com_corpo and "body=" not in url and "authuser" not in url
