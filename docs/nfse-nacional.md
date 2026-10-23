# NFS-e direto no Emissor Nacional (gov.br/nfse)

A nota de serviço sai direto no **Emissor Nacional da NFS-e**, sem intermediário pago
(Focus etc.). Cachoeira do Sul/RS (IBGE 4303004) usa o padrão nacional, obrigatório
para o Simples a partir de 01/11/2026.
Código: `apps/pagamentos/nfse_nacional.py`.

## Como funciona

```
Recebimento/Cobrança paga
  → Vettro monta a DPS (leiaute 1.01) e assina com o certificado A1 da clínica
  → POST {"dpsXmlGZipB64": ...} em sefin.nfse.gov.br/SefinNacional/nfse (TLS mútuo, mesmo certificado)
  ← chave de acesso (50 dígitos) + XML da NFS-e (número dado pelo Emissor Nacional)
```

- **Liga sozinho:** clínica **com** certificado cadastrado em Clínica → Emissor Nacional;
  **sem** certificado → continua a simulação. Nada a configurar no servidor.
- **Ambiente** (em Clínica): *Homologação* = produção restrita do governo, nota de teste
  sem valor fiscal (aparece como "HOMOLOGAÇÃO" na tela e no PDF). *Produção* = nota real.
- **Número da DPS:** série + sequência do Vettro (`nfse_serie`, `nfse_ultimo_dps`).
  O número da NFS-e é o Emissor Nacional que dá.
- **Sem nota em dobro:** se a resposta não chegar (queda, timeout), a nota fica "não
  autorizada" guardando o Id da DPS. Ao clicar em "tentar de novo", o Vettro consulta essa
  DPS (`GET /dps/{id}`) antes de mandar outra.
- **Uma NFS-e = um código de tributação.** Se os serviços do recebimento tiverem códigos
  nacionais diferentes, a emissão é recusada com aviso. Hoje tudo usa o padrão da clínica (050202).
- **Assinatura:** XMLDSig envelopada sobre `infDPS`, C14N inclusivo, RSA-SHA1 (padrão da NF-e).
- **Cancelamento:** `NFSeNacionalBackend.cancelar` (evento 101101) está pronto, mas ainda
  **não tem botão** na tela.
- **PDF:** o Vettro gera o próprio PDF com a chave e o link de consulta pública. O DANFSe
  oficial fica no Portal Nacional.
- **Reforma tributária:** o grupo `IBSCBS` da DPS é opcional no leiaute 1.01 e ainda não é enviado.

## Situação em 22/10/2026 (teste real em homologação)

- O certificado da Lume foi aceito: `testar_nfse_nacional` conectou com TLS mútuo.
- Uma DPS de teste passou no leiaute e na assinatura e foi recusada com **E0037**: Cachoeira do
  Sul ainda **não está no convênio** do Emissor Nacional. Quando a prefeitura aderir (previsto para
  1º/11/2026), reenvie a nota de teste. Do lado do Vettro não há mais nada a fazer.
- **Leiaute:** a produção restrita passou a exigir o leiaute de 20/10/2026 (NT 009, com `finNFSe`
  obrigatório). Os XSDs oficiais ficam em `apps/pagamentos/xsd_nfse/` e a DPS é validada contra eles
  **antes** do envio. Quando o governo mudar o leiaute, troque esses arquivos e ajuste
  `montar_dps`.

## Respostas da Fox Contábil (22/10/2026)

- Alíquota: **6% (Anexo III)**. Ela varia com o faturamento, então é preciso perguntar todo mês e atualizar em Clínica.
- Código **050202** para todos os serviços. Código municipal só se houver outra atividade.
- **Série da DPS: 00001 a 49999** para sistema próprio. A faixa **70000 a 79999** é do portal nacional (emissão manual, o portal escolhe sozinho). O Vettro usa a série 1 e recusa números fora da faixa.
- Inscrição municipal: **ainda não saiu**, só depois dos licenciamentos. Ela é opcional na DPS.
- Hoje Cachoeira do Sul emite pelo **portal da prefeitura**. Pelo comunicado da prefeitura, quem é do Simples passa ao Emissor Nacional (o prazo inicial de 1º/09/2026 foi adiado para 1º/11/2026), e sistemas próprios integram pela **API Nacional**. O teste em homologação confirma se o município já aceita.
- IBS/CBS: **opcional em 2026, obrigatório em 2027**.

## Passo a passo para ligar (Lume)

1. **Pedir à Fox Contábil:**
   - a **alíquota aproximada do Simples** (%) para informar na nota (`pTotTribSN`);
   - confirmar o **código de tributação nacional** (050202 = 5.02) e se Cachoeira do Sul
     exige **código municipal** (3 dígitos) ou **inscrição municipal** na nota;
   - qual **série** usar na DPS (padrão do Vettro: 1). Se a clínica também emitir pelo
     portal gov.br, use uma série diferente da do portal.
2. **Certificado digital A1 (e-CNPJ)** da Lume: o arquivo `.pfx` e a senha.
3. Em **Clínica**: conferir CNPJ e CEP (o código IBGE é preenchido pelo CEP), preencher
   alíquota, inscrição municipal e série, enviar o `.pfx` com a senha e deixar o ambiente em
   **Homologação**. O Vettro recusa certificado de outro CNPJ.
4. No servidor: `python manage.py testar_nfse_nacional --schema=lume`. Esse comando confere o
   certificado e a conexão sem emitir nota.
5. Fazer 2 ou 3 recebimentos de teste e conferir as notas com o contador.
6. Trocar o ambiente para **Produção**.

## Segurança

O `.pfx` e a senha ficam **cifrados** no banco (Fernet, mesma chave dos tokens do WhatsApp:
`WHATSAPP_CHAVE_CRIPTO`, ou derivada do `SECRET_KEY`). Trocar essa chave invalida o
certificado guardado, e aí é só enviar de novo. Ninguém baixa o certificado pelo sistema.
Para a conexão, a chave fica em arquivo temporário só durante a leitura e é apagada na hora.
