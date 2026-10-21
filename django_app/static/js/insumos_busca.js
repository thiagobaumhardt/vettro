// Busca de insumos com "adicionar" (templates/components/_insumos_busca.html).
// Fica dentro do x-data do formulário e mexe direto no `insumosSel` / `qtyTick`
// dele — o total() de cada tela continua lendo os inputs `qtd_<id>`.
document.addEventListener("alpine:init", () => {
  const normalizar = (t) => (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const numero = (v) => parseFloat(String(v ?? "").replace(",", ".")) || 0;
  const brl = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

  Alpine.data("buscaInsumos", (catalogo) => ({
    catalogo, busca: "", destaque: 0, qtds: {},

    resultados() {
      const bruto = this.busca.trim();
      const termo = normalizar(bruto);
      if (!termo) return [];
      return this.catalogo
        .filter((i) => !this.insumosSel.includes(i.id))
        .filter((i) => normalizar(i.nome).includes(termo) || (i.codigo_barras && i.codigo_barras === bruto))
        .slice(0, 8);
    },
    insumo(id) { return this.catalogo.find((i) => i.id === id) || { nome: "?", valor: "0", unidade: "", estoque_num: 0 }; },
    adicionar(i) {
      if (!i) return;
      if (!this.insumosSel.includes(i.id)) { this.qtds[i.id] = 1; this.insumosSel.push(i.id); }
      this.busca = ""; this.destaque = 0; this.qtyTick++;
      // $refs não resolve quando o clique vem de dentro do x-for — busca o campo pela raiz.
      const campo = this.$root.querySelector("input[type=search]");
      this.$nextTick(() => campo && campo.focus());
    },
    remover(id) { this.insumosSel.splice(this.insumosSel.indexOf(id), 1); delete this.qtds[id]; this.qtyTick++; },
    alterar(id, passo) {
      this.qtds[id] = Math.max(1, Math.round((numero(this.qtds[id]) + passo) * 1000) / 1000);
      this.$nextTick(() => this.qtyTick++);
    },
    mover(passo) {
      const total = this.resultados().length;
      if (total) this.destaque = (this.destaque + passo + total) % total;
    },
    // Enter adiciona o destacado (ou o código de barras exato, vindo do leitor) sem enviar o form.
    confirmar() { this.adicionar(this.resultados()[this.destaque]); },

    preco(i) { return brl(numero(i.valor)) + " / " + i.unidade; },
    estoqueBaixo(i) { return i.estoque_num < 3; },
    semEstoqueSuficiente(id) { return numero(this.qtds[id]) > this.insumo(id).estoque_num; },
    subtotal(id) { return brl(numero(this.insumo(id).valor) * numero(this.qtds[id])); },
  }));
});
