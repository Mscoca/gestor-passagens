"""Widgets reutilizáveis: botão de copiar, campo copiável, área de arrastar e soltar, avisos."""
from __future__ import annotations

import functools
import inspect
import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)

AMARELO = "#FFF6C2"      # sugestão tirada da Descrição
AMBAR = "#FFD98A"        # CPF inválido
VERDE = "#D4F1DC"        # menor valor
LARANJA = "#FFE2BF"      # prazo vencendo hoje
VERMELHO = "#F9D3D3"     # viagem próxima sem emissão

ESTILO = """
* { font-family: "Segoe UI"; font-size: 10pt; }
QWidget { color: #1f2933; }
QMainWindow, QDialog, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget { background: #f3f5f8; }
QLabel { background: transparent; }
QToolTip { background: #243447; color: #ffffff; border: none; padding: 4px 8px; }

/* menu lateral */
QListWidget#menu { background: #1f2d3d; color: #e8edf2; border: none; border-radius: 0; font-size: 11pt;
    padding-top: 12px; outline: 0; }
QListWidget#menu::item { padding: 12px 18px; margin: 2px 8px; border-radius: 6px; color: #cfd8e3; }
QListWidget#menu::item:hover { background: #2c3e52; color: #ffffff; }
QListWidget#menu::item:selected { background: #2f6690; color: #ffffff; font-weight: 600; }

/* cartões */
QGroupBox { background: #ffffff; border: 1px solid #dde3ea; border-radius: 8px;
    margin-top: 22px; padding: 14px 10px 10px 10px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 4px; padding: 0 4px 4px 4px;
    color: #2f6690; font-weight: 600; font-size: 10.5pt; background: transparent; }

/* campos */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit {
    background: #ffffff; color: #1f2933; border: 1px solid #c5cdd6; border-radius: 5px; padding: 5px 7px;
    selection-background-color: #2f6690; selection-color: #ffffff; }
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: #9fb3c8; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus { border: 1px solid #2f6690; }
QLineEdit:read-only { background: #f3f5f7; color: #3e4c59; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: #eef1f4; color: #8a96a3; }
QComboBox QAbstractItemView { background: #ffffff; color: #1f2933; border: 1px solid #c5cdd6;
    selection-background-color: #e3eef7; selection-color: #1f2933; outline: 0; }
QCheckBox, QRadioButton { background: transparent; spacing: 6px; }

/* botões */
QPushButton { background: #ffffff; color: #1f2933; border: 1px solid #b9c2cc; border-radius: 5px; padding: 6px 14px; }
QPushButton:hover { background: #eef3f8; border-color: #2f6690; }
QPushButton:pressed { background: #dde8f2; }
QPushButton#primario { background: #2f6690; color: #ffffff; border: 1px solid #2f6690; font-weight: 600; }
QPushButton#primario:hover { background: #3a7ca5; border-color: #3a7ca5; }
QPushButton#primario:pressed { background: #26557a; }
QPushButton:disabled, QPushButton#primario:disabled { color: #9aa5b1; background: #f0f2f4; border: 1px solid #d0d6dc; }
QToolButton { background: transparent; border: none; border-radius: 4px; padding: 2px; }
QToolButton:hover { background: #e3eef7; }

/* abas */
QTabWidget::pane { border: 1px solid #dde3ea; border-radius: 6px; background: #ffffff; top: -1px; }
QTabBar::tab { background: #e9edf2; color: #3e4c59; border: 1px solid #dde3ea; border-bottom: none;
    padding: 7px 16px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:hover { background: #f3f6f9; color: #1f2933; }
QTabBar::tab:selected { background: #ffffff; color: #2f6690; font-weight: 600; }

/* tabelas e listas */
QTableWidget, QTableView, QListWidget { background: #ffffff; color: #1f2933; alternate-background-color: #f7f9fb;
    border: 1px solid #dde3ea; border-radius: 6px; gridline-color: #e8ecf0;
    selection-background-color: #d6e6f3; selection-color: #1f2933; outline: 0; }
QHeaderView { background: transparent; }
QHeaderView::section { background: #eef2f6; color: #3e4c59; font-weight: 600; border: none;
    border-right: 1px solid #dde3ea; border-bottom: 1px solid #dde3ea; padding: 6px; }
QTableCornerButton::section { background: #eef2f6; border: none; }

/* rolagem */
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #c1cad4; border-radius: 5px; min-height: 30px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #9fb3c8; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #c1cad4; border-radius: 5px; min-width: 30px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: #9fb3c8; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* textos especiais */
QLabel#titulo { font-size: 17pt; font-weight: 600; color: #1f2d3d; padding: 2px 0 6px 0; }
QLabel#alerta { background: #fdecc8; color: #5c3d00; border: 1px solid #e8c77a; border-radius: 6px; padding: 8px; }
QFrame#soltar { border: 2px dashed #9fb3c8; border-radius: 10px; background: #ffffff; }
QFrame#soltar[ativo="true"] { border-color: #2f6690; background: #eaf2f8; }
QStatusBar { background: #e9edf2; color: #1f2933; }
"""


