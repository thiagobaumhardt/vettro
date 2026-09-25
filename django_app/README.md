# Vettro — Django (multi-tenant, para a Lume)

Backend/frontend do Vettro (Django + django-tenants + HTMX + Alpine + Tailwind) — único sistema
vivo no repositório (a versão anterior em FastAPI/Vue foi removida, já que nenhuma clínica
estava em produção nela). Ver o plano completo em
`C:\Users\thiag\.claude\plans\golden-tinkering-gem.md`.

**Status**:
- ✅ Fase 1 (esqueleto, multi-tenancy, autenticação) — provisionamento de clínica, login,
  seletor/troca de clínica, admin de plataforma, rate limiting, `/health`.
- ✅ Fase 2 (Tutores + Pacientes) — CRUD de Tutores (CPF, CEP autofill via ViaCEP server-side,
  consentimento/exportação LGPD), CRUD de Pacientes (foto de perfil real via `ImageField`,
  storage isolado por clínica), Ficha do paciente com abas via HTMX (Ficha, Anotações).
- ✅ Fase 3 (Anamnese/Cirurgias/Exames/Fotos, Agenda, Atendimentos, Estoque com ledger) —
  Anamnese e Cirurgias com plantão (+50% só sobre serviços/procedimentos), faixa de peso P/M/G
  pra cirurgia, deslocamento outra cidade (+R$50), débito de estoque e Cobrança automática;
  Exames (PDF) e Fotos (galeria + lightbox) com upload real; Agenda com calendário
  server-rendered + HTMX; Atendimentos avulso (sem gerar Cobrança, assimetria preservada);
  Estoque com ledger `MovimentoEstoque` (SD1 entrada via XML de NF-e **ou** manual sem nota,
  SD2 saída, SD3 ajuste interno), importação de XML já captura NCM automaticamente.
  **+ Consultórios/locais cadastráveis livremente**, fechamento de agenda por dia ou turno
  (admin only, testado: vet não-admin recebe 403), e **lembrete de WhatsApp 24h antes**
  (`enviar_lembretes_whatsapp`, backend substituível — provedor ainda não escolhido).
  **+ Bloqueio geral e recorrente** (paridade com o SimplesVet, que faz distinção entre
  bloqueio geral × individual e pontual × recorrente): `BloqueioAgenda.consultorio` agora aceita
  `None` = fecha a agenda inteira (todos os consultórios de uma vez, não só um por um); e
  `recorrente=True` + `dia_semana` repete o bloqueio toda semana, com `data_fim` opcional
  (recorrência sem data de término). Testado ponta a ponta (clínica de teste provisionada e
  removida): bloqueio geral barra agendamento em qualquer consultório; bloqueio recorrente
  sem data-fim barra o mesmo dia da semana indefinidamente, só no turno certo, só no
  consultório certo, sem vazar pros outros; calendário mostra 🔒 corretamente em todas as
  ocorrências do mês (geral aparece mesmo sem filtrar consultório; recorrente só some ao
  filtrar o consultório certo, mesmo comportamento de antes).
- ✅ Fase 4 (Cobranças, Auditoria, Usuários por clínica) — aba Cobrança (admin-only) com
  criação manual + Cobrança automática de Anamnese/Cirurgia + marcar como pago; Auditoria
  (login, criar/atualizar/excluir/exportar de Tutor/Paciente, import de NF-e) — `LoginAudit`
  global (schema public, tentativas de login antes de escolher clínica) + `AuditLog` por
  clínica; Usuários por clínica com reaproveitamento de identidade global (testado: mesma
  pessoa em 2 clínicas, sem duplicar conta). **+ Perfis de acesso expandidos** (pedido
  explícito do usuário, confirmado como o modelo do SimplesVet): além de admin/vet, agora
  `atendente` (Tutores/Pacientes/Agenda, sem dados clínicos) e `motorista` (só Agenda) —
  testado que cada perfil só acessa exatamente as seções permitidas (403 nas demais).
  **+ Convite por e-mail pra definir senha** (pedido explícito do usuário): admin nunca mais
  digita/sabe a senha de ninguém — cria o Usuario com `set_unusable_password()`, manda um link
  seguro de uso único (token nativo do Django, mesmo mecanismo do "esqueci minha senha") pra
  pessoa definir a própria senha. Mesmo padrão no provisionamento de clínica nova (admin de
  plataforma). Testado ponta a ponta: e-mail enviado, link funciona, senha definida, login
  funciona, **reusar o link depois é bloqueado** (token invalidado após a troca de senha).
