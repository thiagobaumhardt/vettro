// Máscara de telefone (inputs com data-mascara="telefone" — apps/core/campos.py:TelefoneField).
// "+55" já vem preenchido e pode ser trocado por outro DDI; Brasil vira
// "+55 (DD) 9 XXXX-XXXX" (celular) ou "+55 (DD) XXXX-XXXX" (fixo). Quem valida
// de verdade é o servidor (apps/core/validators.py:formatar_telefone).
(() => {
  function formatarTelefone(valor) {
    valor = (valor || "").trimStart();
    let ddi = "55";
    let resto;
    const comDdi = valor.match(/^\+(\d{1,3})(?=\D|$)/);
    if (comDdi) {
      ddi = comDdi[1];
      resto = valor.slice(comDdi[0].length).replace(/\D/g, "");
    } else if (valor.startsWith("+")) {
      return valor; // ainda digitando o DDI
    } else {
      resto = valor.replace(/\D/g, "");
      if (resto.length > 11 && resto.startsWith("55")) resto = resto.slice(2);
    }
    if (ddi !== "55") {
      // Mantém o espaço depois do DDI enquanto o número ainda não começou.
      if (!resto) return valor.length > comDdi[0].length ? `+${ddi} ` : `+${ddi}`;
      return `+${ddi} ${resto.slice(0, 14)}`;
    }

    resto = resto.slice(0, 11);
    if (!resto) return "+55 ";
    let saida = `+55 (${resto.slice(0, 2)}`;
    if (resto.length < 2) return saida;
    saida += ") ";
    const numero = resto.slice(2);
    if (numero.startsWith("9")) {
      // celular: 9 + 4 + 4
      saida += numero.slice(0, 1);
      if (numero.length > 1) saida += " " + numero.slice(1, 5);
      if (numero.length > 5) saida += "-" + numero.slice(5, 9);
    } else {
      // fixo: 4 + 4
      saida += numero.slice(0, 4);
      if (numero.length > 4) saida += "-" + numero.slice(4, 8);
    }
    return saida;
  }

  const ehTelefone = (el) => el instanceof HTMLInputElement && el.dataset.mascara === "telefone";

  document.addEventListener("input", (e) => {
    // Apagando: não reformata, senão os caracteres automáticos voltam e "travam" o backspace.
    if (!ehTelefone(e.target) || (e.inputType || "").startsWith("delete")) return;
    e.target.value = formatarTelefone(e.target.value);
  });
  document.addEventListener("focusin", (e) => {
    if (ehTelefone(e.target) && !e.target.value) e.target.value = "+55 ";
  });
  document.addEventListener("focusout", (e) => {
    if (!ehTelefone(e.target)) return;
    const v = e.target.value.trim();
    e.target.value = v === "+55" || v === "+" ? "" : formatarTelefone(v);
  });

  // Valores que já vieram do servidor (ou de uma troca de aba via HTMX) aparecem formatados.
  const formatarIniciais = (raiz) =>
    raiz.querySelectorAll('input[data-mascara="telefone"]').forEach((el) => {
      if (el.value) el.value = formatarTelefone(el.value);
    });
  document.addEventListener("DOMContentLoaded", () => formatarIniciais(document));
  document.addEventListener("htmx:afterSettle", (e) => formatarIniciais(e.target));
})();
