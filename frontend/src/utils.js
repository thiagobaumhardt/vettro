export function fmt(valor) {
  const n = Number(valor) || 0;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function fmtData(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export function fmtHora(hora) {
  if (!hora) return "";
  return hora.slice(0, 5);
}

export function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

export const ESPECIE_EMOJI = {
  Cachorro: "🐶",
  Gato: "🐱",
  Ave: "🐦",
  Roedor: "🐹",
  Réptil: "🦎",
};

export function especieEmoji(especie) {
  return ESPECIE_EMOJI[especie] || "🐾";
}

export const STATUS_LABEL = {
  agendado: "Agendado",
  confirmado: "Confirmado",
  realizado: "Realizado",
  cancelado: "Cancelado",
};
