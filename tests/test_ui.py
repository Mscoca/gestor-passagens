"""Teste de fumaça da interface (plataforma Qt offscreen, diálogos simulados)."""
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox  # noqa: E402

from tests.test_leitor_pdf import TEXTO_EXEMPLO, _gerar_pdf  # noqa: E402


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("GP_APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("GP_LOCALAPPDATA", str(tmp_path / "local"))
    avisos = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: avisos.append(a[2])))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: avisos.append(a[2])))

    from app import criar_aplicacao
    from core.config import CONFIG_PADRAO
    from core.contexto import Contexto

    app = criar_aplicacao()
    raiz = tmp_path / "DEP. COMPRAS E SERVIÇOS" / "#CRED 01.2026"
    raiz.mkdir(parents=True)
    ctx = Contexto(dict(CONFIG_PADRAO, pasta_raiz=str(raiz), analista_nome="Ana", assinatura="Ana\nFAPEC",
                        primeiro_uso_concluido=True))
    ctx.repo.garantir_estrutura()
    pdf = tmp_path / "Downloads" / "pedido.pdf"
    pdf.parent.mkdir()
    _gerar_pdf(pdf, TEXTO_EXEMPLO)
    return app, ctx, pdf, avisos


def test_fluxo_completo(ambiente, monkeypatch, tmp_path):
    app, ctx, pdf, avisos = ambiente
    from ui.janela_principal import JanelaPrincipal
    from ui.painel_pedido import DialogoVencedora

    janela = JanelaPrincipal(ctx)
    janela.inicializar()
    form = janela.tela_novo
    form.carregar_pdf(str(pdf))
    assert form.resumo.text() == "CGR - FLN"
    assert form.tab_trechos.rowCount() == 2 and form.tab_pass.rowCount() == 1
    assert "G1" in form.rotulo_grupo.text()

    doc = tmp_path / "Downloads" / "cnh.jpg"
    doc.write_bytes(b"jpg")
    form._anexar_doc(form.tab_pass.cellWidget(0, 5), str(doc))
    form.coord_email.setText("coord@ufms.br")
    form.criar_e_salvar()
    assert not avisos, avisos

    pasta = ctx.repo.raiz / "PJ 371" / "Pedido 33276-2026 CGR - FLN"
    assert (pasta / "2. Doc Fulano.jpg").exists() and doc.exists()
    painel = janela.painel
    assert painel is not None and painel.pedido["grupo"]["numero"] == 1

    # ---- cotações: 3 valores com empate
    t = painel.tab_cot
    assert t.rowCount() == 3
    for r, valor in enumerate(("1.539,02", "1.539,02", "1.800,00")):
        t.item(r, 2).setText(valor)
    painel.salvar_cotacoes()
    assert len(painel.pedido["cotacoes"]) == 3
    proposta = tmp_path / "Downloads" / "proposta.pdf"
    proposta.write_bytes(b"%PDF")
    painel.anexar_proposta(0, str(proposta))
    assert (pasta / "4. Cotação" / "G1 - Condor - R$ 1.539,02.pdf").exists()

    def exec_desempate(dlg):
        for dh, pessoa, res in dlg.linhas.values():
            pessoa.setText("Atendente")
            res.setText("Manteve o valor")
        dlg.combo.setCurrentIndex(1)
        dlg.just.setText("Melhor horário de voo")
        return QDialog.Accepted

    monkeypatch.setattr(DialogoVencedora, "exec", exec_desempate)
    janela.painel.definir_vencedora()
    painel = janela.painel
    assert painel.pedido["vencedora"]["empresa_id"] == "plus_viagens"
    assert len(painel.pedido["desempate"]["ligacoes"]) == 2

    # ---- e-mail de aprovação
    painel.email_tipo.setCurrentIndex(1)
    painel.gerar_email()
    assert painel.em_para.text() == "maria.exemplo@ufms.br, coord@ufms.br"
    assert "Prazo para aprovação: até" in painel.em_corpo.toPlainText()
    assert painel.pedido["status"] == "aguardando_aprovacao"
    painel.email_tipo.setCurrentIndex(0)
    painel.gerar_email()
    assert painel.em_assunto.text().startswith("Pedido 33276 - PJ 371 | Cotação Passagens Aéreas")
    assert avisos == ["A Condor não tem e-mail de cotação cadastrado."]
    avisos.clear()

    # ---- arquivos e status
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (a[3][2], True)))
    janela.painel.anexar_fixo("reserva", str(proposta))
    assert (pasta / "5.1 Reserva Volta.pdf").exists()
    janela.painel.mudar_status("aprovado")
    janela.painel.mudar_status("emitido")
    p = ctx.repo.carregar("33276", "2026")
    assert p["status"] == "emitido" and p["aprovacao"]["resultado"] == "aprovado"
    acoes = [h["acao"] for h in p["historico"]]
    for a in ("pedido_criado", "cotacoes_registradas", "proposta_anexada", "vencedora_definida",
              "email_aprovacao_gerado", "arquivo_anexado", "status_aprovado", "status_emitido"):
        assert a in acoes, a

    # ---- lista e busca
    janela.tela_pedidos.busca.setText("Florianópolis")
    assert janela.tela_pedidos.tabela.rowCount() == 1
    janela.tela_pedidos.busca.setText("inexistente")
    assert janela.tela_pedidos.tabela.rowCount() == 0

    # ---- edição com renomear pasta
    from ui.tela_novo_pedido import FormularioPedido

    edit = FormularioPedido(ctx, ctx.repo.carregar("33276", "2026"))
    edit.resumo.setText("CGR - FLN - EXTRA")
    edit.salvar_edicao()
    assert (ctx.repo.raiz / "PJ 371" / "Pedido 33276-2026 CGR - FLN - EXTRA" / "1. Pedido 33276.pdf").exists()
    assert not avisos, avisos

    # ---- configurações abre e lista empresas
    janela.menu.setCurrentRow(2)
    janela.tela_config.atualizar()
    assert janela.tela_config.tab_emp.rowCount() == 10
    janela.close()


def test_segundo_pedido_usa_g2(ambiente):
    app, ctx, pdf, avisos = ambiente
    from ui.tela_novo_pedido import FormularioPedido

    for numero, grupo in (("33276", 1), ("40000", 2)):
        form = FormularioPedido(ctx)
        texto = TEXTO_EXEMPLO.replace("33276/2026", f"{numero}/2026")
        from core.leitor_pdf import ler_texto

        form.preencher_de_leitura(ler_texto(texto))
        form.criar_e_salvar()
        assert ctx.repo.carregar(numero, "2026")["grupo"]["numero"] == grupo
