# WhatsApp (Cloud API da Meta) — como ligar

O código (`django_app/apps/whatsapp`) suporta dois jeitos de conectar o número de uma clínica.
Os dois chegam no mesmo lugar (`ConexaoWhatsApp` + templates criados na WABA da clínica + webhook);
muda só quem cria o token e como.

| | Hoje (fase 1) | Futuro (fase 2) |
|---|---|---|
| Quando | Só a Lume usa o Vettro | Mais de uma clínica |
| Quem conecta | Plataforma, à mão (`/plataforma/` → Conexões de WhatsApp → Conectar manualmente) | A própria clínica, em ⚙️ Clínica → WhatsApp (Embedded Signup) |
| App Meta | Criado no portfólio de negócios **da Lume** | App do **Vettro**, aprovado como Tech Provider |
| Token | System user da Lume, gerado à mão | Gerado pela Meta no Embedded Signup |
| Número | Dedicado à API (não pode estar no app WhatsApp) | Dedicado **ou** coexistência com o app WhatsApp Business |
| Revisão da Meta | Não precisa | App Review + Tech Provider |

---

## Fase 1 — Lume, sem Tech Provider (caminho atual)

Sem revisão da Meta, um app só acessa WABAs do **mesmo portfólio de negócios** em que ele foi
criado. Por isso tudo fica no portfólio da Lume: app, WABA, número, system user e cobrança.

### 1. Portfólio de negócios da Lume
1. Entrar em <https://business.facebook.com> com a conta de quem administra a Lume e criar (ou usar) o
   portfólio de negócios da clínica.
2. Configurações do negócio → Central de segurança → **Verificação da empresa** (CNPJ, comprovante
   de endereço, domínio ou telefone). Sem verificação a Lume fica limitada a 250 conversas
   iniciadas por dia e o nome exibido não aparece — suficiente para testar, mas faça logo.

### 2. Número
- Precisa ser um número que **não esteja** no app WhatsApp nem no WhatsApp Business (se estiver,
  apague a conta do app nesse número antes). Coexistência com o app só existe pelo Embedded Signup
  (fase 2).
- Pode ser fixo ou celular; precisa receber SMS ou ligação para o código de verificação.
- As respostas dos tutores aparecem no menu **Lembretes** do Vettro.

### 3. App Meta (no portfólio da Lume)
1. <https://developers.facebook.com/apps> → Criar app → tipo **Negócios** → portfólio: Lume.
2. Adicionar o produto **WhatsApp**. A Meta cria uma WABA de teste; em WhatsApp → Configuração da
   API → **Adicionar número de telefone**, cadastre o número real da Lume (nome de exibição:
   "Lume Clínica Veterinária" ou o nome que estiver na verificação) e confirme o código.
3. Anote o **ID do número** (`phone_number_id`) e o **ID da conta do WhatsApp Business**
   (`waba_id`) que aparecem nessa tela.
4. Configurações do app → Básico: anote o **ID do app** e a **Chave secreta do app**.

### 4. Token permanente (system user)
1. Configurações do negócio → Usuários → **Usuários do sistema** → Adicionar (função: Admin).
2. **Atribuir ativos**: o app (controle total) e a conta do WhatsApp (controle total).
3. **Gerar token**: app = o da Lume, validade **Nunca**, permissões
   `whatsapp_business_management` e `whatsapp_business_messaging`. Copie na hora — não aparece de novo.

### 5. Webhook
No app → WhatsApp → Configuração → Webhook:
- URL de callback: `https://www.vettro.com.br/whatsapp/webhook/`
- Token de verificação: o mesmo valor de `META_WEBHOOK_VERIFY_TOKEN` no servidor (invente um
  texto longo e aleatório).
- Campos: assinar **messages**, **message_template_status_update** e **account_update**.

O servidor precisa estar no ar com as variáveis abaixo **antes** de salvar o webhook (a Meta faz
um GET de verificação na hora).

