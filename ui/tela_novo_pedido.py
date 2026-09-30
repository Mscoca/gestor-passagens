"""Tela Novo pedido: lê o PDF, pré-preenche, o analista confere e cria a pasta.

O mesmo formulário é usado em "Editar dados" do Painel do pedido.
"""
from __future__ import annotations

import copy
import logging
import os
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import pastas
from core.contexto import Contexto
from core.formatos import cpf_valido, formatar_cpf, hora_hhmm, normalizar, parse_data, somente_digitos
from core.leitor_pdf import ler_pedido
from core.modelo import TIPOS, id_pedido, novo_pedido, registrar_historico
from core.rodizio import GRUPOS, atribuir_grupo, conflitos_recentes, grupo_da_vez, proximo_grupo
from ui.widgets import AMARELO, AMBAR, AreaArrastarSoltar, BotaoArquivo, destacar, protegido, titulo

log = logging.getLogger(__name__)

COLS_PASSAGEIRO = [("nome", "Nome"), ("cpf", "CPF"), ("email", "E-mail"), ("telefone", "Telefone"),
                   ("documento", "Documento"), ("anexar", "")]
COLS_TRECHO = [("sentido", "Sentido"), ("origem", "Origem"), ("destino", "Destino"), ("data", "Data"),
               ("hora_saida", "Hora saída"), ("hora_chegada", "Hora chegada"), ("pessoas", "Pessoas"),
               ("bagagem", "Bagagem"), ("companhia", "Companhia/Viação")]
FILTRO_DOCS = "Documentos (*.pdf *.jpg *.jpeg *.png);;Todos os arquivos (*.*)"


class DialogoSigla(QDialog):
    """Confirma o código de uma cidade que não está na tabela de siglas."""

    def __init__(self, cidade: str, sugestao: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Código da cidade")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"A cidade <b>{cidade}</b> não está na tabela de siglas.<br>Confirme o código:"))
        form = QFormLayout()
        self.codigo = QLineEdit(sugestao)
        self.codigo.setMaxLength(5)
        self.uf = QLineEdit()
        self.uf.setMaxLength(2)
        self.uf.setPlaceholderText("MS")
        form.addRow("Código:", self.codigo)
        form.addRow("UF:", self.uf)
        lay.addLayout(form)
        self.salvar = QCheckBox("Salvar na tabela")
        self.salvar.setChecked(True)
        lay.addWidget(self.salvar)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)


