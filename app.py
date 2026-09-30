"""P.A.T.H. — Passagens Aéreas, Terrestres e Hospedagens (FAPEC).

Uso:
    python app.py                       abre o programa
    python app.py --autoteste PASTA     cria um pedido de teste em PASTA, abre o painel e fecha (código 0 = ok)
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import APP, configurar_logs, dir_recursos  # noqa: E402

log = logging.getLogger("app")


def criar_aplicacao():
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication

    from ui.widgets import aplicar_tema_claro

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setFont(QFont("Segoe UI", 10))
    aplicar_tema_claro(app)
    icone = dir_recursos() / "icone.ico"
    if icone.exists():
        app.setWindowIcon(QIcon(str(icone)))
    return app


def instalar_excecao_global():
    from PySide6.QtWidgets import QMessageBox

    def gancho(tipo, valor, tb):
        log.error("Exceção não tratada:\n%s", "".join(traceback.format_exception(tipo, valor, tb)))
        try:
            from ui.widgets import mensagem_amigavel

            QMessageBox.critical(None, "Erro", mensagem_amigavel(valor))
        except Exception:
            pass

    sys.excepthook = gancho


def main() -> int:
    if "--autoteste" in sys.argv:
        return autoteste(Path(sys.argv[sys.argv.index("--autoteste") + 1]))
    configurar_logs()
    log.info("Iniciando")
    app = criar_aplicacao()
    instalar_excecao_global()

    from PySide6.QtCore import QTimer

    from core.contexto import Contexto
    from ui.janela_principal import JanelaPrincipal
    from ui.tela_configuracoes import AssistentePrimeiroUso

    ctx = Contexto()
    if not ctx.config.get("primeiro_uso_concluido"):
        if not AssistentePrimeiroUso(ctx).exec():
            return 0
    janela = JanelaPrincipal(ctx)
    janela.show()
    QTimer.singleShot(100, janela.inicializar)
    return app.exec()


def autoteste(pasta: Path) -> int:
    """Teste de fumaça do executável: pasta raiz temporária, pedido criado pela tela e fechamento."""
    pasta = pasta.resolve()
    raiz = pasta / "DEP. COMPRAS E SERVIÇOS" / "#CRED 01.2026"
    raiz.mkdir(parents=True, exist_ok=True)
    os.environ["GP_APPDATA"] = str(pasta / "_appdata")
    os.environ["GP_LOCALAPPDATA"] = str(pasta / "_localappdata")
    resultado = pasta / "autoteste.txt"
    configurar_logs()
    try:
        import pymupdf
        from PySide6.QtCore import QTimer

        from core.config import CONFIG_PADRAO, salvar_config
        from core.contexto import Contexto
        from ui.janela_principal import JanelaPrincipal

        app = criar_aplicacao()
        cfg = dict(CONFIG_PADRAO, pasta_raiz=str(raiz), analista_nome="Autoteste", primeiro_uso_concluido=True)
        salvar_config(cfg)
        ctx = Contexto(cfg)
        ctx.repo.garantir_estrutura()

        texto = (dir_recursos() / "exemplo_pedido.txt").read_text(encoding="utf-8")
        pdf = pasta / "Pedido exemplo.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((30, 40), texto, fontsize=7)
        doc.save(pdf)
        doc.close()

        janela = JanelaPrincipal(ctx)
        janela.show()
        janela.inicializar()
        janela.menu.setCurrentRow(1)
        janela.tela_novo.carregar_pdf(str(pdf))
        janela.tela_novo.criar_e_salvar()

        esperado = raiz / "PJ 371" / "Pedido 33276-2026 CGR - FLN" / "1. Pedido 33276.pdf"
        erros = []
        if not esperado.exists():
            erros.append(f"arquivo não criado: {esperado}")
        if not ctx.repo.existe("33276", "2026"):
            erros.append("JSON do pedido não gravado")
        elif ctx.repo.carregar("33276", "2026")["grupo"]["numero"] != 1:
            erros.append("grupo diferente de G1")
        if not ctx.repo.buscar("fulano"):
            erros.append("índice não encontrou o passageiro")
        if janela.painel is None:
            erros.append("painel do pedido não abriu")
        import keyring

        if os.name == "nt" and "Windows" not in type(keyring.get_keyring()).__module__:
            erros.append(f"backend do keyring inesperado: {keyring.get_keyring()!r}")
        QTimer.singleShot(1500, app.quit)
        app.exec()
        resultado.write_text("OK\n" if not erros else "FALHOU\n" + "\n".join(erros), encoding="utf-8")
        return 0 if not erros else 1
    except Exception:
        resultado.write_text("ERRO\n" + traceback.format_exc(), encoding="utf-8")
        return 2


if __name__ == "__main__":
    sys.exit(main())
