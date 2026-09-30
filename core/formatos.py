"""Funções utilitárias de formatação: texto, CPF, moeda, datas e horas."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acentos e sem espaços nas pontas."""
    if not texto:
        return ""
    decomposto = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.lower().strip()


def somente_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def espacos_simples(texto: str | None) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


# ---------------------------------------------------------------- CPF
def cpf_valido(cpf: str | None) -> bool:
    d = somente_digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d[i]) * (tamanho + 1 - i) for i in range(tamanho))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if int(d[tamanho]) != digito:
            return False
    return True


def formatar_cpf(cpf: str | None) -> str:
    d = somente_digitos(cpf)
    if len(d) != 11:
        return cpf or ""
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def mascarar_cpf(cpf: str | None) -> str:
    d = somente_digitos(cpf)
    if len(d) != 11:
        return "***" if cpf else ""
    return f"{d[:3]}.***.***-{d[9:]}"


# ---------------------------------------------------------------- Moeda
def parse_moeda(texto) -> float | None:
    """Converte '1.539,02', 'R$ 1539,02' ou '1539.02' em float. Vazio -> None."""
    if texto is None:
        return None
    if isinstance(texto, (int, float)):
        return float(texto)
    s = str(texto).replace("R$", "").replace(" ", "").strip().replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") >= 1:
        partes = s.split(".")
        if len(partes[-1]) == 3 or len(partes) > 2:
            s = s.replace(".", "")
    try:
        return round(float(s), 2)
    except ValueError:
        raise ValueError(f"Valor inválido: {texto!r}. Use o formato 1.539,02.")


def formatar_moeda(valor, simbolo: bool = True) -> str:
    if valor is None or valor == "":
        return ""
    texto = f"{float(valor):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {texto}" if simbolo else texto


# ---------------------------------------------------------------- Datas
def parse_data(texto: str | None) -> date | None:
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", texto or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def formatar_data(d: date | datetime | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def data_iso(texto_br: str | None) -> str:
    d = parse_data(texto_br)
    return d.isoformat() if d else ""


def dia_mes(texto_br: str | None) -> str:
    """'16/11/2026' -> '16/11'."""
    d = parse_data(texto_br)
    return d.strftime("%d/%m") if d else (texto_br or "")


def proximo_dia_util(base: date) -> date:
    d = base + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def hora_hhmm(texto: str | None) -> str:
    """Normaliza '8h', '8h30', '08:00:00', '8:5' para 'HH:MM'. Inválido -> texto original."""
    s = (texto or "").strip().lower()
    if not s:
        return ""
    m = re.match(r"^(\d{1,2})\s*[:h]\s*(\d{2})?", s)
    if not m:
        return texto.strip()
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h > 23 or mi > 59:
        return texto.strip()
    return f"{h:02d}:{mi:02d}"


def hora_com_h(texto: str | None) -> str:
    """'06:30' -> '06h30'."""
    s = hora_hhmm(texto)
    return s.replace(":", "h") if re.match(r"^\d{2}:\d{2}$", s) else s


# ---------------------------------------------------------------- Nomes
def primeiro_nome(nome: str | None) -> str:
    partes = (nome or "").split()
    return partes[0].capitalize() if partes else "Passageiro"


def slug(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", normalizar(texto)).strip("_")
    return s or "empresa"
