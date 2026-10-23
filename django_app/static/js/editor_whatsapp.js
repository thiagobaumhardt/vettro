/* Editor do lembrete por WhatsApp (tela Lembretes): Quill (static/vendor/quill)
   com a barra padrão — negrito, itálico, tachado, imagem e limpar formatação.
   O WhatsApp não usa HTML: o texto vai com a marcação dele (*negrito*,
   _itálico_, ~tachado~), que é o que fica no campo "texto" enviado ao servidor.
   A imagem não entra no meio do texto: o botão de imagem escolhe a imagem do
   topo da mensagem (campo "imagem", template com cabeçalho de imagem). */
(function () {
  const MARCAS = [["bold", "*"], ["italic", "_"], ["strike", "~"]];

  // Delta do Quill -> texto com a marcação do WhatsApp. A marca precisa
  // encostar no texto ("*oi*", não "* oi *"), então os espaços das pontas
  // ficam do lado de fora; e não atravessa quebra de linha.
  function paraWhatsapp(delta) {
    let saida = "";
    for (const op of delta.ops || []) {
      if (typeof op.insert !== "string") continue;
      const attrs = op.attributes || {};
      saida += op.insert.split("\n").map((trecho) => {
        const m = trecho.match(/^(\s*)([\s\S]*?)(\s*)$/);
        if (!m[2]) return trecho;
        let miolo = m[2];
        for (const [attr, sinal] of MARCAS) if (attrs[attr]) miolo = sinal + miolo + sinal;
        return m[1] + miolo + m[3];
      }).join("\n");
    }
    return saida.replace(/\n+$/, "");
  }

  // Texto do WhatsApp -> Delta (pra reabrir o que foi digitado, ex.: depois de um erro).
  function paraDelta(texto) {
    const ops = [];
    const re = /\*([^*\n]+)\*|_([^_\n]+)_|~([^~\n]+)~/g;
    let ultimo = 0, m;
    while ((m = re.exec(texto || ""))) {
      if (m.index > ultimo) ops.push({ insert: texto.slice(ultimo, m.index) });
      const attr = m[1] ? "bold" : m[2] ? "italic" : "strike";
      ops.push({ insert: m[1] || m[2] || m[3], attributes: { [attr]: true } });
      ultimo = re.lastIndex;
    }
    if (ultimo < (texto || "").length) ops.push({ insert: texto.slice(ultimo) });
    ops.push({ insert: "\n" });
    return { ops };
  }

  window.lembreteForm = function ({ texto, selecionados, limite, placeholder }) {
    return {
      texto: texto || "", busca: "", nomeImagem: "", selecionados: selecionados || [], limite,
      init() {
        const quill = new Quill(this.$refs.editor, {
          theme: "snow",
          placeholder,
          formats: ["bold", "italic", "strike"],
          modules: {
            toolbar: {
              container: [["bold", "italic", "strike"], ["image"], ["clean"]],
              handlers: { image: () => this.$refs.arquivo.click() },
            },
          },
        });
        quill.setContents(paraDelta(this.texto), "silent");
        quill.on("text-change", () => { this.texto = paraWhatsapp(quill.getContents()); });
        // Rótulos acessíveis nos botões da barra (o Quill só põe o desenho).
        const nomes = { "ql-bold": "Negrito", "ql-italic": "Itálico", "ql-strike": "Tachado", "ql-image": "Imagem no topo da mensagem", "ql-clean": "Limpar formatação" };
        this.$refs.editorWrap.querySelectorAll(".ql-toolbar button").forEach((b) => {
          const nome = nomes[[...b.classList].find((c) => nomes[c])];
          if (nome) { b.title = nome; b.setAttribute("aria-label", nome); }
        });
      },
      escolherImagem(evento) {
        const arquivo = evento.target.files[0];
        this.nomeImagem = arquivo ? arquivo.name : "";
      },
      tirarImagem() {
        this.$refs.arquivo.value = "";
        this.nomeImagem = "";
      },
    };
  };
})();
