"""Senhas dos portais: SOMENTE no Gerenciador de Credenciais do Windows (keyring).

A senha nunca vai para JSON, SQLite, log ou arquivo de texto.
"""
from __future__ import annotations

import logging
from typing import Callable

import keyring
from keyring.errors import PasswordDeleteError

log = logging.getLogger(__name__)

SEGUNDOS_LIMPEZA = 30


def servico(empresa_id: str) -> str:
    return f"GestorPassagens:{empresa_id}"


def salvar_senha(empresa_id: str, login: str, senha: str) -> None:
    if not login:
        raise ValueError("Informe o login antes de salvar a senha.")
    keyring.set_password(servico(empresa_id), login, senha)
    log.info("Senha salva no Gerenciador de Credenciais para a empresa %s", empresa_id)


def obter_senha(empresa_id: str, login: str) -> str | None:
    if not login:
        return None
    try:
        return keyring.get_password(servico(empresa_id), login)
    except Exception:
        log.exception("Falha ao ler o Gerenciador de Credenciais (empresa %s)", empresa_id)
        return None


def apagar_senha(empresa_id: str, login: str) -> None:
    try:
        keyring.delete_password(servico(empresa_id), login)
    except PasswordDeleteError:
        pass


class LimpadorAreaTransferencia:
    """Copia um texto sensível e o apaga depois de N segundos, se ele ainda estiver lá."""

    def __init__(self, clipboard=None, agendar: Callable[[int, Callable], None] | None = None):
        self._clipboard = clipboard
        self._agendar = agendar

    @property
    def clipboard(self):
        if self._clipboard is None:
            from PySide6.QtGui import QGuiApplication

            self._clipboard = QGuiApplication.clipboard()
        return self._clipboard

    def agendar(self, ms: int, fn: Callable) -> None:
        if self._agendar is not None:
            self._agendar(ms, fn)
        else:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(ms, fn)

    def copiar(self, texto: str, segundos: int = SEGUNDOS_LIMPEZA) -> None:
        self._definir_texto_sensivel(texto)
        self.agendar(segundos * 1000, lambda: self.limpar_se_igual(texto))

    def limpar_se_igual(self, texto: str) -> bool:
        if self.clipboard.text() == texto:
            self.clipboard.clear()
            return True
        return False

    def _definir_texto_sensivel(self, texto: str) -> None:
        """No Windows, marca o conteúdo para não entrar no histórico da área de transferência (Win+V)."""
        try:
            from PySide6.QtCore import QMimeData

            dados = QMimeData()
            dados.setText(texto)
            fmt = 'application/x-qt-windows-mime;value="{}"'
            dados.setData(fmt.format("ExcludeClipboardContentFromMonitorProcessing"), b"\x00")
            dados.setData(fmt.format("CanIncludeInClipboardHistory"), b"\x00\x00\x00\x00")
            dados.setData(fmt.format("CanUploadToCloudClipboard"), b"\x00\x00\x00\x00")
            self.clipboard.setMimeData(dados)
        except Exception:
            self.clipboard.setText(texto)