def aplicar_tema_claro(app) -> None:
    """Força o tema claro mesmo com o Windows em modo escuro (senão o fundo fica escuro e o texto some)."""
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QStyleFactory

    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:  # Qt < 6.8
        pass
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    cores = {
        QPalette.Window: "#f3f5f8", QPalette.WindowText: "#1f2933", QPalette.Base: "#ffffff",
        QPalette.AlternateBase: "#f7f9fb", QPalette.Text: "#1f2933", QPalette.Button: "#ffffff",
        QPalette.ButtonText: "#1f2933", QPalette.ToolTipBase: "#243447", QPalette.ToolTipText: "#ffffff",
        QPalette.Highlight: "#2f6690", QPalette.HighlightedText: "#ffffff", QPalette.Link: "#2f6690",
        QPalette.PlaceholderText: "#8a96a3", QPalette.BrightText: "#ffffff", QPalette.Light: "#ffffff",
        QPalette.Midlight: "#e9edf2", QPalette.Mid: "#c5cdd6", QPalette.Dark: "#9aa5b1",
        QPalette.Shadow: "#52606d",
    }
    for papel, cor in cores.items():
        pal.setColor(papel, QColor(cor))
    for papel in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, papel, QColor("#9aa5b1"))
    app.setPalette(pal)
    app.setStyleSheet(ESTILO)


# ------------------------------------------------------------------ erros amigáveis
def mensagem_amigavel(exc: BaseException) -> str:
    from core.leitor_pdf import ErroLeituraPDF
    from core.repositorio import ConflitoEdicao, DriveIndisponivel, PedidoJaExiste

    if isinstance(exc, (DriveIndisponivel, ConflitoEdicao, PedidoJaExiste, ErroLeituraPDF, ValueError)):
        return str(exc)
    if isinstance(exc, PermissionError):
        return "Sem permissão ou arquivo em uso (talvez aberto em outro programa ou sincronizando no Drive).\nTente novamente em instantes."
    if isinstance(exc, FileNotFoundError):
        return f"Arquivo ou pasta não encontrado.\n{getattr(exc, 'filename', '') or ''}"
    if isinstance(exc, OSError):
        return "Erro ao acessar arquivos. Verifique se o Google Drive está disponível."
    return "Ocorreu um erro inesperado. O detalhe foi gravado no log do sistema."


def tratar_erro(exc: BaseException, parent: QWidget | None = None, titulo: str = "Atenção") -> None:
    if isinstance(exc, ValueError):
        log.info("Validação: %s", type(exc).__name__)
    else:
        log.error("Erro tratado", exc_info=(type(exc), exc, exc.__traceback__))
    QMessageBox.warning(parent, titulo, mensagem_amigavel(exc))


def protegido(func: Callable) -> Callable:
    """Decora slots: exceções viram mensagem amigável na tela e o detalhe vai para o log."""
    try:
        n = len(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        n = None

    @functools.wraps(func)
    def envoltorio(*args):
        try:
            return func(*(args if n is None else args[:n]))
        except Exception as exc:  # noqa: BLE001
            parent = args[0] if args and isinstance(args[0], QWidget) else None
            tratar_erro(exc, parent)

    return envoltorio


# ------------------------------------------------------------------ copiar
class _Aviso(QLabel):
    def __init__(self, texto: str):
        super().__init__(texto)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setStyleSheet(
            "background:#243447; color:white; padding:4px 10px; border-radius:4px; font-size:9pt;"
        )


_avisos: list[_Aviso] = []


def mostrar_aviso(widget: QWidget | None, texto: str = "Copiado", ms: int = 2000) -> None:
    aviso = _Aviso(texto)
    if widget is not None:
        pos = widget.mapToGlobal(QPoint(0, widget.height() + 2))
    else:
        from PySide6.QtGui import QCursor

        pos = QCursor.pos() + QPoint(12, 12)
    aviso.adjustSize()
    aviso.move(pos)
    aviso.show()
    _avisos.append(aviso)

    def fechar():
        aviso.close()
        if aviso in _avisos:
            _avisos.remove(aviso)

    QTimer.singleShot(ms, fechar)


def copiar_texto(texto: str, widget: QWidget | None = None, aviso: str = "Copiado") -> None:
    QGuiApplication.clipboard().setText(texto or "")
    mostrar_aviso(widget, aviso)


_icone_copiar: QIcon | None = None


def icone_copiar() -> QIcon:
    """Ícone de duas folhas sobrepostas."""
    global _icone_copiar
    if _icone_copiar is None:
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        caneta = QPen(QColor("#3a5a7a"), 2.4)
        p.setPen(caneta)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRect(10, 3, 17, 20), 3, 3)
        p.drawRoundedRect(QRect(4, 9, 17, 20), 3, 3)
        p.end()
        _icone_copiar = QIcon(pm)
    return _icone_copiar