- 🎨 **Identidade visual da marca real (Lume)** aplicada — a partir da apresentação de
  identidade visual da clínica (Lume, Cachoeira do Sul/RS): paleta verde-escuro/verde-oliva/
  verde-claro/marfim/amarelo/terroso (estimada visualmente, sem hex oficial no material — ver
  ressalva em `static/dist/styles.css`), tipografia Livvic (textos, fonte real da marca) +
  Fraunces (títulos, substituta gratuita temporária da Roca Two, que é paga/sem licença web
  confirmada), toggle de sidebar mobile (hambúrguer + off-canvas) finalmente ligado.
- 📱 **Backend real de WhatsApp implementado** (`WhatsAppMetaCloudBackend`, Meta Cloud API
  oficial) — decisão tomada depois de pesquisa mostrando que Z-API/Evolution API conectam via
  QR Code (mesmo risco de banimento do WhatsApp Web não-oficial, mesmo sendo pagas). Mensagem
  vira variável de um template aprovado (obrigatório pra mensagem de negócio-pro-cliente fora
  da janela de 24h). Testado com HTTP mockado: payload correto, tratamento de erro/config
  ausente, fluxo ponta a ponta do comando `enviar_lembretes_whatsapp`. Falta só a conta Meta
  Business + template aprovado de cada clínica pra ativar de verdade (`WHATSAPP_BACKEND` +
  `WHATSAPP_META_*` nas envs).
- 🧩 **Módulos habilitáveis por clínica** (pedido explícito do usuário) — o admin de
  plataforma decide, no provisionamento (editável depois no admin da Clinica), quais módulos
  cada clínica tem: Tutores/Pacientes/Financeiro/Estoque/Atendimentos/Agenda vêm marcados por
  padrão, Lembrete de WhatsApp vem desmarcado (exige config externa). Um módulo desabilitado
  some da sidebar e retorna 403 em qualquer view daquela seção — **pra todo mundo da clínica,
  inclusive o admin dela** (é uma camada acima do papel individual, não substitui ela — ver
  `Clinica.modulos_habilitados()` × `apps.core.decorators.secoes_permitidas`). Testado ponta a
  ponta: módulo desabilitado bloqueia view (403), some do menu, e o comando de lembrete pula
  clínica sem o módulo de WhatsApp habilitado.
- 🧱 **Esqueleto de `apps.pagamentos`** (§8 do plano) — `TransacaoTEF` (adquirente/terminal
  livres, pensando desde já em clínica com mais de uma maquininha simultânea — SiTef exige
  código de terminal distinto por conexão simultânea do mesmo par loja/terminal) e
  `NotaFiscalEmitida` (placeholder, sem chamada real à Focus NFe ainda). Interface `TEFBackendBase`
  + `TEFConsoleBackend` (sandbox, sempre aprova) — mesmo princípio do backend substituível do
  WhatsApp, backend real (SiTef/PayGo) plugável depois via `TEF_BACKEND` sem mudar `services.py`.
  **Importante**: `iniciar_pagamento_tef` só marca a Cobrança como paga — NÃO debita estoque,
  porque o débito (SD2) já acontece na criação da Anamnese/Cirurgia que gera a Cobrança (ver
  `apps.pacientes.services`), então debitar de novo aqui duplicaria a saída. Testado ponta a
  ponta (clínica de teste provisionada e removida na mesma verificação): Cobrança pendente →
  `iniciar_pagamento_tef` → transação aprovada pelo sandbox → Cobrança vira "pago". Ainda **sem
  UI** (nenhum botão chama isso ainda) e sem emissão fiscal real — aguardando decisão SiTef vs
  PayGo e conta Focus NFe homologada.
