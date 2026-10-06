# Vettro — Sistema de Atendimento Veterinário a Domicílio (multi-tenant, para a Lume)

O sistema está em reescrita completa: a versão anterior (FastAPI + Vue, single-tenant) foi
removida do repositório — o código vivo agora é **só** `django_app/` (Django + django-tenants,
multi-tenant SaaS, server-rendered com HTMX/Alpine/Tailwind). Ver `django_app/README.md` pro
status detalhado de cada fase e `docs/` do plano completo.

## Identidade visual (Lume)
Cores medidas na identidade: verde oliva `#949C56`, verde claro `#E5E8C5`, marfim `#F5EFCB`,
amarelo `#EFC15A`, terroso `#C17D46`, texto/títulos verde escuro `#545936`. Tokens em
`static/dist/styles.css` (`--verde-oliva`, `--c-alerta`...) — nunca usar hex solto nos templates.
Tipografia: **Roca Two** (títulos, paga — arquivos em `static/fonts/`, woff2 p/ web e ttf p/ PDF;
sem eles cai na Fraunces SOFT) + **Livvic** (textos, OFL, já em `static/fonts/` e no PDF).

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
- Cadastrar/editar/excluir **insumos** e **tipos de cirurgia** (CirurgiaCategoria), e importar
  XML de NF-e (cria insumos): **só admin** (`admin_required`). Vet ainda faz entrada manual/ajuste.
- **Sem ícones/emojis na interface** (pedido do usuário, 2026-10) — rótulos só em texto.
- `motorista`: só Agenda.

Uma mesma pessoa (identidade global, `plataforma.Usuario`) pode ter papéis diferentes em
clínicas diferentes via `UsuarioClinica`. Cadastro de acesso novo é sempre por convite
(e-mail com link de uso único pra definir senha — admin nunca sabe a senha de ninguém).

## Módulos do sistema
1. **Tutores** — cadastro, busca, CPF, CEP autofill (ViaCEP), consentimento/exportação LGPD.
- **Telefones** (todos os cadastros): `apps/core/campos.py:TelefoneField` — "+55 (DD) 9 XXXX-XXXX"
  (celular, 9 obrigatório) ou "+55 (DD) XXXX-XXXX" (fixo); +55 pré-preenchido mas trocável.
  Máscara em `static/js/mascaras.js` (`data-mascara="telefone"`), validação em
  `core/validators.py:formatar_telefone`.
2. **Pacientes** — cadastro (perfil clínico/`CondicaoClinica` saiu do cadastro/edição/lista em
   2026-10), Ficha com abas: Ficha (dados + linha do tempo), Histórico, Atendimento (só o
   formulário novo — sem lista de consultas), Exames, Fotos, Receitas, Documentos, Vacinas,
   Anotações, Cobrança (admin only). **Cirurgias não tem aba**: entra por Atendimento →
   Procedimento cirúrgico. Clicar num item da linha do tempo abre o detalhe COMPLETO do
   registro (`pacientes:registro`, todos os campos + itens + cobrança + exames/fotos).
   Botão **Imprimir** no detalhe (`pacientes:registro_pdf`) e na aba Histórico
   (`pacientes:historico_pdf`, respeita o filtro da tela) — `apps/pacientes/pdf.py`.
   Exames e Fotos: histórico + "Anexar" com vínculo opcional a um atendimento
   (`Exame.atendimento` / `Foto.atendimento`, só do próprio paciente).
3. **Serviços / Procedimentos Cirúrgicos** — catálogo, preço por faixa de peso (P/M/G) nas
   cirurgias.
