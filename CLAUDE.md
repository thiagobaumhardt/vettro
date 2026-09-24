# Vettro — Sistema de Atendimento Veterinário a Domicílio (multi-tenant, para a Lume)

O sistema está em reescrita completa: a versão anterior (FastAPI + Vue, single-tenant) foi
removida do repositório — o código vivo agora é **só** `django_app/` (Django + django-tenants,
multi-tenant SaaS, server-rendered com HTMX/Alpine/Tailwind). Ver `django_app/README.md` pro
status detalhado de cada fase e `docs/` do plano completo.

## Tecnologia
- **Backend/Frontend:** Django 5 + django-tenants (schema-per-tenant) + HTMX + Alpine.js +
  Tailwind, tudo em `django_app/` — sem API JSON separada, sem SPA.
- **Banco de dados:** PostgreSQL (schema `public` = identidade global/registro de clínicas;
  1 schema por clínica = dados clínicos isolados).
- **Autenticação:** sessão Django (cookie), papéis por clínica: `admin`, `vet`, `atendente`,
  `motorista` (ver `apps/core/decorators.py:PERMISSOES_POR_PAPEL`).
- **Multi-tenant:** domínio único `www.vettro.com.br`, clínica resolvida no login (não por
  subdomínio) — `apps/contas/middleware.py:TenantFromSessionMiddleware`.
- **Deploy alvo:** KingHost (Python/Django hosting) — configuração ainda pendente de
  confirmação de versão de Python suportada (Django 5 exige 3.10+).

## Primeira execução (dev local)
Ver `django_app/README.md` — resumo:
```bash
cd django_app
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
docker compose up -d
python manage.py migrate_schemas --shared
python manage.py createcachetable
python manage.py createsuperuser --email plataforma@vettro.com.br
python manage.py runserver
```
Depois, em `/plataforma/`, provisione a primeira clínica.

## Autenticação e papéis (por clínica, não globais)
- `admin`: acesso total, incluindo Cobranças, Usuários, Auditoria, Consultórios.
- `vet`: todo módulo clínico, sem Cobranças/Usuários/Auditoria.
- `atendente`: Tutores/Pacientes/Agenda, sem abas clínicas (Anamnese/Cirurgia/Exames/Fotos).
- `motorista`: só Agenda.

Uma mesma pessoa (identidade global, `plataforma.Usuario`) pode ter papéis diferentes em
clínicas diferentes via `UsuarioClinica`. Cadastro de acesso novo é sempre por convite
(e-mail com link de uso único pra definir senha — admin nunca sabe a senha de ninguém).

## Módulos do sistema
1. **Tutores** — cadastro, busca, CPF, CEP autofill (ViaCEP), consentimento/exportação LGPD.
2. **Pacientes** — cadastro, Ficha com abas: Ficha, Anamnese, Cirurgias, Exames, Fotos,
   Cobrança (admin only), Anotações.
3. **Serviços / Procedimentos Cirúrgicos** — catálogo, preço por faixa de peso (P/M/G) nas
   cirurgias.
4. **Estoque** — ledger de movimentações estilo Protheus (SD1 entrada via XML de NF-e **ou**
   manual sem nota, SD2 saída, SD3 ajuste interno) — não é mais um contador simples.
5. **Atendimentos** — módulo avulso, não gera Cobrança automática (assimetria proposital).
6. **Agenda** — calendário mensal, Consultórios/locais cadastráveis livremente com fechamento
   por dia ou turno (admin only), lembrete de WhatsApp 24h antes (backend trocável, provedor
   ainda não escolhido).
7. **Cobranças** (admin only) — manual ou automática (Anamnese/Cirurgia com itens faturáveis).
8. **Usuários** (admin only, por clínica) — adiciona por e-mail, reaproveita identidade global
   se a pessoa já tiver conta em outra clínica.
9. **Auditoria** (admin only) — login, criar/atualizar/excluir/exportar de Tutor/Paciente.

## Regras de negócio fixas (não mudar sem avisar)
- Plantão: **+50%** só sobre serviços/procedimentos, nunca sobre insumos.
- Cirurgia "outra cidade": **+R$50 fixo**, acumulável com plantão.
- Faixas de peso cirurgia: **P** &lt;10kg, **M** 10–25kg, **G** &gt;25kg.
- Estoque baixo: qtd &lt; 3. Validade "vencendo": até 60 dias.
- Rate limit de login: 5 tentativas / 15 min.
- Senha: mín. 8 caracteres, letras e números.

## Fora de escopo por ora
- **Pagamentos/Fiscal** (TEF + Focus NFe) e **Configurações fiscais da clínica**: bloqueados
  por decisões externas (provedor de TEF — SiTef/PayGo —, conta Focus NFe, CNPJ/inscrições/
  certificado digital reais). Arquitetura já desenhada, aguardando essas contas.
- **Migração de dados**: não há nenhuma clínica rodando em produção ainda — não é necessária.
