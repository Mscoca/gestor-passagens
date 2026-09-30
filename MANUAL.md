# Manual de Uso — Gestor de Passagens

Atualizado em 30/09/2026

## Visão geral

O **P.A.T.H.** (Passagens Aéreas, Terrestres e Hospedagens) é o aplicativo desktop da FAPEC que ajuda o analista de compras a tratar pedidos de viagem do início ao fim. Ele lê o PDF do Pedido de Compra do Conveniar, cria as pastas no Drive compartilhado, indica o grupo de empresas da vez, registra as cotações e gera os e-mails de cotação e de aprovação.

## Primeiros passos

1. **Instalar:** descompacte o arquivo **Instalador P.A.T.H.zip** e dê dois cliques em **Instalar P.A.T.H.bat**. Não precisa de administrador; os atalhos aparecem na Área de Trabalho e no Menu Iniciar.
2. **Primeiro uso:** o assistente **Bem-vindo ao P.A.T.H.** pede a pasta raiz do credenciamento (no Google Drive), seu nome, e-mail e assinatura. Clique em **Começar**.
3. **Navegar:** o menu lateral tem três telas — **Pedidos**, **Novo pedido** e **Configurações**.

Para atualizar o programa, repita o passo 1 com o zip novo. Suas configurações, senhas e pedidos são mantidos.

## Funcionalidades

### 1. Pedidos (lista)

Tela inicial com todos os pedidos, das viagens mais próximas para as mais distantes.

- **Busca:** digite nº do pedido, projeto, passageiro, CPF ou cidade.
- **Filtros:** por status e por tipo (Passagem Aérea, Passagem Terrestre, Hospedagem, Outro).
- **Atualizar:** relê os pedidos do Drive.
- **Cores:** vermelho = viagem nos próximos 5 dias sem emissão; laranja = prazo de aprovação vence hoje.
- **Duplo clique** numa linha abre o pedido.

### 2. Novo pedido

1. Arraste o **PDF do Pedido de Compra do Conveniar** para a área indicada. O sistema preenche os campos sozinho.
2. Confira os dados. Campos em **amarelo** foram lidos do texto livre e merecem atenção.
3. Revise **Passageiros / hóspedes**, **Trechos** ou **Hospedagem**, e o **Resumo do nome da pasta** (botão **Recalcular**).
4. Veja o **Grupo de empresas (rodízio)** sugerido. Para usar outro, marque **Usar outro grupo** e escreva a justificativa.
5. Clique em **Criar pasta e salvar**. A pasta é criada no Drive e o pedido abre em seguida.

### 3. Painel do pedido

No topo ficam status, grupo, prazo e os botões **Recarregar**, **Editar dados**, **Abrir pasta** e **Mudar status**. O conteúdo fica em seis abas:

| Aba | Para que serve |
| --- | --- |
| **Dados** | Ver o pedido completo; **Copiar descritivo** e **Copiar CPF completo** (o CPF aparece mascarado; use **Mostrar**). |
| **Grupo e acessos** | Ver as empresas do grupo; **Abrir portal**, **Copiar login**, **Copiar senha**; **Trocar grupo…** (com justificativa). |
| **Cotações** | Informar valor e forma (Portal ou E-mail) de cada empresa; **Anexar proposta**; **Salvar cotações**; **Definir vencedora**; **Anexar pré-reserva da vencedora**. |
| **E-mails** | Escolher **Cotação à empresa** ou **Aprovação (solicitante e coordenador)**, clicar em **Gerar e-mail** e usar **Copiar assunto**, **Copiar corpo**, **Copiar destinatários** ou **Abrir no Gmail**. |
| **Arquivos** | Ver os arquivos da pasta; **Anexar pré-reserva**, **Anexar reserva**, **Anexar outro**. Duplo clique abre o arquivo. |
| **Histórico** | Ver quem fez o quê e quando. |

**Mudar status** segue esta ordem: Em cotação → Aguardando aprovação → Aprovado → Emitido. Um pedido **Reprovado** volta para Em cotação. **Cancelar** pede o motivo, e um cancelado pode ser reaberto com **Reabrir (Em cotação)**.

### 4. Configurações

| Aba | Para que serve |
| --- | --- |
| **Geral** | Pasta raiz, conta do Gmail, e-mail em cópia (CC) e último grupo usado. |
| **Meus dados** | Seu nome, e-mail e assinatura dos e-mails. |
| **Meus acessos** | Login e senha de cada portal. A senha fica guardada no Gerenciador de Credenciais do Windows. Use **Testar** para conferir. |
| **Empresas e grupos** | Cadastro compartilhado das empresas e do grupo de cada uma (G1, G2 ou G3). **Incluir empresa**, **Salvar empresas**. |
| **Siglas de cidades** | Tabela de siglas usadas no nome das pastas (ex.: CGR, FLN). |
| **Modelos de e-mail** | Editar os textos dos e-mails; **Restaurar padrão** desfaz as mudanças. |

## Dicas e dúvidas comuns

- **Rodízio:** cada pedido novo usa o grupo seguinte ao do último pedido cadastrado (G1 → G2 → G3 → G1). Pedidos cancelados antes da cotação não contam.
- **Cotações:** registre pelo menos 3 valores. O menor aparece em verde. Em empate, ou se a vencedora não for a mais barata, a justificativa é obrigatória.
- **Aprovação:** ao gerar o e-mail de aprovação, o sistema oferece mudar o status para Aguardando aprovação.
- **Arquivos:** são sempre copiados, nunca movidos nem sobrescritos (cópias recebem “(2)”, “(3)”…).
- **Drive indisponível:** abra o Google Drive para computador e clique em **Atualizar** na lista de pedidos.
- **Pedido alterado por outra pessoa:** o sistema avisa e recarrega o pedido; refaça sua alteração.
- **Arquivos duplicados pelo Drive** (ex.: “33276-2026 (1).json”): a tela Configurações mostra um alerta.
