"""Configurações: Geral, Meus dados, Meus acessos, Empresas e grupos, Siglas e Modelos de e-mail."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import dir_recursos
from core.contexto import Contexto
from core.credenciais import apagar_senha, obter_senha, salvar_senha
from core.emails import CAMPOS_DISPONIVEIS
from core.formatos import hora_hhmm, slug
from ui.widgets import abrir_pasta, abrir_url, mostrar_aviso, protegido, titulo

log = logging.getLogger(__name__)

MODELOS = [("assunto.txt", "Assunto (todos)"), ("cotacao_empresa.txt", "Pedido de cotação à empresa"),
           ("aprovacao.txt", "Pedido de aprovação")]
TIPOS_EMPRESA = ("aerea", "terrestre", "hospedagem")


def _campo_pasta(edit: QLineEdit, parent: QWidget) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.addWidget(edit, 1)
    b = QPushButton("Escolher…")

    def escolher():
        d = QFileDialog.getExistingDirectory(parent, "Pasta raiz do credenciamento", edit.text())
        if d:
            edit.setText(str(Path(d)))

    b.clicked.connect(escolher)
    h.addWidget(b)
    return w


class TelaConfiguracoes(QWidget):
    configAlterada = Signal()

    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.addWidget(titulo("Configurações"))
        self.alerta = QLabel("")
        self.alerta.setObjectName("alerta")
        self.alerta.setWordWrap(True)
        self.alerta.setVisible(False)
        v.addWidget(self.alerta)
        self.abas = QTabWidget()
        v.addWidget(self.abas, 1)
        self.abas.addTab(self._aba_geral(), "Geral")
        self.abas.addTab(self._aba_meus_dados(), "Meus dados")
        self.acessos = QWidget()
        QVBoxLayout(self.acessos)
        self.abas.addTab(self.acessos, "Meus acessos")
        self.empresas_w = QWidget()
        QVBoxLayout(self.empresas_w)
        self.abas.addTab(self.empresas_w, "Empresas e grupos")
        self.siglas_w = QWidget()
        QVBoxLayout(self.siglas_w)
        self.abas.addTab(self.siglas_w, "Siglas de cidades")
        self.abas.addTab(self._aba_modelos(), "Modelos de e-mail")

    def showEvent(self, e):
        super().showEvent(e)
        self.atualizar()

    def atualizar(self):
        self._verificar_duplicados()
        self._montar_acessos()
        self._montar_empresas()
        self._montar_siglas()
        self._carregar_modelo()

    def _verificar_duplicados(self):
        try:
            dup = self.ctx.repo.arquivos_duplicados()
        except Exception:
            dup = []
        if dup:
            nomes = "<br>".join(f"• {p.parent.name}\\{p.name}" for p in dup)
            self.alerta.setText(
                "<b>Arquivos duplicados criados pelo Google Drive (conflito de sincronização):</b><br>"
                f"{nomes}<br>Compare com o arquivo original, mantenha o correto e apague a cópia "
                f"na pasta <i>{self.ctx.repo.pasta_sistema}</i>. Depois clique em Atualizar na lista de pedidos.")
            self.alerta.setVisible(True)
        else:
            self.alerta.setVisible(False)

    @staticmethod
    def _limpar(w: QWidget):
        lay = w.layout()
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    x = sub.takeAt(0)
                    if x.widget():
                        x.widget().deleteLater()

    # ============================================================ Geral
    def _aba_geral(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        c = self.ctx.config
        self.g_raiz = QLineEdit(c["pasta_raiz"])
        self.g_modelo = QLineEdit(c["modelo_pasta"])
        self.g_cc = QLineEdit(c["cc_padrao"])
        self.g_hora = QLineEdit(c["hora_prazo"])
        self.g_gmail = QLineEdit(c["gmail_authuser"])
        self.g_gmail.setPlaceholderText("conta@fapec.org (usada no link do Gmail)")
        self.g_grupo = QComboBox()
        for n in (1, 2, 3):
            self.g_grupo.addItem(f"G{n}", n)
        self.g_grupo.setCurrentIndex(self.g_grupo.findData(c.get("ultimo_grupo", 3)))
        f.addRow("Pasta raiz do credenciamento:", _campo_pasta(self.g_raiz, self))
        f.addRow("Modelo do nome da pasta:", self.g_modelo)
        f.addRow("", QLabel("Campos: {numero}, {ano}, {resumo}"))
        f.addRow("CC padrão:", self.g_cc)
        f.addRow("Hora do prazo de aprovação:", self.g_hora)
        f.addRow("Conta do Gmail (authuser):", self.g_gmail)
        f.addRow("Último grupo usado (só vale sem pedidos):", self.g_grupo)
        f.addRow("", QLabel("A assinatura dos e-mails fica em \"Meus dados\"."))
        b = QPushButton("Salvar")
        b.setObjectName("primario")
        b.setMaximumWidth(160)
        b.clicked.connect(self.salvar_geral)
        f.addRow("", b)
        return w

    @protegido
    def salvar_geral(self):
        c = self.ctx.config
        hora = hora_hhmm(self.g_hora.text())
        if not hora or ":" not in hora:
            raise ValueError("Hora do prazo inválida. Use HH:MM (ex.: 17:00).")
        if "{numero}" not in self.g_modelo.text():
            raise ValueError("O modelo do nome da pasta precisa conter {numero}.")
        raiz_mudou = self.g_raiz.text().strip() != c["pasta_raiz"]
        c.update({
            "pasta_raiz": self.g_raiz.text().strip(), "modelo_pasta": self.g_modelo.text().strip(),
            "cc_padrao": self.g_cc.text().strip(), "hora_prazo": hora, "gmail_authuser": self.g_gmail.text().strip(),
            "ultimo_grupo": self.g_grupo.currentData(),
        })
        self.ctx.salvar_config()
        if raiz_mudou:
            self.ctx.abrir_repositorio()
            if self.ctx.repo.drive_disponivel():
                self.ctx.repo.garantir_estrutura()
                self.ctx.repo.reconstruir_indice()
            else:
                QMessageBox.warning(self, "Pasta raiz", "A pasta raiz informada não está acessível agora.")
        mostrar_aviso(self.sender(), "Configurações salvas")
        self.configAlterada.emit()
        self.atualizar()

    # ============================================================ Meus dados
    def _aba_meus_dados(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        c = self.ctx.config
        self.d_nome = QLineEdit(c["analista_nome"])
        self.d_email = QLineEdit(c["analista_email"])
        self.d_assinatura = QPlainTextEdit(c["assinatura"])
        self.d_assinatura.setMaximumHeight(120)
        f.addRow("Nome do analista:", self.d_nome)
        f.addRow("E-mail:", self.d_email)
        f.addRow("Assinatura dos e-mails:", self.d_assinatura)
        b = QPushButton("Salvar")
        b.setObjectName("primario")
        b.setMaximumWidth(160)
        b.clicked.connect(self.salvar_meus_dados)
        f.addRow("", b)
        return w

    @protegido
    def salvar_meus_dados(self):
        if not self.d_nome.text().strip():
            raise ValueError("Informe o seu nome (ele aparece no histórico dos pedidos).")
        self.ctx.config.update({"analista_nome": self.d_nome.text().strip(), "analista_email": self.d_email.text().strip(),
                                "assinatura": self.d_assinatura.toPlainText().strip()})
        self.ctx.salvar_config()
        mostrar_aviso(self.sender(), "Dados salvos")
        self.configAlterada.emit()

    # ============================================================ Meus acessos
    def _montar_acessos(self):
        self._limpar(self.acessos)
        lay = self.acessos.layout()
        lay.addWidget(QLabel("O login fica na sua configuração local. A senha vai SOMENTE para o Gerenciador de "
                             "Credenciais do Windows. Deixe a senha em branco para mantê-la."))
        try:
            empresas = self.ctx.empresas(somente_ativas=True)
        except Exception:
            empresas = []
        self.tab_acessos = QTableWidget(len(empresas), 5)
        t = self.tab_acessos
        t.setHorizontalHeaderLabels(["Empresa", "Login", "Senha", "Situação", ""])
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._empresas_acesso = empresas
        for r, e in enumerate(empresas):
            item = QTableWidgetItem(f"G{e.get('grupo')} · {e['nome']}")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            t.setItem(r, 0, item)
            login = self.ctx.login(e["id"])
            t.setItem(r, 1, QTableWidgetItem(login))
            senha = QLineEdit()
            senha.setEchoMode(QLineEdit.Password)
            tem = bool(login and obter_senha(e["id"], login))
            senha.setPlaceholderText("•••••• (salva)" if tem else "digite a senha")
            t.setCellWidget(r, 2, senha)
            sit = QTableWidgetItem("Senha salva" if tem else "Sem senha")
            sit.setFlags(sit.flags() & ~Qt.ItemIsEditable)
            t.setItem(r, 3, sit)
            testar = QPushButton("Testar")
            testar.setToolTip("Abre o portal no navegador")
            testar.clicked.connect(lambda _=False, url=e.get("link_portal", ""): abrir_url(url) if url else None)
            t.setCellWidget(r, 4, testar)
        lay.addWidget(t, 1)
        b = QPushButton("Salvar acessos")
        b.setObjectName("primario")
        b.clicked.connect(self.salvar_acessos)
        lay.addWidget(b, alignment=Qt.AlignLeft)

    @protegido
    def salvar_acessos(self):
        logins = dict(self.ctx.config.get("logins") or {})
        for r, e in enumerate(self._empresas_acesso):
            login = self.tab_acessos.item(r, 1).text().strip()
            anterior = logins.get(e["id"], "")
            senha = self.tab_acessos.cellWidget(r, 2).text()
            if anterior and anterior != login:
                antiga = obter_senha(e["id"], anterior)
                apagar_senha(e["id"], anterior)
                if antiga and not senha and login:
                    senha = antiga
            if login:
                logins[e["id"]] = login
                if senha:
                    salvar_senha(e["id"], login, senha)
            else:
                logins.pop(e["id"], None)
        self.ctx.config["logins"] = logins
        self.ctx.salvar_config()
        self._montar_acessos()
        mostrar_aviso(self.tab_acessos, "Acessos salvos")

    # ============================================================ Empresas
    COLS_EMP = [("nome", "Nome"), ("grupo", "Grupo"), ("link_portal", "Link do portal"),
                ("email_cotacao", "E-mail cotação"), ("email_emissao", "E-mail emissão"), ("contato", "Contato"),
                ("observacao", "Observação"), ("tipos", "Tipos"), ("ativa", "Ativa")]

    def _montar_empresas(self):
        self._limpar(self.empresas_w)
        lay = self.empresas_w.layout()
        lay.addWidget(QLabel("Cadastro compartilhado (empresas.json no Drive). Grupo: 1, 2 ou 3. "
                             "Tipos: aerea, terrestre, hospedagem. Desmarque \"Ativa\" para desativar."))
        try:
            empresas = self.ctx.empresas()
        except Exception:
            empresas = []
        t = QTableWidget(0, len(self.COLS_EMP))
        self.tab_emp = t
        t.setHorizontalHeaderLabels([c[1] for c in self.COLS_EMP])
        t.verticalHeader().setVisible(False)
        for e in empresas:
            self._linha_empresa(e)
        t.resizeColumnsToContents()
        t.setColumnWidth(2, 260)
        lay.addWidget(t, 1)
        h = QHBoxLayout()
        inc = QPushButton("Incluir empresa")
        inc.clicked.connect(lambda: self._linha_empresa({"grupo": 1, "ativa": True, "tipos": list(TIPOS_EMPRESA)}))
        sal = QPushButton("Salvar empresas")
        sal.setObjectName("primario")
        sal.clicked.connect(self.salvar_empresas)
        h.addWidget(inc)
        h.addWidget(sal)
        h.addStretch(1)
        lay.addLayout(h)

    def _linha_empresa(self, e: dict):
        t = self.tab_emp
        r = t.rowCount()
        t.insertRow(r)
        for c, (chave, _) in enumerate(self.COLS_EMP):
            if chave == "ativa":
                item = QTableWidgetItem("")
                item.setFlags((item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
                item.setCheckState(Qt.Checked if e.get("ativa", True) else Qt.Unchecked)
            elif chave == "tipos":
                item = QTableWidgetItem(", ".join(e.get("tipos", [])))
            else:
                item = QTableWidgetItem(str(e.get(chave, "") or ""))
            if chave == "nome":
                item.setData(Qt.UserRole, e.get("id"))
            t.setItem(r, c, item)

    @protegido
    def salvar_empresas(self):
        t = self.tab_emp
        empresas, ids = [], set()
        for r in range(t.rowCount()):
            val = {chave: (t.item(r, c).text().strip() if t.item(r, c) else "") for c, (chave, _) in enumerate(self.COLS_EMP)}
            if not val["nome"]:
                continue
            try:
                grupo = int(val["grupo"])
                assert grupo in (1, 2, 3)
            except Exception:
                raise ValueError(f"Grupo inválido para {val['nome']}: use 1, 2 ou 3.")
            tipos = [x.strip() for x in val["tipos"].replace(";", ",").split(",") if x.strip()]
            invalidos = [x for x in tipos if x not in TIPOS_EMPRESA]
            if invalidos:
                raise ValueError(f"Tipo inválido para {val['nome']}: {', '.join(invalidos)}. Use aerea, terrestre, hospedagem.")
            eid = t.item(r, 0).data(Qt.UserRole) or slug(val["nome"])
            base, n = eid, 2
            while eid in ids:
                eid = f"{base}_{n}"
                n += 1
            ids.add(eid)
            empresas.append({
                "id": eid, "nome": val["nome"], "grupo": grupo, "link_portal": val["link_portal"],
                "email_cotacao": val["email_cotacao"], "email_emissao": val["email_emissao"], "contato": val["contato"],
                "observacao": val["observacao"], "tipos": tipos,
                "ativa": t.item(r, len(self.COLS_EMP) - 1).checkState() == Qt.Checked,
            })
        self.ctx.repo.salvar_empresas(empresas)
        mostrar_aviso(self.tab_emp, "Empresas salvas")
        self.atualizar()
        self.configAlterada.emit()

    # ============================================================ Siglas
    def _montar_siglas(self):
        self._limpar(self.siglas_w)
        lay = self.siglas_w.layout()
        lay.addWidget(QLabel("Tabela compartilhada (siglas_cidades.csv). A busca ignora acento e caixa."))
        siglas = self.ctx.siglas(recarregar=True)
        t = QTableWidget(len(siglas.linhas), 3)
        self.tab_siglas = t
        t.setHorizontalHeaderLabels(["Cidade", "UF", "Código"])
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for r, l in enumerate(sorted(siglas.linhas, key=lambda l: l["cidade"])):
            for c, k in enumerate(("cidade", "uf", "codigo")):
                t.setItem(r, c, QTableWidgetItem(l.get(k, "")))
        lay.addWidget(t, 1)
        h = QHBoxLayout()
        inc = QPushButton("Incluir linha")
        inc.clicked.connect(lambda: (t.insertRow(t.rowCount()), t.scrollToBottom()))
        rem = QPushButton("Remover selecionada")
        rem.clicked.connect(lambda: t.removeRow(t.currentRow()) if t.currentRow() >= 0 else None)
        sal = QPushButton("Salvar siglas")
        sal.setObjectName("primario")
        sal.clicked.connect(self.salvar_siglas)
        for b in (inc, rem, sal):
            h.addWidget(b)
        h.addStretch(1)
        lay.addLayout(h)

    @protegido
    def salvar_siglas(self):
        self.ctx.repo.exigir_drive()
        t = self.tab_siglas
        linhas = []
        for r in range(t.rowCount()):
            val = [(t.item(r, c).text().strip() if t.item(r, c) else "") for c in range(3)]
            if val[0] and val[2]:
                linhas.append({"cidade": val[0], "uf": val[1].upper(), "codigo": val[2].upper()})
        siglas = self.ctx.siglas()
        siglas.salvar(linhas)
        mostrar_aviso(t, "Siglas salvas")

    # ============================================================ Modelos
    def _aba_modelos(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        esq = QVBoxLayout()
        self.lista_modelos = QListWidget()
        for arq, rot in MODELOS:
            self.lista_modelos.addItem(rot)
        self.lista_modelos.setCurrentRow(0)
        self.lista_modelos.currentRowChanged.connect(lambda _: self._carregar_modelo())
        self.lista_modelos.setMaximumWidth(260)
        esq.addWidget(self.lista_modelos)
        campos = QLabel("<b>Campos disponíveis:</b><br>" + "<br>".join(
            f"{{{k}}} — {v}" for k, v in CAMPOS_DISPONIVEIS.items()))
        campos.setWordWrap(True)
        campos.setTextInteractionFlags(Qt.TextSelectableByMouse)
        campos.setMaximumWidth(260)
        esq.addWidget(campos)
        esq.addStretch(1)
        h.addLayout(esq)
        dir_ = QVBoxLayout()
        self.editor_modelo = QPlainTextEdit()
        dir_.addWidget(self.editor_modelo, 1)
        b = QHBoxLayout()
        salvar = QPushButton("Salvar modelo")
        salvar.setObjectName("primario")
        salvar.clicked.connect(self.salvar_modelo)
        restaurar = QPushButton("Restaurar padrão")
        restaurar.clicked.connect(self.restaurar_modelo)
        abrir = QPushButton("Abrir pasta dos modelos")
        abrir.clicked.connect(lambda: abrir_pasta(self.ctx.repo.pasta_modelos))
        for x in (salvar, restaurar, abrir):
            b.addWidget(x)
        b.addStretch(1)
        dir_.addLayout(b)
        h.addLayout(dir_, 1)
        return w

    def _modelo_atual(self) -> str:
        return MODELOS[max(self.lista_modelos.currentRow(), 0)][0]

    def _carregar_modelo(self):
        try:
            self.editor_modelo.setPlainText(self.ctx.repo.ler_modelo(self._modelo_atual()))
        except Exception:
            log.exception("Falha ao ler modelo")

    @protegido
    def salvar_modelo(self):
        self.ctx.repo.salvar_modelo(self._modelo_atual(), self.editor_modelo.toPlainText())
        mostrar_aviso(self.editor_modelo, "Modelo salvo")

    def restaurar_modelo(self):
        padrao = (dir_recursos() / "modelos_email" / self._modelo_atual()).read_text(encoding="utf-8")
        self.editor_modelo.setPlainText(padrao.rstrip("\n"))
        mostrar_aviso(self.editor_modelo, "Padrão carregado — clique em Salvar modelo para gravar")


class AssistentePrimeiroUso(QDialog):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Bem-vindo ao P.A.T.H.")
        self.setMinimumWidth(640)
        v = QVBoxLayout(self)
        v.addWidget(titulo("Primeiro uso"))
        v.addWidget(QLabel("Informe a pasta raiz do credenciamento (no Google Drive) e os seus dados.\n"
                           "Tudo pode ser alterado depois em Configurações."))
        f = QFormLayout()
        c = ctx.config
        self.raiz = QLineEdit(c["pasta_raiz"])
        self.nome = QLineEdit(c["analista_nome"])
        self.email = QLineEdit(c["analista_email"])
        self.assinatura = QPlainTextEdit(c["assinatura"])
        self.assinatura.setMaximumHeight(100)
        self.assinatura.setPlaceholderText("Nome\nAnalista de Compras\nFAPEC")
        f.addRow("Pasta raiz:", _campo_pasta(self.raiz, self))
        f.addRow("Seu nome:", self.nome)
        f.addRow("Seu e-mail:", self.email)
        f.addRow("Assinatura:", self.assinatura)
        v.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Começar")
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _ok(self):
        if not self.nome.text().strip():
            QMessageBox.warning(self, "Primeiro uso", "Informe o seu nome.")
            return
        if not Path(self.raiz.text().strip()).is_dir():
            r = QMessageBox.question(self, "Pasta raiz",
                                     "A pasta raiz não está acessível agora (o Drive está aberto?).\nContinuar mesmo assim?")
            if r != QMessageBox.Yes:
                return
        self.ctx.config.update({
            "pasta_raiz": self.raiz.text().strip(), "analista_nome": self.nome.text().strip(),
            "analista_email": self.email.text().strip(), "assinatura": self.assinatura.toPlainText().strip(),
            "primeiro_uso_concluido": True,
        })
        if not self.ctx.config.get("gmail_authuser"):
            self.ctx.config["gmail_authuser"] = self.email.text().strip()
        self.ctx.salvar_config()
        self.ctx.abrir_repositorio()
        self.accept()
