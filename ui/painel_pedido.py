"""Painel do pedido: abas Dados, Grupo e acessos, Cotações, E-mails, Arquivos e Histórico."""
from __future__ import annotations

import copy
import logging
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import cotacoes as cot
from core import emails, pastas
from core.config import agora, agora_iso
from core.contexto import Contexto
from core.credenciais import LimpadorAreaTransferencia, obter_senha
from core.formatos import (
    formatar_cpf,
    formatar_data,
    formatar_moeda,
    mascarar_cpf,
    parse_data,
    parse_moeda,
    proximo_dia_util,
)
from core.modelo import STATUS, TIPOS, TRANSICOES, aplicar_status, descritivo, id_pedido
from core.repositorio import ConflitoEdicao
from core.rodizio import GRUPOS, trocar_grupo
from ui.widgets import (
    VERDE,
    BotaoArquivo,
    BotaoCopiar,
    CampoCopiavel,
    abrir_pasta,
    abrir_url,
    copiar_texto,
    mostrar_aviso,
    protegido,
    titulo,
)

log = logging.getLogger(__name__)
_limpador = LimpadorAreaTransferencia()

ROTULOS_ACAO = {
    "pedido_criado": "Pedido criado", "dados_editados": "Dados editados", "grupo_manual": "Grupo escolhido manualmente",
    "grupo_trocado": "Grupo trocado", "grupo_ajustado_sincronizacao": "Grupo ajustado (sincronização)",
    "cotacoes_registradas": "Cotações registradas", "proposta_anexada": "Proposta anexada",
    "vencedora_definida": "Vencedora definida", "arquivo_anexado": "Arquivo anexado",
    "email_aprovacao_gerado": "E-mail de aprovação gerado", "email_cotacao_gerado": "E-mail de cotação gerado",
    "pasta_renomeada": "Pasta renomeada", "status_aguardando_aprovacao": "Status: Aguardando aprovação",
    "status_aprovado": "Status: Aprovado", "status_reprovado": "Status: Reprovado (volta para Em cotação)",
    "status_emitido": "Status: Emitido", "status_cancelado": "Status: Cancelado",
    "status_em_cotacao": "Status: Reaberto (Em cotação)",
}


def _form(parent=None) -> QFormLayout:
    f = QFormLayout(parent)
    f.setLabelAlignment(Qt.AlignRight)
    f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    return f


def _rolagem(conteudo: QWidget) -> QScrollArea:
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setFrameShape(QScrollArea.NoFrame)
    s.setWidget(conteudo)
    return s


