"""Configuração local do analista, caminhos da aplicação, fuso e logs."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP = "GestorPassagens"
NOME_SISTEMA = "P.A.T.H. — Passagens Aéreas, Terrestres e Hospedagens"
VERSAO = "1.0.0"

PASTA_RAIZ_PADRAO = (
    r"G:\Drives compartilhados\DEP. COMPRAS E SERVIÇOS\2026\7. ATAS 2026\#CRED 01.2026"
)

CONFIG_PADRAO = {
    "pasta_raiz": PASTA_RAIZ_PADRAO,
    "modelo_pasta": "Pedido {numero}-{ano} {resumo}",
    "cc_padrao": "atas@fapec.org",
    "hora_prazo": "17:00",
    "gmail_authuser": "",
    "ultimo_grupo": 3,
    "analista_nome": "",
    "analista_email": "",
    "assinatura": "",
    "logins": {},
    "primeiro_uso_concluido": False,
}

try:
    from zoneinfo import ZoneInfo

    FUSO = ZoneInfo("America/Cuiaba")
except Exception:  # sem base tzdata: Cuiabá está em UTC-4 sem horário de verão
    FUSO = timezone(timedelta(hours=-4), "America/Cuiaba")


def agora() -> datetime:
    return datetime.now(FUSO)


def agora_iso() -> str:
    return agora().isoformat(timespec="seconds")


def parse_iso(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        d = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=FUSO)


# ------------------------------------------------------------------ caminhos
def dir_config() -> Path:
    base = os.environ.get("GP_APPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP


def dir_local() -> Path:
    base = os.environ.get("GP_LOCALAPPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / APP


def caminho_config() -> Path:
    return dir_config() / "config.json"


def caminho_indice() -> Path:
    return dir_local() / "indice.db"


def dir_logs() -> Path:
    return dir_local() / "logs"


def dir_recursos() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "recursos"
    return Path(__file__).resolve().parent.parent / "recursos"


# ------------------------------------------------------------------ config
def carregar_config() -> dict:
    cfg = json.loads(json.dumps(CONFIG_PADRAO))
    caminho = caminho_config()
    if caminho.exists():
        try:
            cfg.update(json.loads(caminho.read_text(encoding="utf-8")))
        except Exception:
            logging.getLogger(__name__).exception("config.json ilegível; usando padrões")
    return cfg


def salvar_config(cfg: dict) -> None:
    caminho = caminho_config()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, caminho)


# ------------------------------------------------------------------ logs
class FiltroDadosSensiveis(logging.Filter):
    """Rede de segurança: mascara CPFs que por engano cheguem ao log."""

    RE_CPF = re.compile(r"\b(\d{3})\.?\d{3}\.?\d{3}-?(\d{2})\b")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        novo = self.RE_CPF.sub(r"\1.***.***-\2", msg)
        if novo != msg:
            record.msg, record.args = novo, ()
        return True


def configurar_logs(nivel=logging.INFO) -> Path:
    pasta = dir_logs()
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "gestor.log"
    raiz = logging.getLogger()
    if not any(isinstance(h, RotatingFileHandler) for h in raiz.handlers):
        h = RotatingFileHandler(arquivo, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        h.addFilter(FiltroDadosSensiveis())
        raiz.addHandler(h)
    raiz.setLevel(nivel)
    return arquivo