- 🔒 **Reforço de LGPD** (pedido explícito do usuário, revisão de conformidade) — dois gaps reais
  corrigidos: (1) **direito à eliminação incompleto** — excluir um Tutor deixava
  `tutor_nome`/`tutor_tel` intactos nos snapshots desnormalizados de Cobrança/Agendamento/
  Atendimento; `apps.tutores.services.escrubar_snapshots_tutor` agora limpa esses snapshots
  (substitui por "Tutor excluído (LGPD)"/vazio) antes da exclusão, preservando o registro em si
  (retenção fiscal/histórico clínico, LGPD Art. 16) — só o dado pessoal do snapshot some.
  (2) **Consentimento LGPD granular** — `Tutor.consentimento_whatsapp` (+ timestamp próprio)
  separado do `consentimento_dados` geral, porque cadastro/atendimento tem base legal própria
  (execução de contrato) mas lembrete via WhatsApp (Meta, fora do Brasil) é tratamento opcional
  que pede opt-in específico e revogável; `enviar_lembretes_whatsapp` agora exige esse
  consentimento além do módulo da clínica — agendamento avulso ou sem tutor consentido nunca
  recebe lembrete (padrão seguro: sem registro de consentimento, não envia). Testado ponta a
  ponta (clínica de teste): sem consentimento não envia, com consentimento envia; exclusão
  escruba os 3 modelos corretamente preservando paciente/histórico; formulário cria e revoga o
  consentimento de WhatsApp independente do geral (verificado via `Client` HTTP real).
- ⏳ Fases 5-6: Configurações fiscais da clínica, emissão fiscal real (Focus NFe), deploy KingHost
  (**bloqueado**: preciso confirmar se o plano da KingHost suporta Python 3.10+ — Django 5.1
  exige isso, e a doc pública encontrada só cobria até Python 3.7).

Tudo testado ponta a ponta via `Client` de teste do Django (não só "escreveu e não rodou") —
login, CRUD completo, troca de clínica, consentimento LGPD, exportação, autofill de CEP.

## Primeira execução (dev local)

```bash
cd django_app
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt

docker compose up -d             # Postgres de dev só deste app, porta 5433
cp .env.example .env             # ajuste se necessário

python manage.py migrate_schemas --shared   # schema public (plataforma/contas/admin/auth)
python manage.py createcachetable            # tabela do rate-limit de login (cache framework)
python manage.py createsuperuser --email plataforma@vettro.com.br  # admin de plataforma

python manage.py runserver
```

Depois, em `/plataforma/` (login com o superuser criado acima), use "Provisionar nova
clínica" na lista de Clínicas — isso cria o schema Postgres da clínica, roda as migrations de
tenant nele e cadastra o primeiro admin *daquela* clínica. Faça login normal em `/login/` com
esse admin pra entrar no sistema da clínica.

Se o schema de tenant mudar (novo model em algum app de `TENANT_APPS`), gere a migration
(`python manage.py makemigrations <app>`) e rode `python manage.py migrate_schemas` de novo —
isso aplica em TODOS os schemas de clínica existentes de uma vez.

## Estrutura

Ver `config/settings/base.py` (`SHARED_APPS`/`TENANT_APPS`) e §2-§3 do plano. Resumo:
- `apps/plataforma` — identidade global (Usuario), registro de clínicas (Clinica), vínculos
  (UsuarioClinica). Vive no schema **public**.
- `apps/contas` — login, logout, seletor/troca de clínica,
  `TenantFromSessionMiddleware` (ativa o schema da clínica pela sessão, não por subdomínio).
- `apps/core` — utilitários cross-app (`admin_required`, `requer_secao`/`PERMISSOES_POR_PAPEL`,
  health check, headers de segurança).
- `apps/dashboard` — tela inicial pós-login (placeholder; estatísticas reais ficam pra depois).
- `apps/tutores`, `apps/pacientes`, `apps/financeiro`, `apps/estoque`, `apps/atendimentos`,
  `apps/agenda`, `apps/auditoria`, `apps/usuarios_clinica` — módulos clínicos/operacionais,
  todos no schema de cada clínica (TENANT_APPS).
- `apps/pagamentos` — esqueleto (models `TransacaoTEF`/`NotaFiscalEmitida` + interface TEF
  plugável, sem UI/backend real ainda — ver Status acima).

`apps/configuracoes` (Fase 6, ainda não implementado) fica pra depois — dados fiscais reais da
clínica (CNPJ, inscrições, certificado digital) precisam ser levantados com o contador antes.

## Tailwind

`static/dist/styles.css` hoje é um CSS escrito à mão (fallback), reencodando as mesmas classes
que o Tailwind vai gerar (`.card`, `.btn-primary`, etc. — mesma paleta oliva/khaki do frontend
Vue atual). Quando Node/npm estiver disponível:

```bash
npm install
npm run build:css   # gera static/dist/styles.css de verdade a partir de static/src/styles.css
```

O caminho de saída é o mesmo — templates não precisam mudar.