class PainelPedido(QWidget):
    voltar = Signal()
    alterado = Signal()

    def __init__(self, ctx: Contexto, pid: str, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.pid = pid
        self.pedido: dict = {}
        self._esperado: str | None = None
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(20, 12, 20, 12)
        self.conteudo: QWidget | None = None
        self.recarregar()

    # ============================================================ carga e gravação
    def recarregar(self, aba: int | None = None):
        self.pedido = self.ctx.repo.carregar_por_id(self.pid)
        self._esperado = self.pedido.get("atualizado_em")
        if aba is None and self.conteudo is not None:
            aba = self.abas.currentIndex()
        if self.conteudo is not None:
            self.lay.removeWidget(self.conteudo)
            self.conteudo.deleteLater()
        self.conteudo = QWidget()
        v = QVBoxLayout(self.conteudo)
        v.setContentsMargins(0, 0, 0, 0)
        self.cab = self._cabecalho()
        v.addWidget(self.cab)
        self.abas = QTabWidget()
        self.abas.addTab(_rolagem(self._aba_dados()), "Dados")
        self.abas.addTab(_rolagem(self._aba_grupo()), "Grupo e acessos")
        self.abas.addTab(self._aba_cotacoes(), "Cotações")
        self.abas.addTab(self._aba_emails(), "E-mails")
        self.abas.addTab(self._aba_arquivos(), "Arquivos")
        self.abas.addTab(self._aba_historico(), "Histórico")
        if aba is not None:
            self.abas.setCurrentIndex(aba)
        v.addWidget(self.abas, 1)
        self.lay.addWidget(self.conteudo)

    def salvar(self, pedido: dict, acao: str, detalhe: str = "") -> bool:
        """Grava com checagem de conflito. Em conflito, avisa e recarrega."""
        try:
            self.ctx.repo.salvar(pedido, self.ctx.analista, acao, detalhe, esperado=self._esperado)
        except ConflitoEdicao as exc:
            QMessageBox.warning(self, "Pedido alterado", str(exc))
            self.recarregar()
            return False
        self.recarregar()
        self.alterado.emit()
        return True

    def copia(self) -> dict:
        return copy.deepcopy(self.pedido)

    @property
    def pasta(self) -> Path:
        return self.ctx.repo.pasta_do_pedido(self.pedido)

    @property
    def grupo(self) -> int | None:
        return (self.pedido.get("grupo") or {}).get("numero")

    # ============================================================ cabeçalho
    def _cabecalho(self) -> QWidget:
        p = self.pedido
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 6)
        h = QHBoxLayout()
        voltar = QPushButton("← Pedidos")
        voltar.clicked.connect(self.voltar.emit)
        h.addWidget(voltar)
        h.addWidget(titulo(f"Pedido {p['numero']}/{p['ano']} — {TIPOS.get(p.get('tipo'), 'Outro')}"))
        h.addStretch(1)
        atualizar = QPushButton("Recarregar")
        atualizar.clicked.connect(lambda: self.recarregar())
        editar = QPushButton("Editar dados")
        editar.clicked.connect(self.editar)
        pasta = QPushButton("Abrir pasta")
        pasta.setObjectName("primario")
        pasta.clicked.connect(self.abrir_pasta)
        for b in (atualizar, editar, pasta):
            h.addWidget(b)
        v.addLayout(h)

        ap = p.get("aprovacao") or {}
        prazo = f"{ap.get('prazo_data', '')} {ap.get('prazo_hora', '')}".strip() or "—"
        g = p.get("grupo") or {}
        grupo = f"G{g.get('numero')}" + (" (manual)" if g.get("manual") else "") if g else "—"
        venc = (p.get("vencedora") or {})
        info = QLabel(
            f"<b>Status:</b> {STATUS.get(p.get('status'), p.get('status'))} &nbsp;&nbsp; "
            f"<b>Grupo:</b> {grupo} &nbsp;&nbsp; <b>Prazo de aprovação:</b> {prazo} &nbsp;&nbsp; "
            f"<b>Projeto:</b> PJ {p['projeto'].get('numero', '')} &nbsp;&nbsp; <b>Resumo:</b> {p.get('resumo', '')}"
            + (f" &nbsp;&nbsp; <b>Vencedora:</b> {venc.get('empresa', '')} {formatar_moeda(venc.get('valor'))}" if venc else "")
        )
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(info)

        h = QHBoxLayout()
        h.addWidget(QLabel("Mudar status:"))
        for acao, rotulo in TRANSICOES.get(p.get("status", "em_cotacao"), []):
            b = QPushButton(rotulo)
            b.clicked.connect(lambda _=False, a=acao: self.mudar_status(a))
            h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        return w

    @protegido
    def abrir_pasta(self):
        abrir_pasta(self.pasta)

    @protegido
    def editar(self):
        from ui.tela_novo_pedido import DialogoEditarPedido

        dlg = DialogoEditarPedido(self.ctx, self.pedido, self)
        if dlg.exec():
            self.recarregar()
            self.alterado.emit()

    @protegido
    def mudar_status(self, acao: str):
        detalhe = ""
        if acao in ("cancelado", "reprovado"):
            texto, ok = QInputDialog.getText(self, "Motivo", "Motivo (opcional):" if acao == "reprovado" else "Motivo do cancelamento:")
            if not ok:
                return
            if acao == "cancelado" and not texto.strip():
                raise ValueError("Informe o motivo do cancelamento.")
            detalhe = texto.strip()
        p = self.copia()
        # aplicar_status registra o histórico; salvar() registra a gravação
        aplicar_status(p, acao, self.ctx.analista, detalhe)
        historico = p["historico"].pop()
        self.salvar(p, historico["acao"], historico["detalhe"])

    # ============================================================ aba Dados
    def _aba_dados(self) -> QWidget:
        p = self.pedido
        w = QWidget()
        v = QVBoxLayout(w)
        h = QHBoxLayout()
        b = QPushButton("Copiar descritivo")
        b.setObjectName("primario")
        b.clicked.connect(lambda: copiar_texto(descritivo(self.pedido), b))
        h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)

        g = QGroupBox("Pedido e projeto")
        f = _form(g)
        pj = p.get("projeto", {})
        s = p.get("solicitante", {})
        for rot, val in (
            ("Nº do pedido", f"{p['numero']}/{p['ano']}"), ("Data do pedido", p.get("data_pedido", "")),
            ("Tipo", TIPOS.get(p.get("tipo"), "")), ("Finalidade", p.get("finalidade", "")),
            ("Situação no Conveniar", p.get("situacao_conveniar", "")),
            ("Projeto", f"{pj.get('numero', '')} - {pj.get('nome', '')}"), ("Coordenador", pj.get("coordenador", "")),
            ("E-mail do coordenador", pj.get("coordenador_email", "")), ("Gestor", pj.get("gestor", "")),
            ("Conta caixa", pj.get("conta_caixa", "")), ("Solicitante", s.get("nome", "")),
            ("E-mail do solicitante", s.get("email", "")), ("Telefone do solicitante", s.get("telefone", "")),
            ("Pasta", str(self.pasta)),
        ):
            f.addRow(rot + ":", CampoCopiavel(val))
        v.addWidget(g)

        for i, x in enumerate(p.get("passageiros", []), start=1):
            g = QGroupBox(f"Passageiro {i}" if p.get("tipo") != "hospedagem" else f"Hóspede {i}")
            f = _form(g)
            f.addRow("Nome:", CampoCopiavel(x.get("nome", "")))
            f.addRow("CPF:", self._campo_cpf(x.get("cpf", "")))
            f.addRow("E-mail:", CampoCopiavel(x.get("email", "")))
            f.addRow("Telefone:", CampoCopiavel(x.get("telefone", "")))
            f.addRow("Documento:", CampoCopiavel(x.get("documento_arquivo", "")))
            v.addWidget(g)

        if p.get("trechos"):
            g = QGroupBox("Trechos")
            f = _form(g)
            for t in sorted(p["trechos"], key=lambda t: t.get("ordem") or 0):
                rot = "Volta" if t.get("sentido") == "volta" else "Ida"
                texto = (f"{t.get('data', '')} {t.get('hora_saida', '')} – {t.get('origem', '')} ({t.get('origem_codigo', '')}) → "
                         f"{t.get('destino', '')} ({t.get('destino_codigo', '')})")
                if t.get("hora_chegada"):
                    texto += f" – chegada {t['hora_chegada']}"
                if t.get("companhia"):
                    texto += f" – {t['companhia']}"
                texto += f" – {t.get('pessoas', 1)} pessoa(s)"
                if t.get("bagagem"):
                    texto += f" – {t['bagagem']}"
                f.addRow(f"{rot}:", CampoCopiavel(texto))
            v.addWidget(g)

        hosp = p.get("hospedagem")
        if hosp:
            g = QGroupBox("Hospedagem")
            f = _form(g)
            for rot, chave in (("Cidade", "cidade"), ("Hotel", "hotel"), ("Check-in", "checkin"),
                               ("Check-out", "checkout"), ("Hóspedes", "hospedes"), ("Quarto", "quarto")):
                f.addRow(rot + ":", CampoCopiavel(str(hosp.get(chave, "") or "")))
            v.addWidget(g)

        itens = p.get("itens_conveniar") or []
        if itens:
            g = QGroupBox("Itens do Conveniar")
            f = _form(g)
            for it in itens:
                f.addRow(f"{it.get('produto', '')}:", CampoCopiavel(
                    f"{it.get('quantidade', '')} × {formatar_moeda(it.get('valor_unit'))} = {formatar_moeda(it.get('valor_total'))}"))
                f.addRow("Descrição:", CampoCopiavel(it.get("descricao", "")))
            v.addWidget(g)
        v.addStretch(1)
        return w

    def _campo_cpf(self, cpf: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(mascarar_cpf(cpf))
        edit.setReadOnly(True)
        mostrar = QPushButton("Mostrar")
        mostrar.setCheckable(True)

        def alternar(on):
            edit.setText(formatar_cpf(cpf) if on else mascarar_cpf(cpf))
            mostrar.setText("Ocultar" if on else "Mostrar")

        mostrar.toggled.connect(alternar)
        h.addWidget(edit, 1)
        h.addWidget(mostrar)
        h.addWidget(BotaoCopiar(lambda: formatar_cpf(cpf), w, "Copiar CPF completo"))
        return w

    # ============================================================ aba Grupo e acessos
    def _aba_grupo(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        g = self.pedido.get("grupo") or {}
        h = QHBoxLayout()
        texto = f"<b>Grupo do pedido: G{g.get('numero', '?')}</b>"
        if g.get("manual"):
            texto += f" — escolhido manualmente. Justificativa: {g.get('justificativa', '')}"
        h.addWidget(QLabel(texto))
        h.addStretch(1)
        b = QPushButton("Trocar grupo…")
        b.clicked.connect(self.trocar_grupo)
        h.addWidget(b)
        v.addLayout(h)
        empresas = self.ctx.empresas_do_grupo(self.grupo) if self.grupo else []
        if not empresas:
            v.addWidget(QLabel("Nenhuma empresa ativa neste grupo. Verifique Configurações → Empresas e grupos."))
        grade = QGridLayout()
        for i, e in enumerate(empresas):
            grade.addWidget(self._cartao_empresa(e), i // 2, i % 2)
        v.addLayout(grade)
        v.addStretch(1)
        return w

    def _cartao_empresa(self, e: dict) -> QGroupBox:
        cartao = QGroupBox(e["nome"])
        f = _form(cartao)
        link = e.get("link_portal", "")
        h = QHBoxLayout()
        portal = QPushButton("Abrir portal")
        portal.setEnabled(bool(link))
        portal.clicked.connect(lambda: abrir_url(link))
        h.addWidget(portal)
        login = self.ctx.login(e["id"])
        bl = QPushButton("Copiar login")
        bl.setEnabled(bool(login))
        bl.clicked.connect(lambda: copiar_texto(login, bl, "Login copiado"))
        h.addWidget(bl)
        bs = QPushButton("Copiar senha")
        bs.setEnabled(bool(login))
        bs.clicked.connect(lambda: self._copiar_senha(e["id"], login, bs))
        h.addWidget(bs)
        h.addStretch(1)
        f.addRow(h)
        if not login:
            aviso = QLabel("Cadastre seu login e senha em Configurações → Meus acessos.")
            aviso.setStyleSheet("color:#9a6700;")
            f.addRow(aviso)
        else:
            f.addRow("Login:", CampoCopiavel(login))
        f.addRow("Portal:", CampoCopiavel(link))
        for rot, chave in (("E-mail cotação", "email_cotacao"), ("E-mail emissão", "email_emissao"),
                           ("Contato", "contato"), ("Observação", "observacao")):
            if e.get(chave):
                f.addRow(rot + ":", CampoCopiavel(e[chave]))
        return cartao

    def _copiar_senha(self, empresa_id: str, login: str, botao: QWidget):
        senha = obter_senha(empresa_id, login)
        if not senha:
            QMessageBox.information(self, "Senha", "Senha não cadastrada. Use Configurações → Meus acessos.")
            return
        _limpador.copiar(senha)
        mostrar_aviso(botao, "Senha copiada — será apagada em 30 s", 2500)

    @protegido
    def trocar_grupo(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Trocar grupo")
        f = QFormLayout(dlg)
        combo = QComboBox()
        for n in GRUPOS:
            if n != self.grupo:
                combo.addItem(f"G{n}", n)
        just = QLineEdit()
        f.addRow("Novo grupo:", combo)
        f.addRow("Justificativa:", just)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if not dlg.exec():
            return
        p = self.copia()
        trocar_grupo(p, combo.currentData(), just.text(), self.ctx.analista)
        h = p["historico"].pop()
        self.salvar(p, h["acao"], h["detalhe"])

    # ============================================================ aba Cotações
    def _empresas_cotacao(self) -> list[dict]:
        lista = list(self.ctx.empresas_do_grupo(self.grupo)) if self.grupo else []
        ids = {e["id"] for e in lista}
        todas = {e["id"]: e for e in self.ctx.empresas()}
        for c in self.pedido.get("cotacoes", []):
            if c["empresa_id"] not in ids:
                lista.append(todas.get(c["empresa_id"], {"id": c["empresa_id"], "nome": c.get("empresa", c["empresa_id"])}))
                ids.add(c["empresa_id"])
        return lista

    def _aba_cotacoes(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(
            f"Empresas ativas do grupo G{self.grupo}. Registre pelo menos {cot.MINIMO_COTACOES} valores. "
            "Anexe a proposta pelo botão ou arrastando o arquivo até ele."))
        self.empresas_cot = self._empresas_cotacao()
        existentes = {c["empresa_id"]: c for c in self.pedido.get("cotacoes", [])}
        tab = QTableWidget(len(self.empresas_cot), 6)
        self.tab_cot = tab
        tab.setHorizontalHeaderLabels(["Empresa", "Forma", "Valor total (R$)", "Proposta", "Arquivo", "Observação"])
        tab.verticalHeader().setVisible(False)
        tab.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        tab.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        tab.setColumnWidth(0, 170)
        tab.setColumnWidth(2, 130)
        tab.setColumnWidth(3, 150)
        tipo = self.pedido.get("tipo")
        for r, e in enumerate(self.empresas_cot):
            c = existentes.get(e["id"], {})
            item = QTableWidgetItem(e["nome"])
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if e.get("tipos") and tipo in TIPOS and tipo != "outro" and tipo not in e["tipos"]:
                item.setToolTip("Esta empresa não está marcada para este tipo de pedido")
            tab.setItem(r, 0, item)
            forma = QComboBox()
            forma.addItem("Portal", "portal")
            forma.addItem("E-mail", "email")
            padrao = "email" if (tipo in ("terrestre", "hospedagem") and e.get("email_cotacao")) else "portal"
            forma.setCurrentIndex(forma.findData(c.get("forma", padrao)))
            tab.setCellWidget(r, 1, forma)
            tab.setItem(r, 2, QTableWidgetItem(formatar_moeda(c.get("valor"), simbolo=False)))
            botao = BotaoArquivo("Anexar proposta", "Propostas (*.pdf *.png *.jpg *.jpeg);;Todos (*.*)")
            botao.arquivo.connect(lambda arq, linha=r: self.anexar_proposta(linha, arq))
            tab.setCellWidget(r, 3, botao)
            arq = QTableWidgetItem(c.get("arquivo", ""))
            arq.setFlags(arq.flags() & ~Qt.ItemIsEditable)
            tab.setItem(r, 4, arq)
            tab.setItem(r, 5, QTableWidgetItem(c.get("obs", "")))
        tab.itemChanged.connect(lambda _: self._destacar_menor())
        v.addWidget(tab, 1)

        self.rotulo_cot = QLabel("")
        v.addWidget(self.rotulo_cot)
        venc = self.pedido.get("vencedora")
        if venc:
            txt = f"<b>Vencedora:</b> {venc.get('empresa', '')} — {formatar_moeda(venc.get('valor'))}"
            if venc.get("justificativa"):
                txt += f" — Justificativa: {venc['justificativa']}"
            v.addWidget(QLabel(txt))
        h = QHBoxLayout()
        salvar = QPushButton("Salvar cotações")
        salvar.clicked.connect(self.salvar_cotacoes)
        definir = QPushButton("Definir vencedora")
        definir.setObjectName("primario")
        definir.clicked.connect(self.definir_vencedora)
        self.botao_definir = definir
        pre = BotaoArquivo("Anexar pré-reserva da vencedora", "PDF (*.pdf);;Todos (*.*)")
        pre.setEnabled(bool(venc))
        pre.arquivo.connect(lambda arq: self.anexar_fixo("pre_reserva", arq))
        for b in (salvar, definir, pre):
            h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        self._destacar_menor()
        return w

    def _ler_tabela_cotacoes(self) -> list[dict]:
        existentes = {c["empresa_id"]: c for c in self.pedido.get("cotacoes", [])}
        saida = []
        for r, e in enumerate(self.empresas_cot):
            texto = self.tab_cot.item(r, 2).text().strip() if self.tab_cot.item(r, 2) else ""
            try:
                valor = parse_moeda(texto)
            except ValueError:
                raise ValueError(f"Valor inválido para {e['nome']}: {texto!r}. Use o formato 1.539,02.")
            obs = self.tab_cot.item(r, 5).text().strip() if self.tab_cot.item(r, 5) else ""
            anterior = existentes.get(e["id"], {})
            if valor is None and not anterior.get("arquivo") and not obs:
                continue
            saida.append({
                "empresa_id": e["id"], "empresa": e["nome"], "forma": self.tab_cot.cellWidget(r, 1).currentData(),
                "valor": valor, "arquivo": anterior.get("arquivo", ""),
                "registrado_em": anterior.get("registrado_em") if anterior.get("valor") == valor else agora_iso(),
                "obs": obs,
            })
        return saida

    def _destacar_menor(self):
        if not hasattr(self, "tab_cot"):
            return
        tab = self.tab_cot
        valores = []
        for r in range(tab.rowCount()):
            try:
                valores.append(parse_moeda(tab.item(r, 2).text()) if tab.item(r, 2) else None)
            except ValueError:
                valores.append(None)
        validos = [x for x in valores if x]
        minimo = min(validos) if validos else None
        tab.blockSignals(True)
        for r, val in enumerate(valores):
            cor = QColor(VERDE) if (minimo is not None and val == minimo) else QColor("#ffffff")
            for c in (0, 2, 4, 5):
                if tab.item(r, c):
                    tab.item(r, c).setBackground(cor)
        tab.blockSignals(False)
        empate = validos.count(minimo) > 1 if minimo is not None else False
        txt = f"{len(validos)} valor(es) registrado(s) de {tab.rowCount()} empresa(s)."
        if minimo is not None:
            txt += f" Menor valor: {formatar_moeda(minimo)}"
            txt += " — EMPATE: registre as ligações para desempatar." if empate else "."
        if len(validos) < cot.MINIMO_COTACOES:
            txt += f" Faltam {cot.MINIMO_COTACOES - len(validos)} para liberar \"Definir vencedora\"."
        self.rotulo_cot.setText(txt)
        if hasattr(self, "botao_definir"):
            self.botao_definir.setEnabled(len(validos) >= cot.MINIMO_COTACOES)

    @protegido
    def salvar_cotacoes(self):
        p = self.copia()
        p["cotacoes"] = self._ler_tabela_cotacoes()
        self.salvar(p, "cotacoes_registradas", f"{len(cot.com_valor(p['cotacoes']))} valor(es)")

    @protegido
    def anexar_proposta(self, linha: int, arquivo: str):
        e = self.empresas_cot[linha]
        p = self.copia()
        p["cotacoes"] = self._ler_tabela_cotacoes()
        c = next((x for x in p["cotacoes"] if x["empresa_id"] == e["id"]), None)
        if c is None or not c.get("valor"):
            raise ValueError(f"Informe primeiro o valor total da {e['nome']} (ele entra no nome do arquivo).")
        destino = self.pasta / pastas.PASTA_COTACAO
        nome = pastas.nome_proposta(self.grupo or 0, e["nome"], c["valor"], Path(arquivo).suffix or ".pdf")
        alvo = pastas.copiar_sem_sobrescrever(arquivo, destino, nome)
        c["arquivo"] = f"{pastas.PASTA_COTACAO}/{alvo.name}"
        p.setdefault("arquivos", []).append({"tipo": "proposta", "nome": c["arquivo"]})
        self.salvar(p, "proposta_anexada", c["arquivo"])

    @protegido
    def definir_vencedora(self):
        p = self.copia()
        p["cotacoes"] = self._ler_tabela_cotacoes()
        if not cot.pode_definir_vencedora(p["cotacoes"]):
            raise ValueError(f"Registre pelo menos {cot.MINIMO_COTACOES} valores e salve as cotações.")
        dlg = DialogoVencedora(p["cotacoes"], self)
        if not dlg.exec():
            return
        cot.definir_vencedora(p, dlg.empresa_id(), dlg.justificativa(), dlg.desempate(), self.ctx.analista)
        h = p["historico"].pop()
        self.salvar(p, h["acao"], h["detalhe"])

    # ============================================================ aba E-mails
    def _aba_emails(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        topo = QHBoxLayout()
        self.email_tipo = QComboBox()
        self.email_tipo.addItem("Cotação à empresa", "cotacao")
        self.email_tipo.addItem("Aprovação (solicitante e coordenador)", "aprovacao")
        self.email_empresa = QComboBox()
        for e in self._empresas_cotacao():
            self.email_empresa.addItem(e["nome"], e)
        topo.addWidget(QLabel("E-mail:"))
        topo.addWidget(self.email_tipo)
        topo.addWidget(self.email_empresa)
        topo.addStretch(1)
        v.addLayout(topo)

        self.box_aprov = QGroupBox("Aprovação")
        f = QGridLayout(self.box_aprov)
        ap = self.pedido.get("aprovacao") or {}
        self.ap_sol = QLineEdit(self.pedido.get("solicitante", {}).get("email", ""))
        self.ap_coord = QLineEdit(self.pedido.get("projeto", {}).get("coordenador_email", "")
                                  or self.ctx.repo.ultimo_email_coordenador(self.pedido["projeto"].get("numero", "")))
        self.ap_coord.setPlaceholderText("e-mail do coordenador")
        self.ap_prazo = QDateEdit()
        self.ap_prazo.setCalendarPopup(True)
        self.ap_prazo.setDisplayFormat("dd/MM/yyyy")
        prazo = parse_data(ap.get("prazo_data")) or proximo_dia_util(agora().date())
        self.ap_prazo.setDate(QDate(prazo.year, prazo.month, prazo.day))
        self.ap_hora = QLineEdit(ap.get("prazo_hora") or self.ctx.config.get("hora_prazo", "17:00"))
        self.ap_hora.setMaximumWidth(70)
        f.addWidget(QLabel("E-mail do solicitante:"), 0, 0)
        f.addWidget(self.ap_sol, 0, 1)
        f.addWidget(QLabel("E-mail do coordenador:"), 0, 2)
        f.addWidget(self.ap_coord, 0, 3)
        f.addWidget(QLabel("Prazo:"), 1, 0)
        f.addWidget(self.ap_prazo, 1, 1)
        f.addWidget(QLabel("Hora:"), 1, 2)
        f.addWidget(self.ap_hora, 1, 3)
        v.addWidget(self.box_aprov)

        gerar = QPushButton("Gerar e-mail")
        gerar.setObjectName("primario")
        gerar.clicked.connect(self.gerar_email)
        v.addWidget(gerar, alignment=Qt.AlignLeft)

        g = QGroupBox("Mensagem")
        f = _form(g)
        self.em_para, self.em_cc, self.em_assunto = QLineEdit(), QLineEdit(), QLineEdit()
        self.em_corpo = QPlainTextEdit()
        self.em_corpo.setMinimumHeight(240)
        f.addRow("Para:", self.em_para)
        f.addRow("CC:", self.em_cc)
        f.addRow("Assunto:", self.em_assunto)
        f.addRow("Corpo:", self.em_corpo)
        v.addWidget(g, 1)

        h = QHBoxLayout()
        for rot, fn in (("Copiar assunto", lambda b: copiar_texto(self.em_assunto.text(), b)),
                        ("Copiar corpo", lambda b: copiar_texto(self.em_corpo.toPlainText(), b)),
                        ("Copiar destinatários", lambda b: copiar_texto(self._destinatarios_texto(), b)),
                        ("Abrir no Gmail", lambda b: self.abrir_gmail(b)),
                        ("Abrir pasta do pedido", lambda b: self.abrir_pasta())):
            b = QPushButton(rot)
            b.clicked.connect(lambda _=False, f=fn, b=b: f(b))
            h.addWidget(b)
        h.addStretch(1)
        v.addLayout(h)
        self.email_tipo.currentIndexChanged.connect(self._tipo_email_mudou)
        self._tipo_email_mudou()
        return w

    def _tipo_email_mudou(self):
        aprov = self.email_tipo.currentData() == "aprovacao"
        self.email_empresa.setVisible(not aprov)
        self.box_aprov.setVisible(aprov)

    def _destinatarios_texto(self) -> str:
        para = emails.separar_emails(self.em_para.text())
        cc = emails.separar_emails(self.em_cc.text())
        return "; ".join(para + cc)

    @protegido
    def gerar_email(self):
        repo = self.ctx.repo
        cc = self.ctx.config.get("cc_padrao", "")
        assunto = emails.montar_assunto(self.pedido, repo.ler_modelo("assunto.txt"))
        if self.email_tipo.currentData() == "cotacao":
            e = self.email_empresa.currentData() or {}
            corpo = emails.corpo_cotacao(self.pedido, repo.ler_modelo("cotacao_empresa.txt"), self.ctx.assinatura,
                                         e.get("nome", ""))
            self._preencher_email(e.get("email_cotacao", ""), cc, assunto, corpo)
            if not e.get("email_cotacao"):
                QMessageBox.information(self, "E-mail da empresa",
                                        f"A {e.get('nome', 'empresa')} não tem e-mail de cotação cadastrado.")
            p = self.copia()
            self.salvar_sem_recarregar(p, "email_cotacao_gerado", e.get("nome", ""))
            return

        prazo = self.ap_prazo.date().toString("dd/MM/yyyy")
        hora = self.ap_hora.text().strip() or "17:00"
        p = self.copia()
        p["solicitante"]["email"] = self.ap_sol.text().strip()
        p["projeto"]["coordenador_email"] = self.ap_coord.text().strip()
        para = emails.destinatarios_aprovacao(p)
        if len(para) < 2:
            QMessageBox.information(self, "Destinatários", "Confira: o e-mail deve ir para o solicitante e para o coordenador.")
        corpo = emails.corpo_aprovacao(p, repo.ler_modelo("aprovacao.txt"), prazo, hora,
                                       len(self.ctx.empresas(somente_ativas=True)), self.ctx.assinatura)
        anterior = p.get("aprovacao") or {}
        p["aprovacao"] = {"para": para, "cc": emails.separar_emails(cc), "prazo_data": prazo, "prazo_hora": hora,
                          "gerado_em": agora_iso(), "resultado": anterior.get("resultado"),
                          "respondido_em": anterior.get("respondido_em")}
        mudar = False
        if p.get("status") == "em_cotacao":
            r = QMessageBox.question(self, "Status", "Mudar o status para \"Aguardando aprovação\"?")
            mudar = r == QMessageBox.Yes
        if mudar:
            p["status"] = "aguardando_aprovacao"
        self.salvar_sem_recarregar(p, "email_aprovacao_gerado", f"prazo {prazo} {hora}" + (" — status: aguardando aprovação" if mudar else ""))
        self._preencher_email(", ".join(para), cc, assunto, corpo)

    def salvar_sem_recarregar(self, p: dict, acao: str, detalhe: str) -> None:
        """Grava mantendo a aba E-mails como está (o texto gerado continua na tela)."""
        try:
            self.ctx.repo.salvar(p, self.ctx.analista, acao, detalhe, esperado=self._esperado)
        except ConflitoEdicao as exc:
            QMessageBox.warning(self, "Pedido alterado", str(exc))
            self.recarregar()
            return
        self.pedido = p
        self._esperado = p["atualizado_em"]
        novo = self._cabecalho()
        self.conteudo.layout().replaceWidget(self.cab, novo)
        self.cab.deleteLater()
        self.cab = novo
        self.alterado.emit()

    def _preencher_email(self, para: str, cc: str, assunto: str, corpo: str):
        self.em_para.setText(para)
        self.em_cc.setText(cc)
        self.em_assunto.setText(assunto)
        self.em_corpo.setPlainText(corpo)

    def abrir_gmail(self, botao: QWidget):
        conta = self.ctx.config.get("gmail_authuser") or self.ctx.config.get("analista_email", "")
        url, com_corpo = emails.url_gmail(conta, emails.separar_emails(self.em_para.text()),
                                          emails.separar_emails(self.em_cc.text()), self.em_assunto.text(),
                                          self.em_corpo.toPlainText())
        if not com_corpo:
            copiar_texto(self.em_corpo.toPlainText(), botao, "Corpo copiado, cole no e-mail")
            QMessageBox.information(self, "Gmail", "O texto é longo demais para o link.\nCorpo copiado, cole no e-mail.")
        abrir_url(url)

    # ============================================================ aba Arquivos
    def _aba_arquivos(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(f"Pasta: {self.pasta}"))
        self.lista_arq = QListWidget()
        self.lista_arq.itemDoubleClicked.connect(
            lambda it: QDesktopServices.openUrl(QUrl.fromLocalFile(it.data(Qt.UserRole))))
        v.addWidget(self.lista_arq, 1)
        self._listar_arquivos()
        h = QHBoxLayout()
        for rot, tipo in (("Anexar pré-reserva", "pre_reserva"), ("Anexar reserva", "reserva"), ("Anexar outro", "outro")):
            b = BotaoArquivo(rot, "Todos os arquivos (*.*)")
            b.arquivo.connect(lambda arq, t=tipo: self.anexar_fixo(t, arq))
            h.addWidget(b)
        atualizar = QPushButton("Atualizar lista")
        atualizar.clicked.connect(self._listar_arquivos)
        abrir = QPushButton("Abrir pasta")
        abrir.clicked.connect(self.abrir_pasta)
        h.addWidget(atualizar)
        h.addWidget(abrir)
        h.addStretch(1)
        v.addLayout(h)
        v.addWidget(QLabel("Dica: arraste o arquivo até o botão. Duplo clique abre o arquivo."))
        return w

    def _listar_arquivos(self):
        self.lista_arq.clear()
        arquivos = pastas.listar_arquivos(self.pasta)
        if not self.pasta.exists():
            self.lista_arq.addItem("(pasta do pedido não encontrada — Drive indisponível?)")
        for a in arquivos:
            it = QListWidgetItem(str(a.relative_to(self.pasta)))
            it.setData(Qt.UserRole, str(a))
            self.lista_arq.addItem(it)

    @protegido
    def anexar_fixo(self, tipo: str, arquivo: str):
        ext = Path(arquivo).suffix or ".pdf"
        if tipo == "reserva":
            opcoes = ["Reserva única (5. Reserva)", "Reserva Ida (5. Reserva Ida)", "Reserva Volta (5.1 Reserva Volta)"]
            escolha, ok = QInputDialog.getItem(self, "Reserva", "Qual reserva?", opcoes, 0, False)
            if not ok:
                return
            tipo = ["reserva", "reserva_ida", "reserva_volta"][opcoes.index(escolha)]
        if tipo == "outro":
            nome, ok = QInputDialog.getText(self, "Nome do arquivo", "Nome do arquivo:", text=Path(arquivo).stem)
            if not ok or not nome.strip():
                return
            nome = nome.strip()
            if not Path(nome).suffix:
                nome += ext
        else:
            nome = pastas.nome_fixo(tipo, ext)
        alvo = pastas.copiar_sem_sobrescrever(arquivo, self.pasta, nome)
        p = self.copia()
        p.setdefault("arquivos", []).append({"tipo": tipo, "nome": alvo.name})
        self.salvar(p, "arquivo_anexado", alvo.name)

    # ============================================================ aba Histórico
    def _aba_historico(self) -> QWidget:
        hist = list(reversed(self.pedido.get("historico", [])))
        tab = QTableWidget(len(hist), 4)
        tab.setHorizontalHeaderLabels(["Quando", "Quem", "O quê", "Detalhe"])
        tab.verticalHeader().setVisible(False)
        tab.setEditTriggers(QTableWidget.NoEditTriggers)
        tab.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        for r, h in enumerate(hist):
            quando = h.get("quando", "")[:19].replace("T", " ")
            if len(quando) >= 10:
                quando = f"{quando[8:10]}/{quando[5:7]}/{quando[0:4]}{quando[10:16]}"
            for c, val in enumerate((quando, h.get("quem", ""), ROTULOS_ACAO.get(h.get("acao"), h.get("acao", "")),
                                     h.get("detalhe", ""))):
                tab.setItem(r, c, QTableWidgetItem(val))
        tab.resizeColumnsToContents()
        tab.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        return tab


class DialogoVencedora(QDialog):
    """Escolha da vencedora. Em empate, exige a ligação para cada empresa empatada."""

    def __init__(self, cotacoes: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Definir vencedora")
        self.setMinimumWidth(640)
        self.empatadas = cot.menores(cotacoes) if cot.ha_empate(cotacoes) else []
        v = QVBoxLayout(self)
        self.combo = QComboBox()
        candidatas = self.empatadas or sorted(cot.com_valor(cotacoes), key=lambda c: c["valor"])
        for c in candidatas:
            self.combo.addItem(f"{c['empresa']} — {formatar_moeda(c['valor'])}", c["empresa_id"])
        self.linhas: dict[str, tuple[QLineEdit, QLineEdit, QLineEdit]] = {}
        if self.empatadas:
            aviso = QLabel(f"<b>Empate no menor valor ({formatar_moeda(self.empatadas[0]['valor'])}).</b> "
                           "Registre a ligação para cada empresa empatada antes de escolher.")
            aviso.setWordWrap(True)
            v.addWidget(aviso)
            grade = QGridLayout()
            for i, rot in enumerate(("Empresa", "Data e hora", "Pessoa contatada", "Resultado")):
                grade.addWidget(QLabel(f"<b>{rot}</b>"), 0, i)
            for r, c in enumerate(self.empatadas, start=1):
                dh = QLineEdit(agora().strftime("%d/%m/%Y %H:%M"))
                pessoa, resultado = QLineEdit(), QLineEdit()
                grade.addWidget(QLabel(c["empresa"]), r, 0)
                grade.addWidget(dh, r, 1)
                grade.addWidget(pessoa, r, 2)
                grade.addWidget(resultado, r, 3)
                self.linhas[c["empresa_id"]] = (dh, pessoa, resultado)
            v.addLayout(grade)
        f = QFormLayout()
        f.addRow("Vencedora:", self.combo)
        self.just = QLineEdit()
        self.just.setPlaceholderText("Obrigatória em empate ou se não for o menor valor")
        f.addRow("Justificativa:", self.just)
        v.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self._cotacoes = cotacoes

    def _ok(self):
        teste = {"cotacoes": copy.deepcopy(self._cotacoes)}
        try:
            cot.definir_vencedora(teste, self.empresa_id(), self.justificativa(), self.desempate())
        except ValueError as exc:
            QMessageBox.warning(self, "Vencedora", str(exc))
            return
        self.accept()

    def empresa_id(self) -> str:
        return self.combo.currentData()

    def justificativa(self) -> str:
        return self.just.text().strip()

    def desempate(self) -> dict | None:
        if not self.empatadas:
            return None
        return {"ligacoes": [
            {"empresa_id": eid, "data_hora": dh.text().strip(), "pessoa": p.text().strip(), "resultado": r.text().strip()}
            for eid, (dh, p, r) in self.linhas.items()
        ]}