class FormularioPedido(QWidget):
    pedidoSalvo = Signal(str)

    def __init__(self, ctx: Contexto, pedido: dict | None = None, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.pedido = copy.deepcopy(pedido) if pedido else None
        self.modo_edicao = pedido is not None
        self.caminho_pdf: str | None = None
        self.itens_conveniar: list[dict] = []
        self.confirmados: dict[str, str] = {}
        self.grupo_exibido: int | None = None
        self._montar()
        if self.modo_edicao:
            self._preencher_de_pedido(self.pedido)
        else:
            self.formulario.setVisible(False)

    # ============================================================ montagem
    def _montar(self):
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.NoFrame)
        externo.addWidget(rolagem)
        corpo = QWidget()
        rolagem.setWidget(corpo)
        lay = QVBoxLayout(corpo)
        lay.setContentsMargins(20, 16, 20, 16)

        lay.addWidget(titulo("Editar dados do pedido" if self.modo_edicao else "Novo pedido"))
        if not self.modo_edicao:
            self.area_pdf = AreaArrastarSoltar(
                "Arraste o PDF do pedido aqui (Pedido de Compra do Conveniar)", "PDF (*.pdf)", altura=110
            )
            self.area_pdf.arquivos.connect(lambda l: self.carregar_pdf(l[0]))
            lay.addWidget(self.area_pdf)
            self.rotulo_pdf = QLabel("")
            self.rotulo_pdf.setStyleSheet("color:#3e4c59; font-size:9pt;")
            lay.addWidget(self.rotulo_pdf)

        self.formulario = QWidget()
        f = QVBoxLayout(self.formulario)
        f.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.formulario)
        legenda = QLabel(
            f"<span style='background:{AMARELO}; color:#1f2933'>&nbsp;Amarelo&nbsp;</span> = sugestão lida da Descrição "
            "(texto livre): confira antes de salvar."
        )
        f.addWidget(legenda)

        # ---------------- Pedido
        g = QGroupBox("Pedido")
        grid = QGridLayout(g)
        self.numero, self.ano, self.data_pedido = QLineEdit(), QLineEdit(), QLineEdit()
        self.situacao, self.finalidade = QLineEdit(), QLineEdit()
        self.tipo = QComboBox()
        for chave, rot in TIPOS.items():
            self.tipo.addItem(rot, chave)
        self.tipo.currentIndexChanged.connect(self._tipo_mudou)
        self._grade(grid, [("Nº do pedido", self.numero), ("Ano", self.ano), ("Data do pedido", self.data_pedido),
                           ("Tipo", self.tipo), ("Situação no Conveniar", self.situacao),
                           ("Finalidade", self.finalidade)])
        if self.modo_edicao:
            self.numero.setReadOnly(True)
            self.ano.setReadOnly(True)
        f.addWidget(g)

        # ---------------- Projeto / Solicitante / Coordenador
        g = QGroupBox("Projeto")
        grid = QGridLayout(g)
        self.proj_numero, self.proj_nome, self.coordenador = QLineEdit(), QLineEdit(), QLineEdit()
        self.gestor, self.conta_caixa, self.coord_email = QLineEdit(), QLineEdit(), QLineEdit()
        self.proj_numero.editingFinished.connect(self._projeto_mudou)
        self.coord_email.setPlaceholderText("Digite na primeira vez; depois o sistema lembra por projeto")
        self._grade(grid, [("Nº do projeto", self.proj_numero), ("Nome do projeto", self.proj_nome),
                           ("Coordenador", self.coordenador), ("E-mail do coordenador", self.coord_email),
                           ("Gestor", self.gestor), ("Conta caixa", self.conta_caixa)])
        f.addWidget(g)

        g = QGroupBox("Solicitante")
        grid = QGridLayout(g)
        self.sol_nome, self.sol_email, self.sol_tel = QLineEdit(), QLineEdit(), QLineEdit()
        self._grade(grid, [("Nome", self.sol_nome), ("E-mail", self.sol_email), ("Telefone", self.sol_tel)], 3)
        f.addWidget(g)

        # ---------------- Passageiros
        self.grp_passageiros = QGroupBox("Passageiros / hóspedes")
        v = QVBoxLayout(self.grp_passageiros)
        self.tab_pass = QTableWidget(0, len(COLS_PASSAGEIRO))
        self.tab_pass.setHorizontalHeaderLabels([c[1] for c in COLS_PASSAGEIRO])
        self.tab_pass.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tab_pass.verticalHeader().setVisible(False)
        self.tab_pass.setMinimumHeight(120)
        self.tab_pass.itemChanged.connect(self._item_passageiro_mudou)
        v.addWidget(self.tab_pass)
        v.addLayout(self._botoes_tabela(self.tab_pass, self.adicionar_passageiro))
        f.addWidget(self.grp_passageiros)

        # ---------------- Trechos
        self.grp_trechos = QGroupBox("Trechos")
        v = QVBoxLayout(self.grp_trechos)
        self.tab_trechos = QTableWidget(0, len(COLS_TRECHO))
        self.tab_trechos.setHorizontalHeaderLabels([c[1] for c in COLS_TRECHO])
        self.tab_trechos.verticalHeader().setVisible(False)
        self.tab_trechos.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tab_trechos.horizontalHeader().setStretchLastSection(True)
        for i, largura in enumerate((80, 140, 140, 90, 80, 90, 60, 200)):
            self.tab_trechos.setColumnWidth(i, largura)
        self.tab_trechos.setMinimumHeight(150)
        v.addWidget(self.tab_trechos)
        v.addLayout(self._botoes_tabela(self.tab_trechos, self.adicionar_trecho))
        f.addWidget(self.grp_trechos)

        # ---------------- Hospedagem
        self.grp_hosp = QGroupBox("Hospedagem")
        grid = QGridLayout(self.grp_hosp)
        self.h_cidade, self.h_hotel, self.h_checkin = QLineEdit(), QLineEdit(), QLineEdit()
        self.h_checkout, self.h_quarto = QLineEdit(), QLineEdit()
        self.h_checkin.setPlaceholderText("dd/mm/aaaa")
        self.h_checkout.setPlaceholderText("dd/mm/aaaa")
        self.h_hospedes = QSpinBox()
        self.h_hospedes.setRange(1, 99)
        self._grade(grid, [("Cidade", self.h_cidade), ("Hotel", self.h_hotel), ("Check-in", self.h_checkin),
                           ("Check-out", self.h_checkout), ("Hóspedes", self.h_hospedes), ("Quarto", self.h_quarto)])
        f.addWidget(self.grp_hosp)

        # ---------------- Pasta
        g = QGroupBox("Pasta do pedido")
        v = QVBoxLayout(g)
        h = QHBoxLayout()
        h.addWidget(QLabel("Resumo do nome da pasta:"))
        self.resumo = QLineEdit()
        self.resumo.textChanged.connect(self.atualizar_previa)
        h.addWidget(self.resumo, 1)
        b = QPushButton("Recalcular")
        b.setToolTip("Monta o resumo pelos códigos das cidades (IATA)")
        b.clicked.connect(self.recalcular_resumo)
        h.addWidget(b)
        v.addLayout(h)
        self.previa = QLabel("")
        self.previa.setWordWrap(True)
        self.previa.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.previa.setStyleSheet("color:#2f6690;")
        v.addWidget(self.previa)
        f.addWidget(g)

        # ---------------- Grupo (somente novo)
        if not self.modo_edicao:
            g = QGroupBox("Grupo de empresas (rodízio)")
            v = QVBoxLayout(g)
            self.rotulo_grupo = QLabel("")
            v.addWidget(self.rotulo_grupo)
            h = QHBoxLayout()
            self.trocar_grupo = QCheckBox("Usar outro grupo:")
            self.combo_grupo = QComboBox()
            for n in GRUPOS:
                self.combo_grupo.addItem(f"G{n}", n)
            self.justificativa = QLineEdit()
            self.justificativa.setPlaceholderText("Justificativa obrigatória para trocar o grupo")
            self.combo_grupo.setEnabled(False)
            self.justificativa.setEnabled(False)
            self.trocar_grupo.toggled.connect(self.combo_grupo.setEnabled)
            self.trocar_grupo.toggled.connect(self.justificativa.setEnabled)
            h.addWidget(self.trocar_grupo)
            h.addWidget(self.combo_grupo)
            h.addWidget(self.justificativa, 1)
            v.addLayout(h)
            f.addWidget(g)

        # ---------------- Botões
        h = QHBoxLayout()
        h.addStretch(1)
        if not self.modo_edicao:
            limpar = QPushButton("Limpar")
            limpar.clicked.connect(self.limpar)
            h.addWidget(limpar)
        self.botao_salvar = QPushButton("Salvar alterações" if self.modo_edicao else "Criar pasta e salvar")
        self.botao_salvar.setObjectName("primario")
        self.botao_salvar.clicked.connect(self.salvar_edicao if self.modo_edicao else self.criar_e_salvar)
        h.addWidget(self.botao_salvar)
        f.addLayout(h)
        lay.addStretch(1)
        self._tipo_mudou()

    @staticmethod
    def _grade(grid: QGridLayout, campos: list, colunas: int = 2):
        for i, (rotulo, w) in enumerate(campos):
            linha, col = divmod(i, colunas)
            grid.addWidget(QLabel(rotulo + ":"), linha, col * 2)
            grid.addWidget(w, linha, col * 2 + 1)
        for c in range(colunas):
            grid.setColumnStretch(c * 2 + 1, 1)

    def _botoes_tabela(self, tabela: QTableWidget, adicionar) -> QHBoxLayout:
        h = QHBoxLayout()
        b1 = QPushButton("Adicionar linha")
        b1.clicked.connect(lambda: adicionar({}))
        b2 = QPushButton("Remover selecionada")
        b2.clicked.connect(lambda: tabela.removeRow(tabela.currentRow()) if tabela.currentRow() >= 0 else None)
        h.addWidget(b1)
        h.addWidget(b2)
        h.addStretch(1)
        return h

    # ============================================================ tabelas
    def adicionar_passageiro(self, p: dict, sugestao: bool = False):
        t = self.tab_pass
        t.blockSignals(True)
        r = t.rowCount()
        t.insertRow(r)
        valores = {
            "nome": p.get("nome", ""), "cpf": formatar_cpf(p.get("cpf", "")), "email": p.get("email", ""),
            "telefone": p.get("telefone", ""), "documento": p.get("documento_arquivo", ""),
        }
        for c, (chave, _) in enumerate(COLS_PASSAGEIRO[:5]):
            item = QTableWidgetItem(valores[chave])
            if chave == "documento":
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            elif sugestao:
                item.setBackground(QColor(AMARELO))
            t.setItem(r, c, item)
        botao = BotaoArquivo("Anexar doc…", FILTRO_DOCS)
        botao.arquivo.connect(lambda arq, b=botao: self._anexar_doc(b, arq))
        t.setCellWidget(r, 5, botao)
        t.blockSignals(False)
        self._marcar_cpf(r)

    def _anexar_doc(self, botao: QWidget, arquivo: str):
        for r in range(self.tab_pass.rowCount()):
            if self.tab_pass.cellWidget(r, 5) is botao:
                item = self.tab_pass.item(r, 4)
                item.setText(Path(arquivo).name)
                item.setData(Qt.UserRole, arquivo)
                item.setToolTip(arquivo)
                return

    def _item_passageiro_mudou(self, item: QTableWidgetItem):
        if item.column() == 1:
            self._marcar_cpf(item.row())

    def _marcar_cpf(self, r: int):
        item = self.tab_pass.item(r, 1)
        if item is None:
            return
        self.tab_pass.blockSignals(True)
        texto = item.text().strip()
        if texto and not cpf_valido(texto):
            item.setBackground(QColor(AMBAR))
            item.setToolTip("CPF inválido (dígito verificador não confere)")
        elif item.toolTip():
            item.setBackground(QColor("#ffffff"))
            item.setToolTip("")
        self.tab_pass.blockSignals(False)

    def adicionar_trecho(self, t: dict, sugestao: bool = False):
        tab = self.tab_trechos
        r = tab.rowCount()
        tab.insertRow(r)
        combo = QComboBox()
        combo.addItem("Ida", "ida")
        combo.addItem("Volta", "volta")
        combo.setCurrentIndex(1 if t.get("sentido") == "volta" else 0)
        tab.setCellWidget(r, 0, combo)
        valores = {**t, "hora_saida": t.get("hora_saida") or t.get("hora", ""), "pessoas": str(t.get("pessoas") or 1)}
        for c, (chave, _) in enumerate(COLS_TRECHO[1:], start=1):
            item = QTableWidgetItem(str(valores.get(chave, "") or ""))
            if sugestao and chave not in ("hora_chegada", "companhia"):
                item.setBackground(QColor(AMARELO))
            tab.setItem(r, c, item)

    def _texto(self, tab: QTableWidget, r: int, c: int) -> str:
        item = tab.item(r, c)
        return item.text().strip() if item else ""

    def ler_passageiros(self) -> list[dict]:
        saida = []
        for r in range(self.tab_pass.rowCount()):
            nome = self._texto(self.tab_pass, r, 0)
            if not nome:
                continue
            doc_item = self.tab_pass.item(r, 4)
            saida.append({
                "nome": nome,
                "cpf": somente_digitos(self._texto(self.tab_pass, r, 1)),
                "email": self._texto(self.tab_pass, r, 2),
                "telefone": self._texto(self.tab_pass, r, 3),
                "documento_arquivo": doc_item.text() if doc_item else "",
                "_novo_documento": doc_item.data(Qt.UserRole) if doc_item else None,
            })
        return saida

    def ler_trechos(self) -> list[dict]:
        saida = []
        for r in range(self.tab_trechos.rowCount()):
            origem, destino = self._texto(self.tab_trechos, r, 1), self._texto(self.tab_trechos, r, 2)
            if not origem and not destino:
                continue
            pessoas = somente_digitos(self._texto(self.tab_trechos, r, 6))
            saida.append({
                "ordem": len(saida) + 1,
                "sentido": self.tab_trechos.cellWidget(r, 0).currentData(),
                "origem": origem,
                "origem_codigo": self._codigo(origem),
                "destino": destino,
                "destino_codigo": self._codigo(destino),
                "data": self._texto(self.tab_trechos, r, 3),
                "hora_saida": hora_hhmm(self._texto(self.tab_trechos, r, 4)),
                "hora_chegada": hora_hhmm(self._texto(self.tab_trechos, r, 5)),
                "pessoas": int(pessoas) if pessoas else 1,
                "bagagem": self._texto(self.tab_trechos, r, 7),
                "companhia": self._texto(self.tab_trechos, r, 8),
            })
        return saida

    # ============================================================ siglas
    def _codigo(self, cidade: str) -> str:
        if not cidade:
            return ""
        chave = normalizar(cidade)
        if chave in self.confirmados:
            return self.confirmados[chave]
        return self.ctx.siglas().codigo_ou_sugestao(cidade)[0]

    def _cidades_do_formulario(self) -> list[str]:
        cidades = []
        tipo = self.tipo.currentData()
        if tipo == "hospedagem":
            cidades.append(self.h_cidade.text().strip())
        else:
            for r in range(self.tab_trechos.rowCount()):
                cidades += [self._texto(self.tab_trechos, r, 1), self._texto(self.tab_trechos, r, 2)]
        return [c for c in cidades if c]

    def confirmar_siglas(self) -> None:
        """Pede confirmação do código das cidades que não estão na tabela (e oferece salvar)."""
        siglas = self.ctx.siglas()
        for cidade in self._cidades_do_formulario():
            chave = normalizar(cidade)
            if chave in self.confirmados or siglas.codigo(cidade):
                continue
            dlg = DialogoSigla(cidade, siglas.sugerir(cidade), self)
            dlg.exec()
            codigo = (dlg.codigo.text().strip() or siglas.sugerir(cidade)).upper()
            self.confirmados[chave] = codigo
            if dlg.salvar.isChecked():
                try:
                    siglas.adicionar(cidade, dlg.uf.text(), codigo)
                except Exception:
                    log.exception("Não foi possível salvar a sigla na tabela")
                    QMessageBox.warning(self, "Siglas", "Não foi possível salvar na tabela (Drive indisponível?).")

    @protegido
    def recalcular_resumo(self):
        self.confirmar_siglas()
        tipo = self.tipo.currentData()
        resumo = pastas.resumo_pasta(tipo, self.ler_trechos(), self._ler_hospedagem(), self.ctx.siglas(), self.confirmados)
        self.resumo.setText(resumo)

    def atualizar_previa(self):
        numero, ano, pj = self.numero.text().strip(), self.ano.text().strip(), self.proj_numero.text().strip()
        if not (numero and ano and pj):
            self.previa.setText("Prévia do caminho: preencha nº do pedido, ano e projeto.")
            return
        raiz = self.ctx.repo.raiz
        pasta_pj = pastas.pasta_projeto(raiz, pj)
        nome = pastas.nome_pasta_pedido(numero, ano, self.resumo.text().strip(), self.ctx.config.get("modelo_pasta"))
        if self.modo_edicao:
            pasta_pj = raiz / self.pedido["pasta"]["projeto"]
        existente = " (pasta do projeto já existe)" if pasta_pj.exists() else " (pasta do projeto será criada)"
        self.previa.setText(f"Prévia do caminho: {pasta_pj / nome}{existente}")

    # ============================================================ preencher
    def _tipo_mudou(self):
        tipo = self.tipo.currentData()
        self.grp_trechos.setVisible(tipo != "hospedagem")
        self.grp_hosp.setVisible(tipo in ("hospedagem", "outro"))

    def _projeto_mudou(self):
        pj = self.proj_numero.text().strip()
        if pj and not self.coord_email.text().strip():
            try:
                self.coord_email.setText(self.ctx.repo.ultimo_email_coordenador(pj))
            except Exception:
                log.exception("Falha ao consultar e-mail do coordenador no índice")
        self.atualizar_previa()

    @protegido
    def carregar_pdf(self, caminho: str):
        dados = ler_pedido(caminho)
        self.limpar()
        self.caminho_pdf = caminho
        self.rotulo_pdf.setText(f"PDF lido: {caminho}")
        self.preencher_de_leitura(dados)
        log.info("PDF lido: pedido %s", id_pedido(dados["numero"], dados["ano"]))

    def preencher_de_leitura(self, d: dict):
        self.formulario.setVisible(True)
        self.numero.setText(d["numero"])
        self.ano.setText(d["ano"])
        self.data_pedido.setText(d.get("data_pedido", ""))
        self.situacao.setText(d.get("situacao", ""))
        self.finalidade.setText(d.get("finalidade", ""))
        self.tipo.setCurrentIndex(max(self.tipo.findData(d.get("tipo", "outro")), 0))
        pj = d["projeto"]
        self.proj_numero.setText(pj["numero"])
        self.proj_nome.setText(pj["nome"])
        self.coordenador.setText(pj["coordenador"])
        self.gestor.setText(pj["gestor"])
        self.conta_caixa.setText(pj["conta_caixa"])
        s = d["solicitante"]
        self.sol_nome.setText(s["nome"])
        self.sol_email.setText(s["email"])
        self.sol_tel.setText(s["telefone"])
        self.itens_conveniar = d.get("itens", [])
        for p in d["passageiros"]:
            self.adicionar_passageiro(p, sugestao=True)
        if not d["passageiros"]:
            self.adicionar_passageiro({})
        for t in d["trechos"]:
            self.adicionar_trecho(t, sugestao=True)
        h = d.get("hospedagem")
        if h:
            self._preencher_hospedagem(h, sugestao=True)
        self._projeto_mudou()
        self.recalcular_resumo()
        self.atualizar_grupo()
        self.atualizar_previa()

    def _preencher_hospedagem(self, h: dict, sugestao: bool = False):
        for w, chave in ((self.h_cidade, "cidade"), (self.h_hotel, "hotel"), (self.h_checkin, "checkin"),
                         (self.h_checkout, "checkout"), (self.h_quarto, "quarto")):
            w.setText(h.get(chave, "") or "")
            if sugestao and w.text():
                destacar(w, AMARELO)
        self.h_hospedes.setValue(int(h.get("hospedes") or 1))

    def _preencher_de_pedido(self, p: dict):
        self.numero.setText(p["numero"])
        self.ano.setText(p["ano"])
        self.data_pedido.setText(p.get("data_pedido", ""))
        self.situacao.setText(p.get("situacao_conveniar", ""))
        self.finalidade.setText(p.get("finalidade", ""))
        self.tipo.setCurrentIndex(max(self.tipo.findData(p.get("tipo", "outro")), 0))
        pj = p.get("projeto", {})
        self.proj_numero.setText(pj.get("numero", ""))
        self.proj_nome.setText(pj.get("nome", ""))
        self.coordenador.setText(pj.get("coordenador", ""))
        self.coord_email.setText(pj.get("coordenador_email", ""))
        self.gestor.setText(pj.get("gestor", ""))
        self.conta_caixa.setText(pj.get("conta_caixa", ""))
        s = p.get("solicitante", {})
        self.sol_nome.setText(s.get("nome", ""))
        self.sol_email.setText(s.get("email", ""))
        self.sol_tel.setText(s.get("telefone", ""))
        for x in p.get("passageiros", []):
            self.adicionar_passageiro(x)
        for t in p.get("trechos", []):
            self.adicionar_trecho(t)
            for lado in ("origem", "destino"):
                if t.get(f"{lado}_codigo"):
                    self.confirmados.setdefault(normalizar(t[lado]), t[f"{lado}_codigo"])
        if p.get("hospedagem"):
            self._preencher_hospedagem(p["hospedagem"])
        self.itens_conveniar = p.get("itens_conveniar", [])
        self.resumo.setText(p.get("resumo", ""))
        self.atualizar_previa()

    def atualizar_grupo(self):
        if self.modo_edicao:
            return
        try:
            pedidos = [p for _, p in self.ctx.repo.listar_pedidos()]
            g = grupo_da_vez(pedidos, self.ctx.config.get("ultimo_grupo", 3))
            self.grupo_exibido = g
            nomes = ", ".join(e["nome"] for e in self.ctx.empresas_do_grupo(g))
            self.rotulo_grupo.setText(f"Grupo da vez: <b>G{g}</b> — {nomes}")
            self.combo_grupo.setCurrentIndex(self.combo_grupo.findData(proximo_grupo(g)))
        except Exception as exc:
            log.warning("Grupo da vez indisponível: %s", type(exc).__name__)
            self.grupo_exibido = None
            self.rotulo_grupo.setText("Grupo da vez: não foi possível ler a pasta de pedidos (Drive indisponível?).")

    def limpar(self):
        for w in (self.numero, self.ano, self.data_pedido, self.situacao, self.finalidade, self.proj_numero,
                  self.proj_nome, self.coordenador, self.gestor, self.conta_caixa, self.coord_email, self.sol_nome,
                  self.sol_email, self.sol_tel, self.h_cidade, self.h_hotel, self.h_checkin, self.h_checkout,
                  self.h_quarto, self.resumo):
            w.clear()
            destacar(w, None)
        self.h_hospedes.setValue(1)
        self.tab_pass.setRowCount(0)
        self.tab_trechos.setRowCount(0)
        self.caminho_pdf = None
        self.itens_conveniar = []
        self.confirmados = {}
        if not self.modo_edicao:
            self.rotulo_pdf.setText("")
            self.trocar_grupo.setChecked(False)
            self.justificativa.clear()
            self.formulario.setVisible(False)

    # ============================================================ coletar e validar
    def _ler_hospedagem(self) -> dict | None:
        if self.tipo.currentData() not in ("hospedagem", "outro") or not self.h_cidade.text().strip():
            return None
        return {
            "cidade": self.h_cidade.text().strip(), "hotel": self.h_hotel.text().strip(),
            "checkin": self.h_checkin.text().strip(), "checkout": self.h_checkout.text().strip(),
            "hospedes": self.h_hospedes.value(), "quarto": self.h_quarto.text().strip(),
        }

    def coletar(self) -> dict:
        tipo = self.tipo.currentData()
        return {
            "numero": self.numero.text().strip(),
            "ano": self.ano.text().strip(),
            "tipo": tipo,
            "data_pedido": self.data_pedido.text().strip(),
            "situacao_conveniar": self.situacao.text().strip(),
            "finalidade": self.finalidade.text().strip(),
            "resumo": pastas.sanitizar(self.resumo.text()),
            "projeto": {
                "numero": somente_digitos(self.proj_numero.text()), "nome": self.proj_nome.text().strip(),
                "coordenador": self.coordenador.text().strip(), "coordenador_email": self.coord_email.text().strip(),
                "gestor": self.gestor.text().strip(), "conta_caixa": self.conta_caixa.text().strip(),
            },
            "solicitante": {"nome": self.sol_nome.text().strip(), "email": self.sol_email.text().strip(),
                            "telefone": self.sol_tel.text().strip()},
            "passageiros": self.ler_passageiros(),
            "trechos": self.ler_trechos() if tipo != "hospedagem" else [],
            "hospedagem": self._ler_hospedagem(),
            "itens_conveniar": self.itens_conveniar,
        }

    def validar(self, d: dict) -> None:
        erros = []
        if not d["numero"].isdigit():
            erros.append("Nº do pedido")
        if not (d["ano"].isdigit() and len(d["ano"]) == 4):
            erros.append("Ano (4 dígitos)")
        if not d["projeto"]["numero"]:
            erros.append("Nº do projeto")
        if not d["resumo"]:
            erros.append("Resumo do nome da pasta")
        if not d["passageiros"]:
            erros.append("Pelo menos um passageiro/hóspede")
        if d["tipo"] in ("aerea", "terrestre"):
            if not d["trechos"]:
                erros.append("Pelo menos um trecho")
            for t in d["trechos"]:
                if not (t["origem"] and t["destino"]):
                    erros.append(f"Origem e destino do trecho {t['ordem']}")
                if t["data"] and not parse_data(t["data"]):
                    erros.append(f"Data do trecho {t['ordem']} (dd/mm/aaaa)")
        if d["tipo"] == "hospedagem":
            h = d["hospedagem"] or {}
            if not h.get("cidade"):
                erros.append("Cidade da hospedagem")
            for k in ("checkin", "checkout"):
                if not parse_data(h.get(k, "")):
                    erros.append(f"{k.capitalize()} (dd/mm/aaaa)")
        if erros:
            raise ValueError("Confira os campos:\n• " + "\n• ".join(erros))

    def _confirmar_cpfs(self, d: dict) -> bool:
        invalidos = [p["nome"] for p in d["passageiros"] if p["cpf"] and not cpf_valido(p["cpf"])]
        if not invalidos:
            return True
        r = QMessageBox.question(self, "CPF inválido",
                                 "CPF inválido para: " + ", ".join(invalidos) + ".\nDeseja salvar mesmo assim?")
        return r == QMessageBox.Yes

    def _copiar_documentos(self, pedido: dict, pasta: Path) -> None:
        for p in pedido["passageiros"]:
            origem = p.pop("_novo_documento", None)
            if origem:
                alvo = pastas.copiar_sem_sobrescrever(origem, pasta, pastas.nome_doc_passageiro(p["nome"], Path(origem).suffix))
                p["documento_arquivo"] = alvo.name
                pedido.setdefault("arquivos", []).append({"tipo": "documento", "nome": alvo.name})

    # ============================================================ criar
    @protegido
    def criar_e_salvar(self):
        self.confirmar_siglas()
        d = self.coletar()
        self.validar(d)
        if not self._confirmar_cpfs(d):
            return
        repo, analista = self.ctx.repo, self.ctx.analista
        repo.garantir_estrutura()
        pid = id_pedido(d["numero"], d["ano"])
        if repo.existe(d["numero"], d["ano"]):
            r = QMessageBox.question(self, "Pedido já cadastrado",
                                     f"O pedido {d['numero']}/{d['ano']} já está cadastrado.\nAbrir o pedido existente?")
            if r == QMessageBox.Yes:
                self.pedidoSalvo.emit(pid)
            return

        # ---- grupo da vez (relê a pasta de pedidos antes de gravar)
        pedidos = [p for _, p in repo.listar_pedidos()]
        sugerido = grupo_da_vez(pedidos, self.ctx.config.get("ultimo_grupo", 3))
        manual = self.trocar_grupo.isChecked() and self.combo_grupo.currentData() != sugerido
        escolhido = self.combo_grupo.currentData() if manual else sugerido
        justificativa = self.justificativa.text().strip() if manual else ""
        if manual and not justificativa:
            raise ValueError(f"O grupo da vez é G{sugerido}. Para usar G{escolhido}, escreva a justificativa.")
        if not manual and self.grupo_exibido and sugerido != self.grupo_exibido:
            QMessageBox.information(self, "Grupo atualizado",
                                    f"Outro pedido foi registrado enquanto você conferia.\nO grupo da vez agora é G{sugerido}.")
        ajuste_concorrencia = ""
        conflitos = conflitos_recentes(pedidos, escolhido)
        if conflitos:
            outro = conflitos[0]
            seguinte = proximo_grupo(escolhido)
            r = QMessageBox.question(
                self, "Possível conflito de rodízio",
                f"O pedido {outro['numero']}/{outro['ano']} foi criado há menos de 10 minutos com o grupo G{escolhido} "
                f"(o Drive pode estar sincronizando).\n\nUsar o grupo seguinte, G{seguinte}? (recomendado)")
            if r == QMessageBox.Yes:
                ajuste_concorrencia = f"G{escolhido} → G{seguinte}: pedido {outro['numero']}/{outro['ano']} criado há menos de 10 min no mesmo grupo"
                escolhido = sugerido = seguinte

        pedido = novo_pedido(d, analista)
        atribuir_grupo(pedido, escolhido, sugerido, justificativa, analista)
        if ajuste_concorrencia:
            registrar_historico(pedido, analista, "grupo_ajustado_sincronizacao", ajuste_concorrencia)

        # ---- pastas e arquivos
        nome = pastas.nome_pasta_pedido(d["numero"], d["ano"], d["resumo"], self.ctx.config.get("modelo_pasta"))
        pj, ped, existia = pastas.criar_pastas(repo.raiz, d["projeto"]["numero"], nome)
        if existia:
            QMessageBox.information(self, "Pasta existente", f"A pasta já existia e será usada, sem duplicar:\n{ped}")
        os.makedirs(pastas.caminho_longo(ped / pastas.PASTA_COTACAO), exist_ok=True)
        pedido["pasta"] = {"projeto": pj.name, "pedido": ped.name}
        if self.caminho_pdf:
            alvo = pastas.copiar_sem_sobrescrever(self.caminho_pdf, ped, pastas.nome_arquivo_pedido(d["numero"]))
            pedido["arquivos"].append({"tipo": "pedido", "nome": alvo.name})
        self._copiar_documentos(pedido, ped)
        for p in pedido["passageiros"]:
            p.pop("_novo_documento", None)

        repo.criar(pedido, analista)
        self.limpar()
        self.pedidoSalvo.emit(pid)

    # ============================================================ editar
    @protegido
    def salvar_edicao(self):
        self.confirmar_siglas()
        d = self.coletar()
        self.validar(d)
        if not self._confirmar_cpfs(d):
            return
        repo, analista = self.ctx.repo, self.ctx.analista
        p = copy.deepcopy(self.pedido)
        esperado = p.get("atualizado_em")
        for chave in ("tipo", "data_pedido", "situacao_conveniar", "finalidade", "resumo", "trechos", "hospedagem"):
            p[chave] = d[chave]
        p["projeto"].update(d["projeto"])
        p["solicitante"].update(d["solicitante"])
        p["passageiros"] = d["passageiros"]
        pasta_atual = repo.pasta_do_pedido(p)
        if d["resumo"] != self.pedido.get("resumo"):
            novo_nome = pastas.nome_pasta_pedido(p["numero"], p["ano"], d["resumo"], self.ctx.config.get("modelo_pasta"))
            if novo_nome != p["pasta"]["pedido"]:
                r = QMessageBox.question(self, "Renomear pasta",
                                         f"O resumo mudou. Renomear a pasta do pedido?\n\nDe: {p['pasta']['pedido']}\nPara: {novo_nome}")
                if r == QMessageBox.Yes:
                    destino = pasta_atual.parent / novo_nome
                    if destino.exists():
                        raise ValueError(f"Já existe uma pasta com o nome:\n{destino}")
                    if pasta_atual.exists():
                        os.rename(pastas.caminho_longo(pasta_atual), pastas.caminho_longo(destino))
                    else:
                        os.makedirs(pastas.caminho_longo(destino), exist_ok=True)
                    registrar_historico(p, analista, "pasta_renomeada", f"{p['pasta']['pedido']} → {novo_nome}")
                    p["pasta"]["pedido"] = novo_nome
                    pasta_atual = destino
        self._copiar_documentos(p, pasta_atual)
        for x in p["passageiros"]:
            x.pop("_novo_documento", None)
        repo.salvar(p, analista, "dados_editados", esperado=esperado)
        self.pedido = p
        self.pedidoSalvo.emit(id_pedido(p["numero"], p["ano"]))


class DialogoEditarPedido(QDialog):
    def __init__(self, ctx: Contexto, pedido: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Editar pedido {pedido['numero']}/{pedido['ano']}")
        self.resize(1100, 800)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.form = FormularioPedido(ctx, pedido, self)
        self.form.pedidoSalvo.connect(lambda _: self.accept())
        lay.addWidget(self.form)
