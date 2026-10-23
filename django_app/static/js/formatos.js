// Formato de dinheiro nas telas (totais calculados no navegador): 1425.45 -> "R$ 1.425,45",
// igual ao filtro |moeda dos templates (apps/core/templatetags/formatos.py).
window.brl = (v) => (Number(v) || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }).replace(/ /g, " ");