4. **Estoque** — ledger de movimentações estilo Protheus (SD1 entrada via XML de NF-e **ou**
   manual sem nota, SD2 saída, SD3 ajuste interno) — não é mais um contador simples.
   Unidades como a 1ª/2ª UM do Protheus: estoque, preço e consumo sempre na **unidade de uso**
   (`Insumo.unidade`: un, ml, comp...; aceita fração, ex. 2,5 ml); compra na **embalagem**
   (`embalagem` + `unidades_por_pacote` = conteúdo). Entrada manual e XML convertem embalagem →
   unidade de uso. Estoque baixo: `estoque_minimo` do produto ou, sem ele, < 3. Serviço pode ser
   cobrado por quantidade (`Servico.unidade_cobranca`, ex. oxigenoterapia por hora).
5. **Atendimentos** — grade com filtros (tipo, espécie, período). Tipo: Consulta, Retorno
   (vincula o nº do atendimento de origem), Ambulatorial, Emergência, Aplicação de medicação,
   Curativo, Vacinação (vacina do catálogo + dose 1/2/3/Anual + "revacinar em"; **sem plantão
   e sem serviços** — só vacina + insumos, também ignorados no servidor). Na Ficha, a
   aba 🩺 Atendimento abre 6 botões: Consulta (= ficha de anamnese), Vacina, Procedimento
   cirúrgico (aba Cirurgias), Retorno, Aplicação de medicação, Curativos. Lembrete de WhatsApp:
   24h, 5 ou 30 dias antes da revacinação/retorno. Código `#numero` sequencial por clínica. Gera
   Cobrança pendente automática (desde 2026-09, igual Anamnese/Cirurgia). Excluir estorna o
   estoque (SD3 `estorno_consumo`) e remove a cobrança se ainda pendente.
6. **Agenda** — calendário mensal, Consultórios/locais cadastráveis livremente com fechamento
   por dia ou turno (admin only), lembrete de WhatsApp 24h antes (backend trocável, provedor
   ainda não escolhido).
7. **Cobranças** (admin only) — manual ou automática (Anamnese/Cirurgia/Atendimento com itens
   faturáveis). Baixa manual com desconto opcional (R$ ou %) e motivo obrigatório; `total` é o
   valor cheio, `valor_pago` = total − desconto.
14. **Vendas** (admin/vet/atendente; módulo estoque) — venda de balcão sem paciente, nasce
   paga (não gera Cobrança), baixa SD2 `venda_produto` na hora, desconto R$/% com motivo,
   leitor de código de barras. Cancelar (admin only) estorna o estoque e mantém o registro.
- **Notas fiscais** (`apps/pagamentos/notas.py`): NFS-e sai ao receber uma Cobrança, NFC-e ao
  finalizar uma Venda (automático; botão "tentar de novo" se recusada). Backend trocável
  (`NOTA_FISCAL_BACKEND`); o padrão é `NotaFiscalSimulacaoBackend` — valida como o emissor real
  (CNPJ/razão social/cidade da clínica, NCM dos produtos), gera número/chave fictícios (chave
  começa com 99) e PDF "SIMULAÇÃO — SEM VALOR FISCAL". Focus NFe entra trocando o backend.
- **Novo atendimento**: `/atendimentos/novo/` sem `tipo` abre o hub (paciente + tipo); Consulta e
  Cirurgia levam à Ficha (cirurgia com seletor "Tipo de cirurgia" = CirurgiaCategoria).
- **Lembretes automáticos de WhatsApp** (`enviar_lembretes_whatsapp`, cron diário): agendamento
  de amanhã, próxima dose de vacina e data de retorno de consulta — `lembrete_dias_antes` dias
  antes; não envia se o paciente já voltou. Exige módulo da clínica + consentimento do tutor.
11. **Orçamentos** (admin/vet/atendente; módulo financeiro) — itens do catálogo ou livres, PDF
   com aviso de "valores de orçamento" + validade (padrão em ⚙️ Clínica).
