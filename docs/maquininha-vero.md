# Maquininha integrada — Vero Cliente PDV

Integração da venda de balcão (cartão/Pix) com a Smart POS da Vero (Banrisul), exigida
pela NFC-e no RS (Decreto 56.670, `tpIntegra=1`). Baseado no **Guia de Integração 1.14 —
Vero Cliente PDV** (out/2025). Código: `apps/pagamentos/tef.py:VeroClientePDVBackend`.

## Como funciona

```
Vettro (nuvem) ──POST JSON──► Servidor PDV da Vero (pdv.verostore.com.br) ──► app Vero Cliente PDV na maquininha
      ▲                                                                                │
      └──────────── consulta a cada 5s: Aprovada + bandeira, NSU, autorização ◄────────┘
```

Sem USB, sem programa no computador da recepção. A cobrança abre sozinha na maquininha
da clínica porque o Vettro envia o token dela no campo `group`.

| Forma no Vettro | Método Vero | Observação |
|---|---|---|
| Débito | `DEBIT_UNDEFINED` | Aceita bandeira **e Banricompras**; a modalidade Banricompras é escolhida na maquininha |
| Crédito 1x | `CREDIT_1X` | |
| Crédito 2x+ | `CREDIT_NX_STORE` | Parcelado lojista (sem juros pro cliente) |
| Pix | `QRCODE_VERO_X` | QR code na tela da maquininha |
| Estorno (cancelar venda paga) | `CANCEL` + NSU | Abre na maquininha onde foi pago; **o operador conclui lá** |

Status da Vero → Vettro: Disponível/Em andamento = aguardando; Aprovada = aprovado;
Declinada/Não aprovada = negado; Cancelada (PDV/Operador) = cancelado; Falha = erro.

## Passo a passo para ligar

1. **Cadastrar a integração Vettro na Vero** (veroparadesenvolvedores@banrisulpagamentos.com.br)
   e receber o `pdvToken`. É **um token só para o Vettro inteiro** — vale para todas as clínicas.
2. **Confirmar o CNPJ da credenciadora** que vai na NFC-e. O padrão no código é o da
   Banrisul Cartões S.A. (`92.934.215/0001-06`) — confirmar com a Vero/contador.
3. No servidor, configurar:
   ```
   TEF_BACKEND=apps.pagamentos.tef.VeroClientePDVBackend
   VERO_PDV_TOKEN=<token da integração>
   VERO_CNPJ_CREDENCIADORA=<confirmado no passo 2>
   ```
4. **Na maquininha da clínica:** instalar o app **Vero Cliente PDV** pela Vero Store e abrir.
   Ele mostra o **token do terminal**.
5. **No Vettro, em Clínica:** conferir o CNPJ (o mesmo da maquininha) e preencher
   **Token da maquininha**. Ao salvar, o Vettro vincula a maquininha (`apiDeviceLink`).
6. Fazer uma venda de teste de R$ 1,00 no débito, no crédito e no Pix, e cancelar uma delas.

## Limites conhecidos

- **Estorno:** o Vettro só abre o estorno na maquininha. Se ninguém concluir lá, o
  valor não volta ao cliente — a tela avisa ao cancelar a venda.
- **Cancelar cobrança já iniciada** (cliente já passou o cartão) não é possível pela API;
  cancela-se na maquininha.
- **Servidor de contingência** (IP da maquininha no Wi-Fi) não é usado: exige estar na
  mesma rede, e o Vettro roda na nuvem.
- Uma maquininha por clínica (`ConfiguracaoClinica.tef_terminal_token`). Mais de uma
  maquininha = escolher o terminal na hora de cobrar (o `terminal_codigo` já existe no fluxo).