class BotaoCopiar(QToolButton):
    def __init__(self, obter_texto: Callable[[], str], parent=None, dica: str = "Copiar", aviso: str = "Copiado"):
        super().__init__(parent)
        self._obter = obter_texto
        self._aviso = aviso
        self.setIcon(icone_copiar())
        self.setToolTip(dica)
        self.setAutoRaise(True)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._copiar)

    def _copiar(self):
        copiar_texto(self._obter() or "", self, self._aviso)


class CampoCopiavel(QWidget):
    """Campo de texto (somente leitura por padrão) com botão de copiar ao lado."""

    def __init__(self, valor: str = "", parent=None, copia: Callable[[], str] | None = None,
                 somente_leitura: bool = True):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.edit = QLineEdit(valor or "")
        self.edit.setReadOnly(somente_leitura)
        self.edit.setCursorPosition(0)
        lay.addWidget(self.edit, 1)
        self.botao = BotaoCopiar(copia or self.edit.text, self)
        lay.addWidget(self.botao)

    def texto(self) -> str:
        return self.edit.text()

    def definir(self, valor: str) -> None:
        self.edit.setText(valor or "")
        self.edit.setCursorPosition(0)


def linha_copiavel(*widgets: QWidget) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    for x in widgets:
        lay.addWidget(x)
    return w


# ------------------------------------------------------------------ arrastar e soltar
def _arquivos_do_evento(evento) -> list[str]:
    md = evento.mimeData()
    if not md.hasUrls():
        return []
    return [u.toLocalFile() for u in md.urls() if u.isLocalFile() and Path(u.toLocalFile()).is_file()]


class AreaArrastarSoltar(QFrame):
    arquivos = Signal(list)

    def __init__(self, texto: str = "Arraste o arquivo aqui", filtro: str = "Todos os arquivos (*.*)",
                 multiplo: bool = False, parent=None, altura: int = 90):
        super().__init__(parent)
        self.setObjectName("soltar")
        self.setAcceptDrops(True)
        self.filtro = filtro
        self.multiplo = multiplo
        self.setMinimumHeight(altura)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        self.rotulo = QLabel(texto)
        self.rotulo.setAlignment(Qt.AlignCenter)
        self.rotulo.setStyleSheet("color:#3e4c59; font-size:12pt; border:none; background:transparent;")
        lay.addWidget(self.rotulo)
        botao = QPushButton("Selecionar…")
        botao.clicked.connect(self.selecionar)
        lay.addWidget(botao, alignment=Qt.AlignCenter)

    def selecionar(self):
        if self.multiplo:
            lista, _ = QFileDialog.getOpenFileNames(self, "Selecionar arquivos", "", self.filtro)
        else:
            arq, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", "", self.filtro)
            lista = [arq] if arq else []
        if lista:
            self.arquivos.emit(lista)

    def _ativo(self, sim: bool):
        self.setProperty("ativo", "true" if sim else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if _arquivos_do_evento(e):
            e.acceptProposedAction()
            self._ativo(True)

    def dragLeaveEvent(self, e):
        self._ativo(False)

    def dropEvent(self, e):
        self._ativo(False)
        lista = _arquivos_do_evento(e)
        if lista:
            self.arquivos.emit(lista if self.multiplo else lista[:1])
            e.acceptProposedAction()


class BotaoArquivo(QPushButton):
    """Botão que abre o seletor de arquivo e também aceita arrastar e soltar."""

    arquivo = Signal(str)

    def __init__(self, texto: str = "Anexar…", filtro: str = "Todos os arquivos (*.*)", parent=None):
        super().__init__(texto, parent)
        self.filtro = filtro
        self.setAcceptDrops(True)
        self.setToolTip("Clique para selecionar ou arraste o arquivo até aqui")
        self.clicked.connect(self._selecionar)

    def _selecionar(self):
        arq, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", "", self.filtro)
        if arq:
            self.arquivo.emit(arq)

    def dragEnterEvent(self, e):
        if _arquivos_do_evento(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        lista = _arquivos_do_evento(e)
        if lista:
            self.arquivo.emit(lista[0])
            e.acceptProposedAction()


# ------------------------------------------------------------------ utilidades
def abrir_pasta(caminho: Path) -> None:
    if not Path(caminho).exists():
        raise FileNotFoundError(str(caminho))
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho)))


def abrir_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl.fromEncoded(url.encode("ascii", "ignore")) if "%" in url else QUrl(url))


def titulo(texto: str) -> QLabel:
    l = QLabel(texto)
    l.setObjectName("titulo")
    return l


def destacar(widget: QWidget, cor: str | None) -> None:
    """Fundo colorido para QLineEdit e afins (None remove o destaque)."""
    widget.setStyleSheet(f"background:{cor};" if cor else "")