12. **Receitas** (aba da Ficha, `pacientes_clinico`) — livre (texto), simples (medicamentos com
   uso/farmácia/concentração/**quantidade (obrigatória)**/periodicidade/período/obs) e controlada
   (= simples, mas **só 1 medicamento por receita**, PDF em 2 vias farmácia/tutor; exige CRMV).
   PDF no layout do modelo enviado pela clínica (`receita_controlada_amoxi_lilly_assinado.pdf`,
   `gerar_pdf(estilo="receita")`): cabeçalho emoldurado (logo à direita), título em caixa, blocos
   com título sublinhado **Dados do emitente** (nome, CRMV, MAPA, endereço, cidade/UF, telefones,
   data de emissão) → **Dados do tutor** (nome, CPF, RG, endereço, cidade/UF) → **Dados do
   animal** (nome, espécie, raça, sexo, idade, peso) → **Prescrição**; sem marca d'água; rodapé
   "Impresso em: … Por: <quem imprimiu> Pág. x / N". Controlada: "Farmácia veterinária ( )
   Farmácia Humana ( )" marcada pelos itens + quadro Identificação do comprador | do fornecedor
   (moldura dupla) fixo no pé de cada via + "1ª via - Farmácia / 2ª via - Paciente".
   Snapshots na Receita: tutor CPF/RG/cidade, sexo do animal, MAPA do vet.
   Assinatura: simples/livre saem com a **imagem da assinatura do cadastro** do vet; a
   **controlada sai SEMPRE sem a imagem** (assinatura manual obrigatória — `com_imagem=False`).
13. **Documentos** — modelos editáveis por clínica com variáveis `{paciente}`,
   `{tutor}`... (7 modelos padrão na migração `documentos/0002`), emitidos por paciente.
   **Menu Documentos (lista geral, modelos, excluir emitido): só admin.** Vet emite, vê e
   imprime pela aba Documentos da Ficha.
- **PDFs** (`apps/core/pdf.py`, ReportLab): cabeçalho (logo da clínica no canto **superior
  direito** em todo documento) + marca d'água da clínica
  (`core.ConfiguracaoClinica`, admin em ⚙️ Clínica) + assinatura/CRMV do
  `core.PerfilProfissional` (👤 Meu perfil, ou admin em 🔑 Usuários).
- **Perfil profissional** (`core.PerfilProfissional`, por clínica): nome, CRMV/UF, assinatura,
  telefone de contato, endereço (CEP com autofill ViaCEP, rua, número, complemento, bairro,
  cidade, UF) e **data de admissão — só o admin edita** (`PerfilProfissionalAdminForm`).
8. **Usuários** (admin only, por clínica) — adiciona por e-mail, reaproveita identidade global
   se a pessoa já tiver conta em outra clínica.
10. **Lembretes** (admin/vet/atendente; exige módulo `modulo_whatsapp_lembrete` da clínica) —
   texto livre por WhatsApp para tutores selecionados, só com `consentimento_whatsapp` (LGPD).
   Usa `Tutor.tel` (WhatsApp); `Tutor.tel2` é o outro telefone.
9. **Auditoria** (admin only) — login, criar/atualizar/excluir/exportar de Tutor/Paciente.

## Regras de negócio fixas (não mudar sem avisar)
- Plantão: **+50%** só sobre serviços, nunca sobre insumos (Anamnese/Atendimento; removido da
  Cirurgia em 2026-10 a pedido do usuário, junto com Deslocamento e Clínica/local).
- Faixas de peso cirurgia: **P** &lt;10kg, **M** 10–25kg, **G** &gt;25kg.
- Estoque baixo: qtd &lt; 3. Validade "vencendo": até 60 dias.
- Rate limit de login: 5 tentativas / 15 min.
- Senha: mín. 8 caracteres, letras e números.

## Fora de escopo por ora
- **Pagamentos/Fiscal** (TEF + Focus NFe) e **Configurações fiscais da clínica**: bloqueados
  por decisões externas (provedor de TEF — SiTef/PayGo —, conta Focus NFe, CNPJ/inscrições/
  certificado digital reais). Arquitetura já desenhada, aguardando essas contas.
- **Migração de dados**: não há nenhuma clínica rodando em produção ainda — não é necessária.
