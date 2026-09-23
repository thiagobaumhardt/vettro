export function fmt(valor) {
  const n = Number(valor) || 0;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function fmtData(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export function fmtDataHora(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pt-BR");
}

export function fmtHora(hora) {
  if (!hora) return "";
  return hora.slice(0, 5);
}

export function fmtCpf(cpf) {
  if (!cpf) return "";
  const d = cpf.replace(/\D/g, "");
  if (d.length !== 11) return cpf;
  return d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
}

export function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

export function idadeTexto(dataNascimentoIso) {
  if (!dataNascimentoIso) return "";
  const nasc = new Date(dataNascimentoIso + "T00:00:00");
  const hoje = new Date();
  let anos = hoje.getFullYear() - nasc.getFullYear();
  let meses = hoje.getMonth() - nasc.getMonth();
  if (hoje.getDate() < nasc.getDate()) meses--;
  if (meses < 0) {
    anos--;
    meses += 12;
  }
  if (anos > 0) return meses > 0 ? `${anos} ano${anos > 1 ? "s" : ""} e ${meses} m${meses > 1 ? "eses" : "ês"}` : `${anos} ano${anos > 1 ? "s" : ""}`;
  return `${meses} m${meses !== 1 ? "eses" : "ês"}`;
}

export const ESPECIE_EMOJI = {
  Cão: "🐶",
  Gato: "🐱",
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
