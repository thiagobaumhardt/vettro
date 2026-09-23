# Vettro — Sistema de Atendimento Veterinário a Domicílio

## Tecnologia
- **Backend:** FastAPI + SQLAlchemy + Alembic, Python 3.12 (`backend/`)
- **Banco de dados:** PostgreSQL
- **Frontend:** Vue 3 + Vite (`frontend/`), consumindo a API REST em `/api/*`
- **Autenticação:** JWT (Bearer token), papéis `admin` e `vet`
- **Dev local:** `docker compose up` sobe Postgres (5432), backend com reload (8000) e o dev
  server do Vite (5173, proxy `/api` → backend)
- **Produção:** `Dockerfile.prod` builda o frontend e serve tudo (API + estático) num único
  container FastAPI — sem CORS, ideal para Railway/Render com Postgres gerenciado

### Primeira execução (dev local)
```
docker compose up -d
docker compose exec backend alembic upgrade head   # aplica a migration já versionada em backend/alembic/versions/
docker compose exec backend python -m app.seed      # cria o admin inicial (ver backend/.env.example) — idempotente
```
Se o schema mudar (novo campo/tabela em `models.py`), gere uma nova revision com
`docker compose exec backend alembic revision --autogenerate -m "descrição"` e rode `alembic upgrade head` de novo.

Serviços: frontend em http://localhost:5173, API em http://localhost:8000 (docs em `/docs`).

## Deploy (Railway ou Render)

O projeto já está pronto para deploy via `Dockerfile.prod` (build multi-stage: builda o Vue e
serve tudo — API + estático — num único container FastAPI, sem CORS). Testado localmente de
ponta a ponta: build, migrations, seed idempotente, SPA fallback (rotas do Vue Router
sobrevivem a refresh) e 404 correto para rotas `/api/*` inexistentes.

- **Railway**: `railway.json` já configura o build (`Dockerfile.prod`) e o healthcheck
  (`/health`). Basta conectar o repo, adicionar um plugin PostgreSQL e definir as env vars
  abaixo — Railway injeta `DATABASE_URL` automaticamente ao linkar o Postgres ao serviço.
- **Render**: `render.yaml` é um Blueprint completo (web service + Postgres gerenciado com
  backup). Use "New +" → "Blueprint" apontando para o repo.

**Variáveis de ambiente obrigatórias em produção** (ver `backend/.env.example`):
- `DATABASE_URL` — gerada automaticamente pela plataforma ao linkar o Postgres (aceita tanto
  `postgres://` quanto `postgresql://`, o backend normaliza para o driver psycopg)
- `JWT_SECRET` — troque o valor padrão (o app loga um aviso no startup se detectar o default)
- `ADMIN_EMAIL` / `ADMIN_SENHA` — credenciais do admin criado pelo seed no primeiro deploy;
  troque a senha padrão
- `CORS_ORIGINS` — pode ficar `*` (o frontend é servido pelo mesmo domínio da API em produção)

`$PORT` é respeitado automaticamente (a plataforma injeta a porta; o `CMD` do `Dockerfile.prod`
usa `${PORT:-8000}`).

## Autenticação e papéis
- `admin` (e-mail da clínica): acesso a todos os módulos, incluindo **Cobranças** (faturamento).
- `vet` (login nominal de cada veterinária, criado pelo admin em 🔑 Usuários): acesso a todos os
  módulos clínicos, mas **sem acesso ao módulo de Cobranças/faturamento**.
- Login em `/login`; token JWT válido por `JWT_EXPIRA_HORAS` (padrão 8h).

## Segurança e LGPD
- **Rate limiting no login**: bloqueia por 15 min após 5 tentativas erradas (IP + e-mail).
- **Headers de segurança** (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, `Strict-Transport-Security`) em todas as respostas da API.
- **Validação de CPF** (dígito verificador) e **política de senha** (mín. 8 caracteres, letras
  e números) para usuários.
- **Limite de tamanho de upload reforçado no servidor** (não só no navegador): fotos 3–4MB,
  exames PDF 5MB.
- **Trilha de auditoria** (`audit_log` / módulo 🛡️ Auditoria, admin only): login, criação,
  edição e exclusão de tutores/pacientes, com usuário, IP e timestamp.
- **Consentimento LGPD** por tutor (`consentimento_dados` + timestamp) e **exportação de dados**
  do titular (botão "Exportar dados (LGPD)" na ficha do tutor, admin only) — direito de
  acesso/portabilidade.

## Módulos do sistema

### 1. Tutores
- Cadastro completo (nome, telefone, e-mail, CPF, endereço, observações) com busca
- Cada tutor lista os animais vinculados

### 2. Pacientes
- Cadastro: nome do animal, espécie (Cão/Gato/Outro), raça (lista por espécie), peso, data de
  nascimento, tutor vinculado, foto de perfil, observações
- Ficha do paciente com sub-abas:
  - **Ficha** — dados básicos e banner do tutor
  - **Anamnese** — registro de atendimento com avaliação física completa (FC, FR, PA, temperatura,
    hidratação, mucosas, linfonodos), seleção de serviços/insumos usados, plantão (+50% nos
    serviços), histórico expansível
  - **Cirurgias** — procedimento cirúrgico com valor calculado por faixa de peso do paciente
    (até 10kg / 10–25kg / acima de 25kg), acréscimos de plantão (+50%) e deslocamento outra
    cidade (+R$ 50)
  - **Exames** — upload de PDFs (máx. 5MB), armazenados como base64
  - **Fotos** — upload de imagens (máx. 4MB), galeria com lightbox
  - **Cobrança** (admin only) — cobranças geradas manualmente ou automaticamente a partir de
    anamnese/cirurgia, com status pendente/pago
  - **Anotações** — notas livres com título opcional

### 3. Serviços
- Nome e valor (R$); CRUD completo

### 4. Procedimentos Cirúrgicos (catálogo)
- Nome + valor por faixa de peso (até 10kg / 10–25kg / acima 25kg); CRUD completo

### 5. Insumos / Estoque
- Nome, categoria, valor unitário, quantidade em estoque; CRUD completo
- Estoque debitado automaticamente ao registrar atendimento/anamnese/cirurgia/cobrança
- Alerta de estoque baixo (< 3 unidades) e sem estoque (0 unidades)

### 6. Atendimentos (módulo standalone)
- Vincula paciente, data/hora, serviços, insumos (desconta estoque), plantão, observações
- Exibe valor total (serviços + insumos [+ 50% se plantão])

### 7. Agenda
- Calendário mensal com indicador de dias com agendamento
- Agendamento com paciente cadastrado ou avulso (nome livre)
- Status: agendado → confirmado/realizado/cancelado; ações rápidas de reagendar
- Lista de "Próximos agendamentos"

### 8. Usuários (admin only)
- CRUD dos logins das veterinárias (papel `vet`) e de outros admins
