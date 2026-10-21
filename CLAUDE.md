# Vettro — Sistema de Atendimento Veterinário a Domicílio (multi-tenant, para a Lume)

O sistema está em reescrita completa: a versão anterior (FastAPI + Vue, single-tenant) foi
removida do repositório — o código vivo agora é **só** `django_app/` (Django + django-tenants,
multi-tenant SaaS, server-rendered com HTMX/Alpine/Tailwind). Ver `django_app/README.md` pro
status detalhado de cada fase e `docs/` do plano completo.

## Identidade visual (Lume)
Cores medidas na identidade: verde oliva `#949C56`, verde claro `#E5E8C5`, marfim `#F5EFCB`,
amarelo `#EFC15A`, terroso `#C17D46`, texto/títulos verde escuro `#545936`. Tokens em
`static/dist/styles.css` (`--verde-oliva`, `--c-alerta`...) — nunca usar hex solto nos templates.
Interface (2026-10): menu lateral **preto** (`--sidebar-bg`), botões primários **verde mais claro**
(`--primary` #7A8240, texto branco), visual reto (`border-radius: 0` global) — única exceção: botões
do hub de novo atendimento (`.hub-tipo`, 8px).
Tipografia: **Roca Two** (títulos, paga — arquivos em `static/fonts/`, woff2 p/ web e ttf p/ PDF;
sem eles cai na Fraunces SOFT) + **Livvic** (textos, OFL, já em `static/fonts/` e no PDF).

## Tecnologia
- **Backend/Frontend:** Django 5 + django-tenants (schema-per-tenant) + HTMX + Alpine.js +
  Tailwind, tudo em `django_app/` — sem API JSON separada, sem SPA.
- **Banco de dados:** PostgreSQL (schema `public` = identidade global/registro de clínicas;
  1 schema por clínica = dados clínicos isolados).
  Nomes de tabela: padrão Django (`app_modelo`), exceto as renomeadas para o nome de negócio
  (padrão MKSaúde) via `Meta.db_table`: `agenda` (Agendamento) e `atendimentos` (Atendimento).
- **Autenticação:** sessão Django (cookie), papéis por clínica: `admin`, `vet`, `atendente`,
  (ver `apps/core/decorators.py:PERMISSOES_POR_PAPEL`).
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
- `atendente` (rótulo **Recepção**): Tutores/Pacientes/Agenda/Vendas + **receber pagamentos**
  (seção `recepcao`), sem abas clínicas (Anamnese/Cirurgia/Exames/Fotos).
- Cadastrar/editar/excluir **insumos** e **tipos de cirurgia** (CirurgiaCategoria), e importar
  XML de NF-e (cria insumos): **só admin** (`admin_required`). Vet ainda faz entrada manual/ajuste.
- **Sem ícones/emojis na interface** (pedido do usuário, 2026-10) — rótulos só em texto.
- (Perfil `motorista` removido em 2026-10 — quem tinha virou Recepção.)

Uma mesma pessoa (identidade global, `plataforma.Usuario`) pode ter papéis diferentes em
clínicas diferentes via `UsuarioClinica`. Cadastro de acesso novo é sempre por convite
(e-mail com link de uso único pra definir senha — admin nunca sabe a senha de ninguém).

## Módulos do sistema
1. **Tutores** — cadastro, busca, CPF, CEP autofill (ViaCEP), consentimento/exportação LGPD.
   Consentimento de lembrete por WhatsApp já vem **marcado** no cadastro de tutor novo (desmarcável).
- **Telefones** (todos os cadastros): `apps/core/campos.py:TelefoneField` — "+55 (DD) 9 XXXX-XXXX"
  (celular, 9 obrigatório) ou "+55 (DD) XXXX-XXXX" (fixo); +55 pré-preenchido mas trocável.
  Máscara em `static/js/mascaras.js` (`data-mascara="telefone"`), validação em
  `core/validators.py:formatar_telefone`.
2. **Pacientes** — cadastro (perfil clínico/`CondicaoClinica` saiu do cadastro/edição/lista em
   2026-10), Ficha com abas: Ficha (dados + linha do tempo), Histórico, Atendimento (só o
   formulário novo — sem lista de consultas), Exames, Fotos, Receitas, Documentos, Vacinas,
   Anotações, Cobrança (admin only), **Peso** (histórico `Pesagem` + gráfico; `Paciente.peso` = pesagem
   mais recente, mostrada no cabeçalho com a data; peso **não** fica no cadastro/edição do paciente — só pela aba Peso; botão Gerar PDF com gráfico). **Cirurgias não tem aba**: entra por Atendimento →
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
   Gestão estilo SimplesVet (2026-10, abas em `estoque/_subnav.html`). **Sem fornecedores e sem
   pedidos de compra** (decisão da clínica, 2026-10: compras avulsas — entram por Entrada manual
   ou XML da NF-e; o emitente fica só na observação do movimento; não reintroduzir).
   **Saídas** (consumo interno, perda de validade, avaria, doação, devolução de compra + motivos
   livres + resumo), **Inventário** (contagem por código de barras/câmera, divergências → SD3
   `inventario_*`), **Análise** (sugestão de compra = consumo 90 dias × frequência de compras,
   excedentes, parados 90+ dias, capital parado; só admin) e **Etiquetas** Pimaco (PDF, EAN-13
   interno com prefixo 2).
   Código em `apps/estoque/{operacoes,etiquetas,views_gestao}.py`.
   **Dados fiscais do produto** (venda no balcão/NFC-e): NCM, **CEST** (7 dígitos, obrigatório com
   ICMS-ST — a NFC-e recusa sem ele), origem, ICMS-ST e **PIS/COFINS monofásico** (sai com CST 04;
   os demais, CST 49 no Simples / 01 no Presumido/Real) — tudo lido do XML da nota de compra
   (CST de PIS 02/03/04 = monofásico). CFOP/CSOSN vêm da regra da clínica (`apps/estoque/fiscal.py`).
   Guia do contador (Fox Contábil, 2026-10): **código interno** `codigo` (produto 001, 002...; serviço
   SERV001...; gerado no `save`, vai no cProd/NFS-e), **unidade na nota** (`unidade_venda`, UN/CX/FR;
   vazio = derivada da unidade de uso), **GTIN** só se GS1 válido — senão "SEM GTIN" (etiqueta interna
   prefixo 2 também), **finalidade** (uso interno / revenda / ambos: Vendas só lista revenda+ambos,
   atendimentos só uso interno+ambos; medicamento aplicado no atendimento é consumo, não venda).
5. **Atendimentos** — grade com filtros (tipo, espécie, período). Tipo: Consulta, Retorno
   (vincula o nº do atendimento de origem), Ambulatorial, Emergência, Aplicação de medicação,
   Curativo, Vacinação (vacina do catálogo + dose 1/2/3/Anual + "revacinar em"; **sem plantão
   e sem serviços** — só vacina + insumos, também ignorados no servidor). Na Ficha, a
   aba 🩺 Atendimento abre 6 botões: Consulta (= ficha de anamnese), Vacina, Procedimento
   cirúrgico (aba Cirurgias), Retorno, Aplicação de medicação, Curativos. Lembrete de WhatsApp:
   24h, 5 ou 30 dias antes da revacinação/retorno. Código `numero` sequencial por clínica. Gera
   Cobrança pendente automática (desde 2026-09, igual Anamnese/Cirurgia). Campo opcional
   **Orçamento de origem** (`Atendimento.orcamento`, só orçamento do paciente ou do tutor dele).
   Número exibido sem "#". Hub de novo atendimento não pede paciente (só Consulta/Cirurgia, ao clicar). Excluir estorna o
   estoque (SD3 `estorno_consumo`) e remove a cobrança se ainda pendente.
6. **Agenda** (estilo SimplesVet, 2026-10) — **organizada por consultório** (não por usuário/
   veterinário — decisão da clínica, 2026-10; sem campo Veterinário no agendamento nem nos
   bloqueios): visões **Dia** (uma coluna por consultório + "Sem consultório" se houver),
   **Semana**, **Mês** e **Ordem de chegada** (aguardando → em atendimento → finalizado, com tempo
   de espera/atendimento e médias do dia e 30 dias). Filtros no topo: Consultório, Serviço,
   Status, Tipo de atendimento, Data. Agendamento com consultório, duração (soma das
   `Servico.duracao_min`), status "Agendado" ao criar (**sem etapa de confirmação** — removida em 2026-10), **tipo de atendimento
   como etiqueta de cor** (Consulta, Retorno, Ambulatorial, Emergência, Vacinação, Aplicação de
   medicação, Curativo, Exame), encaixe (permite conflito). Conflito de horário = mesmo consultório.
   **Sem recorrência, sem comunicados e sem campo Status no formulário** (nasce "agendado";
   status muda só pelas ações do detalhe). **Sem painel de horários livres** (removido a pedido, 2026-10). Bloqueios (admin only) da clínica ou
   de um consultório, por dia, turno ou horário exato (almoço). Faixa da grade em ⚙️ Clínica
   (`agenda_hora_inicio/fim/intervalo_min`). Lembrete de WhatsApp 24h antes.
   Qualquer papel agenda e mexe nos agendamentos; **fechar a agenda (bloqueios) e Consultórios: só admin**.
   Agendamento: seção **Serviços** (só `Servico.na_agenda=True`) + seção **Exames** (tabela própria
   `tipos_exames` = `financeiro.TipoExame`: nome, duração, valor opcional, ativo — cadastrada em Serviços
   → Tipos de exame; snapshot em `Agendamento.exames`). Duração = soma de serviços + exames (exibida
   como "2h"/"1h 30m" pelo filtro `duracao` em `core/templatetags/formatos.py`). Anexar exame na Ficha
   exige o tipo (`Exame.tipo`).
   Regras em `apps/agenda/services.py`.
   Cor de cada tipo de atendimento (`--et-<tipo>` em styles.css) é a mesma na Agenda e no hub de
   novo atendimento (8 botões coloridos, 2 fileiras de 4): vacinação laranja, cirurgia azul, retorno roxo...
   O agendamento não tem mais campo de tipo: a **cor vem do serviço** (`Servico.tipo`, editável em Serviços;
   snapshot `tipo` em `Agendamento.servicos`; `Agendamento.tipo_cor`) — usada só no formulário/catálogo.
   **Na grade a cor é do STATUS** (fundo branco; borda/rótulo: agendado azul, chegou amarelo, em
   atendimento verde (pulsando), atendido cinza, cancelado vermelho — `--st-*` em styles.css).
   **Sem status "Faltou"**: cancelar exige **motivo** (lista `MOTIVOS_CANCELAMENTO`, ex. "Faltou (não
   compareceu)", ou texto livre) e libera o horário. **Atrasado** (laranja, pulsando) é calculado, não
   gravado: status Agendado e já passou do horário (`Agendamento.atrasado` / `status_exibido`).
   Cancelados não ocupam a grade: ficam no botão "Cancelados (N)" acima dela. **Arrastar** um bloco
   (Agendado/Aguardando) pra outro horário/consultório (Dia) ou dia (Semana) abre janela de confirmação
   → `agenda:mover` (`services.mover`: respeita bloqueio; conflito só como encaixe).
   Botão **Locais** escolhe quais consultórios/salas aparecem (vários; guardado na sessão `agenda_ver`).
   Locais da Lume: Bloco Cirúrgico, Consultório Franciele, Consultório Luisa, Sala de Exames.
- **Recepção / receber pagamento** (2026-10, `apps/financeiro/{recepcao,views_recepcao,urls_recepcao}.py`):
  o vet clica **Finalizar atendimento** (Atendimento, Consulta/Anamnese, Cirurgia) → nasce a Cobrança
  pendente → a tela inicial de quem tem `recepcao` (admin, Recepção) lista "Aguardando pagamento"
  por tutor → **Receber pagamento**: escolhe as cobranças, desconto R$/% com motivo, até 4 formas
  (dinheiro, Pix, débito, crédito com parcelas — ex. 2 cartões; só dinheiro dá troco), CPF na nota
  (vem do tutor, editável) e emitir NFS-e → `Recebimento` + `PagamentoRecebimento`, desconto rateado
  nas cobranças, **uma NFS-e por recebimento**. Maquininha não integrada (confirmação manual).
  Aparece na aba **Cobranças** da tela do Tutor (`?aba=cobrancas`) e em "Recebidos hoje".
7. **Cobranças** (admin only) — manual ou automática (Anamnese/Cirurgia/Atendimento com itens
   faturáveis). Baixa manual com desconto opcional (R$ ou %) e motivo obrigatório; `total` é o
   valor cheio, `valor_pago` = total − desconto.
14. **Vendas** (admin/vet/atendente; módulo estoque) — **simples por decisão da clínica (2026-10)**:
   vende produto do estoque e gera a nota (NFC-e) e pronto. Cliente opcional: no balcão pergunta o
   **CPF na nota** — se for de um Tutor cadastrado liga a venda a ele (`Venda.tutor`), senão a venda
   guarda só o CPF (`Venda.cliente_cpf`, vai pra NFC-e). Venda de balcão sem paciente, nasce
   paga (não gera Cobrança), baixa SD2 `venda_produto` na hora, desconto R$/% com motivo,
   leitor de código de barras. Cancelar (admin only) estorna o estoque e mantém o registro.
   **Cartão/Pix = maquininha integrada (TEF)** — exigência da NFC-e no RS (Decreto 56.670): a venda
   nasce `pagamento_status="aguardando"`, o total vai pra maquininha (`TransacaoTEF`), a tela
   `vendas:pagamento` consulta a cada 2s; aprovado → paga → NFC-e com bandeira/autorização/CNPJ da
   credenciadora (`tpIntegra=1`; sem isso a NFC-e de cartão/Pix é recusada). Recusa: cobrar de novo,
   trocar a forma (dinheiro fecha na hora) ou desistir (qualquer papel, só se não paga). Cancelar venda
   paga estorna na maquininha. Backend trocável (`TEF_BACKEND`, `apps/pagamentos/tef.py`); padrão é
   sandbox (aprova em ~4s, valor terminado em ,99 é negado). Dinheiro continua nascendo paga.
   (PDV completo com caixa/comissão/kits/pacotes foi feito e removido a pedido — não reintroduzir.)
- **Notas fiscais** (`apps/pagamentos/notas.py`): NFS-e sai ao receber uma Cobrança, NFC-e ao
  finalizar uma Venda (automático; botão "tentar de novo" se recusada). Backend trocável
  (`NOTA_FISCAL_BACKEND`); o padrão é `NotaFiscalSimulacaoBackend` — valida como o emissor real
  (CNPJ/razão social/cidade da clínica, NCM dos produtos), gera número/chave fictícios (chave
  começa com 99) e PDF "SIMULAÇÃO — SEM VALOR FISCAL". Focus NFe entra trocando o backend.
  NFS-e: código de tributação nacional **050202** (subitem 5.02) e código municipal = padrão em
  ⚙️ Clínica, exceção por serviço no catálogo. XML autorizado e de cancelamento guardados na nota
  (`xml`/`xml_cancelamento`); **Contabilidade** (`notas:contabilidade`, admin, link em ⚙️ Clínica):
  ZIP do mês com XMLs por pasta + `relatorio_itens.csv` separando serviços × vendas
  (`apps/pagamentos/contabilidade.py`).
- **Novo atendimento**: `/atendimentos/novo/` sem `tipo` abre o hub (paciente + tipo); Consulta e
  Cirurgia levam à Ficha (cirurgia com seletor "Tipo de cirurgia" = CirurgiaCategoria).
- **Lembretes automáticos de WhatsApp** (`enviar_lembretes_whatsapp`, cron diário): agendamento
  de amanhã, próxima dose de vacina e data de retorno de consulta — `lembrete_dias_antes` dias
  antes; não envia se o paciente já voltou. Exige módulo da clínica + consentimento do tutor.
- **WhatsApp SaaS** (`apps/whatsapp`, 2026-10): Cloud API oficial da Meta, Vettro = Tech Provider
  (1 app Meta); cada clínica conecta o próprio número em ⚙️ Clínica → WhatsApp (admin) via
  Embedded Signup — número novo ou coexistência com o app WhatsApp Business. `ConexaoWhatsApp`
  (schema public, token cifrado) + templates do Vettro criados na WABA da clínica
  (`modelos.py`: lembretes = utility, aviso = marketing). Webhook único `/whatsapp/webhook/`
  (URLconf público): status, respostas (menu Lembretes; "SAIR" revoga consentimento) e
  aprovação de template. Log em `lembretes.MensagemWhatsApp`. Meta cobra direto da clínica.
  Conexão manual pela plataforma em `/plataforma/` → Conexões de WhatsApp. **Hoje (só a Lume):
  fase 1 = conexão manual, app Meta no portfólio da Lume, sem Tech Provider; Embedded Signup
  fica para a fase 2** — passo a passo em `docs/whatsapp-meta.md`.
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
- **Provedor real de TEF e Focus NFe** e **Configurações fiscais da clínica**: bloqueados
  por decisões externas (contrato com a maquininha integrada, conta Focus NFe, CNPJ/inscrições/
  certificado digital reais). Fluxo da venda com maquininha já pronto em sandbox; falta o backend real.
- **Migração de dados**: não há nenhuma clínica rodando em produção ainda — não é necessária.
