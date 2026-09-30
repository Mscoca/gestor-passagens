"""Lista de pedidos com busca, filtros e destaques de prazo."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config import agora
from core.contexto import Contexto
from core.modelo import STATUS, TIPOS
from ui.widgets import LARANJA, VERMELHO, protegido, titulo

COLUNAS = ["Nº", "Projeto", "Tipo", "Passageiro(s)", "Resumo", "Viagem", "Grupo", "Status", "Prazo", "Analista"]
DIAS_ALERTA = 5


def _br(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if iso and len(iso) >= 10 else ""


def ordenar(linhas: list[dict], hoje: date) -> list[dict]:
    """Viagens futuras (mais próximas primeiro), depois passadas (mais recentes primeiro), depois sem data."""
    h = hoje.isoformat()

    def chave(r):
        d = r.get("data_viagem") or ""
        if not d:
            return (2, "")
        if d >= h:
            return (0, d)
        return (1, "".join(chr(255 - ord(c)) for c in d))

    return sorted(linhas, key=chave)


def cor_da_linha(r: dict, hoje: date) -> str | None:
    status = r.get("status")
    viagem = r.get("data_viagem") or ""
    if viagem and status not in ("emitido", "cancelado"):
        if hoje.isoformat() <= viagem <= (hoje + timedelta(days=DIAS_ALERTA)).isoformat():
            return VERMELHO
    if r.get("prazo") == hoje.isoformat() and status not in ("emitido", "cancelado"):
        return LARANJA
    return None


class TelaPedidos(QWidget):
    abrirPedido = Signal(str)

    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        h = QHBoxLayout()
        h.addWidget(titulo("Pedidos"))
        h.addStretch(1)
        self.aviso_drive = QLabel("")
        self.aviso_drive.setObjectName("alerta")
        self.aviso_drive.setVisible(False)
        v.addLayout(h)
        v.addWidget(self.aviso_drive)

        h = QHBoxLayout()
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar por nº do pedido, projeto, passageiro, CPF ou cidade…")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(self.filtrar)
        self.f_status = QComboBox()
        self.f_status.addItem("Todos os status", None)
        for k, rot in STATUS.items():
            self.f_status.addItem(rot, k)
        self.f_tipo = QComboBox()
        self.f_tipo.addItem("Todos os tipos", None)
        for k, rot in TIPOS.items():
            self.f_tipo.addItem(rot, k)
        self.f_status.currentIndexChanged.connect(self.filtrar)
        self.f_tipo.currentIndexChanged.connect(self.filtrar)
        atualizar = QPushButton("Atualizar")
        atualizar.setToolTip("Relê os pedidos do Drive")
        atualizar.clicked.connect(self.atualizar)
        h.addWidget(self.busca, 1)
        h.addWidget(self.f_status)
        h.addWidget(self.f_tipo)
        h.addWidget(atualizar)
        v.addLayout(h)

        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setAlternatingRowColors(False)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tabela.cellDoubleClicked.connect(self._abrir)
        v.addWidget(self.tabela, 1)
        legenda = QLabel(
            f"<span style='background:{VERMELHO}; color:#1f2933'>&nbsp;Vermelho&nbsp;</span> viagem nos próximos {DIAS_ALERTA} dias sem "
            f"emissão &nbsp; <span style='background:{LARANJA}; color:#1f2933'>&nbsp;Laranja&nbsp;</span> prazo de aprovação vence hoje "
            "&nbsp; — duplo clique abre o pedido"
        )
        v.addWidget(legenda)
        self.contador = QLabel("")
        v.addWidget(self.contador)

    @protegido
    def atualizar(self):
        """Relê os JSONs do Drive e reconstrói o índice local."""
        repo = self.ctx.repo
        if repo.drive_disponivel():
            repo.garantir_estrutura()
            repo.reconstruir_indice()
            self.aviso_drive.setVisible(False)
        else:
            self.aviso_drive.setText(
                f"Drive indisponível: {repo.raiz}\nMostrando a última lista conhecida. Abra o Google Drive e clique em Atualizar.")
            self.aviso_drive.setVisible(True)
        self.filtrar()

    @protegido
    def filtrar(self):
        linhas = self.ctx.repo.buscar(self.busca.text(), self.f_status.currentData(), self.f_tipo.currentData())
        hoje = agora().date()
        linhas = ordenar(linhas, hoje)
        t = self.tabela
        t.setRowCount(len(linhas))
        for r, l in enumerate(linhas):
            valores = [
                f"{l['numero']}/{l['ano']}", l["projeto"], TIPOS.get(l["tipo"], l["tipo"]), l["passageiros"],
                l["resumo"], _br(l["data_viagem"]), f"G{l['grupo']}" if l["grupo"] else "",
                STATUS.get(l["status"], l["status"]), _br(l["prazo"]), l["analista"],
            ]
            cor = cor_da_linha(l, hoje)
            for c, val in enumerate(valores):
                item = QTableWidgetItem(val)
                if c == 0:
                    item.setData(Qt.UserRole, l["id"])
                if cor:
                    item.setBackground(QColor(cor))
                t.setItem(r, c, item)
        t.resizeColumnsToContents()
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.contador.setText(f"{len(linhas)} pedido(s)")

    def _abrir(self, linha: int, _col: int):
        item = self.tabela.item(linha, 0)
        if item:
            self.abrirPedido.emit(item.data(Qt.UserRole))
