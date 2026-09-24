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
- ⏳ Fases 5-6: Configurações fiscais da clínica, Pagamentos (TEF+Focus NFe), deploy KingHost
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

`apps/pagamentos` e `apps/configuracoes` (Fases 5-6, ainda não implementados) ficam pra depois
por dependerem de decisões externas (provedor de TEF/Focus NFe, dados fiscais reais).

## Tailwind

`static/dist/styles.css` hoje é um CSS escrito à mão (fallback), reencodando as mesmas classes
que o Tailwind vai gerar (`.card`, `.btn-primary`, etc. — mesma paleta oliva/khaki do frontend
Vue atual). Quando Node/npm estiver disponível:

```bash
npm install
npm run build:css   # gera static/dist/styles.css de verdade a partir de static/src/styles.css
```

O caminho de saída é o mesmo — templates não precisam mudar.
