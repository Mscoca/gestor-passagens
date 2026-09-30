import keyring
import pytest
from keyring.backend import KeyringBackend

from core import credenciais


class MemoriaKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.dados = {}

    def set_password(self, service, username, password):
        self.dados[(service, username)] = password

    def get_password(self, service, username):
        return self.dados.get((service, username))

    def delete_password(self, service, username):
        from keyring.errors import PasswordDeleteError

        if (service, username) not in self.dados:
            raise PasswordDeleteError()
        del self.dados[(service, username)]


@pytest.fixture
def memoria():
    anterior = keyring.get_keyring()
    k = MemoriaKeyring()
    keyring.set_keyring(k)
    yield k
    keyring.set_keyring(anterior)


def test_senha_vai_para_o_keyring(memoria):
    credenciais.salvar_senha("condor", "ana.login", "s3nh@!")
    assert memoria.dados == {("GestorPassagens:condor", "ana.login"): "s3nh@!"}
    assert credenciais.obter_senha("condor", "ana.login") == "s3nh@!"
    credenciais.apagar_senha("condor", "ana.login")
    assert credenciais.obter_senha("condor", "ana.login") is None
    credenciais.apagar_senha("condor", "ana.login")  # não quebra se não existir


class ClipboardFalso:
    def __init__(self):
        self.conteudo = ""

    def text(self):
        return self.conteudo

    def setText(self, t):
        self.conteudo = t

    def setMimeData(self, dados):
        self.conteudo = dados.text()

    def clear(self):
        self.conteudo = ""


def test_limpa_area_de_transferencia_apos_30s():
    agendados = []
    cb = ClipboardFalso()
    lim = credenciais.LimpadorAreaTransferencia(cb, lambda ms, fn: agendados.append((ms, fn)))
    lim.copiar("s3nh@!")
    assert cb.text() == "s3nh@!"
    assert agendados[0][0] == 30_000
    agendados[0][1]()
    assert cb.text() == ""


def test_nao_limpa_se_o_conteudo_mudou():
    agendados = []
    cb = ClipboardFalso()
    lim = credenciais.LimpadorAreaTransferencia(cb, lambda ms, fn: agendados.append((ms, fn)))
    lim.copiar("s3nh@!")
    cb.setText("outra coisa copiada pelo analista")
    agendados[0][1]()
    assert cb.text() == "outra coisa copiada pelo analista"