### 6. Variáveis no servidor
```
WHATSAPP_BACKEND=apps.whatsapp.backends.WhatsAppMetaCloudBackend
META_APP_ID=<ID do app da Lume>
META_APP_SECRET=<chave secreta do app da Lume>   # valida a assinatura do webhook
META_WEBHOOK_VERIFY_TOKEN=<o mesmo do passo 5>
WHATSAPP_CHAVE_CRIPTO=<opcional: Fernet.generate_key()>
# Fase 2 apenas — deixe vazio agora (sem ele a tela da clínica esconde o Embedded Signup):
META_EMBEDDED_SIGNUP_CONFIG_ID=
```
Gerar a chave Fernet: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
Se trocar `WHATSAPP_CHAVE_CRIPTO` (ou o `DJANGO_SECRET_KEY`, quando ela estiver vazia) o token
salvo fica ilegível — é só conectar de novo.

### 7. Conectar no Vettro
1. `/plataforma/` → Conexões de WhatsApp → **Conectar manualmente**.
2. Clínica: Lume · WABA · ID do número · token do passo 4.
3. Marque **Registrar o número na Cloud API** se o número acabou de ser adicionado (gera e guarda o
   PIN de 2 etapas). Se já estiver registrado (aparece "Conectado" no WhatsApp Manager), deixe
   desmarcado.
4. O Vettro assina os webhooks na WABA, lê o número e **cria os 4 modelos de mensagem** (agendamento,
   vacina, retorno = utilidade; aviso = marketing). A aprovação leva de minutos a 1 dia: acompanhe
   em ⚙️ Clínica → WhatsApp → "Atualizar situação" (o webhook também atualiza sozinho).

### 8. Cobrança e liberação
1. WhatsApp Manager → Visão geral → **Adicionar forma de pagamento** (cartão da Lume). Sem isso
   os modelos pagos não saem.
2. Habilitar o módulo da Lume: `/plataforma/` → Clínicas → Lume → "Lembrete de WhatsApp (Agenda)".
3. ⚙️ Clínica → WhatsApp → **Enviar teste** para um celular seu.
4. Cron diário no servidor: `python manage.py enviar_lembretes_whatsapp`.

---

## Fase 2 — Vettro como Tech Provider (quando entrar a 2ª clínica)

O código já está pronto (`conectar_embedded_signup`, tela com os dois botões, coexistência). Falta:

1. Portfólio de negócios **do Vettro** (verificado com o CNPJ do Vettro) e um **app novo** nele —
   não reaproveitar o app da Lume, que é da clínica.
2. Inscrever o app como **Tech Provider** e passar pelo **App Review** pedindo Advanced Access em
   `whatsapp_business_management` e `whatsapp_business_messaging` (vídeo do fluxo de conexão).
3. Produto **Facebook Login for Business** → Configurações → nova configuração do tipo
   **Embedded Signup** (v4 — v2/v3 foram descontinuados em 15/10/2026) com o produto WhatsApp →
   copie o ID para `META_EMBEDDED_SIGNUP_CONFIG_ID`.
4. Facebook Login → Configurações: `www.vettro.com.br` em **Allowed domains** e **Valid OAuth
   redirect URIs** (exige HTTPS).
5. Webhook no app do Vettro igual ao passo 5, acrescentando os campos da coexistência:
   **history**, **smb_app_state_sync** e **smb_message_echoes**.
6. Trocar `META_APP_ID` e `META_APP_SECRET` pelos do app do Vettro. **Atenção:** a assinatura do
   webhook passa a ser validada com o segredo do app novo, então a conexão manual da Lume deixa de
   receber webhooks — **reconecte a Lume** pelo Embedded Signup (⚙️ Clínica → WhatsApp →
   Desconectar → Conectar). A WABA e o número continuam os mesmos (a Meta permite escolher uma
   conta existente no Embedded Signup); os modelos já aprovados são reaproveitados.
7. Cada clínica nova conecta sozinha e paga a Meta direto na conta dela.

Referências (documentação oficial):
- Visão geral: <https://developers.facebook.com/documentation/business-messaging/whatsapp/overview/>
- Embedded Signup: <https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/implementation/>
- Passos do Tech Provider: <https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-customers-as-a-tech-provider/>
- Coexistência: <https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-business-app-users/>
- Webhooks: <https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview/>
