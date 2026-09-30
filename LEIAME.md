# P.A.T.H. — Passagens Aéreas, Terrestres e Hospedagens

Aplicativo desktop (Windows) da FAPEC para o analista de compras: lê o PDF do Pedido de Compra do
Conveniar, cria as pastas no Drive compartilhado, indica o grupo de empresas da vez (rodízio),
registra cotações e gera os e-mails de cotação e de aprovação.

## Instalação (analistas) — um clique

1. Pegue o arquivo **`Instalador P.A.T.H.zip`** (ex.: numa pasta do Drive da equipe) e descompacte.
2. Dê dois cliques em **`Instalar P.A.T.H.bat`**.

Pronto: o programa é copiado para `%LOCALAPPDATA%\Programs\PATH` (não precisa de administrador),
os atalhos **P.A.T.H.** são criados na Área de Trabalho e no Menu Iniciar, e o programa abre.
Na primeira vez, um assistente pede a pasta raiz, seu nome, e-mail e assinatura.

**Para atualizar** para uma versão nova: repita os mesmos 2 passos com o zip novo. O instalador fecha
o programa se estiver aberto e substitui os arquivos. Configurações, senhas e pedidos não são afetados.

## Como gerar o executável e o instalador (quem mantém o sistema)

1. Instale o **Python 3.12** (python.org, marque "Add to PATH"). Se o 3.12 não existir, o script usa o Python 3 instalado.
2. Dê dois cliques em `build.bat` (ou rode no Prompt de Comando, dentro desta pasta).
   O script:
   1. cria o ambiente `.venv`;
   2. instala `requirements.txt` e o PyInstaller;
   3. roda os testes (`pytest`) e **para se algum falhar**;
   4. gera o executável com `GestorPassagens.spec`.
   5. monta o pacote `dist\Instalador P.A.T.H.zip` para distribuir à equipe;
   6. pergunta se quer instalar neste computador agora.
3. Resultado: `dist\Instalador P.A.T.H.zip` e `dist\GestorPassagens\GestorPassagens.exe`
   (modo pasta: o `.exe` precisa da pasta `_internal` ao lado).

Teste rápido do executável (cria um pedido de exemplo numa pasta temporária, abre o painel e fecha):

```
dist\GestorPassagens\GestorPassagens.exe --autoteste %TEMP%\path_autoteste
```

O resultado fica em `%TEMP%\path_autoteste\autoteste.txt` (`OK` = tudo certo).

## Modo desenvolvimento

```
cd gestor_passagens
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

Testes: `.venv\Scripts\python -m pytest -q`. Os testes de interface rodam sem abrir janelas.
PDFs reais colocados em `tests\pdfs\` entram automaticamente nos testes do leitor.

## Onde ficam os dados

| O quê | Onde |
|---|---|
| Pedidos (fonte da verdade, 1 JSON por pedido) | `<pasta raiz>\_Sistema Passagens\pedidos\` |
| Empresas e grupos | `<pasta raiz>\_Sistema Passagens\empresas.json` |
| Siglas das cidades | `<pasta raiz>\_Sistema Passagens\siglas_cidades.csv` |
| Modelos de e-mail | `<pasta raiz>\_Sistema Passagens\modelos_email\` |
| Índice de busca (SQLite, só desta máquina) | `%LOCALAPPDATA%\GestorPassagens\indice.db` |
| Logs (com rotação) | `%LOCALAPPDATA%\GestorPassagens\logs\` |
| Configuração do analista | `%APPDATA%\GestorPassagens\config.json` |
| Senhas dos portais | Gerenciador de Credenciais do Windows (`GestorPassagens:<empresa>`) |

- O SQLite **nunca** fica no Drive: ele é reconstruído dos JSONs ao abrir o programa e no botão **Atualizar**.
- Os JSONs são gravados de forma atômica (`.tmp` + renomear). Se outro analista alterou o pedido no meio tempo,
  o programa avisa e recarrega.
- Se o Drive criar cópias em conflito (ex.: `33276-2026 (1).json`), a tela **Configurações** mostra um alerta.
- Senhas, CPF completo e conteúdo de e-mails não vão para o log.

## Regras principais

- **Rodízio**: cada pedido novo usa o grupo seguinte ao do pedido cadastrado mais recentemente (G1 → G2 → G3 → G1).
  Pedidos cancelados antes da cotação não contam. Trocar o grupo exige justificativa, que fica no histórico.
  Sem nenhum pedido registrado, vale o "Último grupo usado" em Configurações → Geral.
- **Cotações**: mínimo de 3 valores; o menor fica em verde. Em empate, é preciso registrar a ligação para cada
  empresa empatada e justificar a escolha.
- **Arquivos**: sempre copiados (o original não é movido) e nunca sobrescritos (` (2)`, ` (3)`…).
