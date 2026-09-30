"""Janela principal com menu lateral: Pedidos, Novo pedido, Configurações."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QMainWindow, QMessageBox, QStackedWidget, QWidget

from core.config import NOME_SISTEMA, VERSAO
from core.contexto import Contexto
from ui.painel_pedido import PainelPedido
from ui.tela_configuracoes import TelaConfiguracoes
from ui.tela_novo_pedido import FormularioPedido
from ui.tela_pedidos import TelaPedidos
from ui.widgets import protegido

log = logging.getLogger(__name__)


class JanelaPrincipal(QMainWindow):
    def __init__(self, ctx: Contexto):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{NOME_SISTEMA} — v{VERSAO}")
        self.resize(1280, 820)
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.menu = QListWidget()
        self.menu.setObjectName("menu")
        self.menu.setFixedWidth(200)
        self.menu.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.menu.addItems(["Pedidos", "Novo pedido", "Configurações"])
        self.menu.setFocusPolicy(Qt.NoFocus)
        lay.addWidget(self.menu)
        self.pilha = QStackedWidget()
        lay.addWidget(self.pilha, 1)
        self.setCentralWidget(central)

        self.tela_pedidos = TelaPedidos(ctx)
        self.tela_novo = FormularioPedido(ctx)
        self.tela_config = TelaConfiguracoes(ctx)
        for w in (self.tela_pedidos, self.tela_novo, self.tela_config):
            self.pilha.addWidget(w)
        self.painel: PainelPedido | None = None

        self.menu.currentRowChanged.connect(self._menu)
        self.tela_pedidos.abrirPedido.connect(self.abrir_pedido)
        self.tela_novo.pedidoSalvo.connect(self._pedido_criado)
        self.tela_config.configAlterada.connect(self._config_alterada)
        self.menu.setCurrentRow(0)

    def inicializar(self):
        """Verifica o Drive, cria a estrutura e reconstrói o índice local."""
        repo = self.ctx.repo
        if not repo.drive_disponivel():
            QMessageBox.warning(
                self, "Drive indisponível",
                f"A pasta raiz não está acessível:\n{repo.raiz}\n\n"
                "Abra o Google Drive para computador (unidade G:) e clique em Atualizar na lista de pedidos.\n"
                "Enquanto isso, a lista mostra a última versão conhecida.")
        self.tela_pedidos.atualizar()
        try:
            if repo.arquivos_duplicados():
                self.statusBar().showMessage("Atenção: há arquivos duplicados pelo Drive. Veja Configurações.", 15000)
        except Exception:
            log.exception("Falha ao verificar duplicados")

    def _menu(self, linha: int):
        if linha == 1:
            self.tela_novo.atualizar_grupo()
        self.pilha.setCurrentIndex(linha)

    @protegido
    def abrir_pedido(self, pid: str):
        if self.painel is not None:
            self.pilha.removeWidget(self.painel)
            self.painel.deleteLater()
        self.painel = PainelPedido(self.ctx, pid)
        self.painel.voltar.connect(self.voltar_lista)
        self.painel.alterado.connect(self.tela_pedidos.filtrar)
        self.pilha.addWidget(self.painel)
        self.pilha.setCurrentWidget(self.painel)
        self.menu.blockSignals(True)
        self.menu.clearSelection()
        self.menu.setCurrentRow(-1)
        self.menu.blockSignals(False)

    def voltar_lista(self):
        self.menu.setCurrentRow(0)
        self.pilha.setCurrentIndex(0)

    def _pedido_criado(self, pid: str):
        self.tela_pedidos.filtrar()
        self.statusBar().showMessage(f"Pedido {pid.replace('-', '/')} salvo.", 8000)
        self.abrir_pedido(pid)

    def _config_alterada(self):
        self.tela_pedidos.atualizar()
