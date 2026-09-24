/** Paleta e tipografia da marca real Lume (ver Apresentação Lume, Studio
 * Ananda Souza, 2026) — hex estimados visualmente (o material não trouxe
 * hex oficiais, ver ressalva em static/dist/styles.css). Roca Two (títulos
 * da marca) é fonte paga sem confirmação de licença web — Fraunces é
 * substituta temporária gratuita. Livvic (textos) é a fonte real da marca. */
module.exports = {
  content: ["./templates/**/*.html", "./apps/**/templates/**/*.html"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["Fraunces", "Georgia", "serif"],
        body: ["Livvic", "Segoe UI", "sans-serif"],
      },
      colors: {
        bg: "#F3F0D8",
        text: "#2B2B20",
        primary: { DEFAULT: "#7C8752", hover: "#626D3F" },
        sidebar: { from: "#4B5530", to: "#333B22", active: "#5C6640" },
        secondary: { DEFAULT: "#EDE9CD", hover: "#E2DCB8" },
        accent: { DEFAULT: "#BC7440", hover: "#A25F31" },
        danger: { DEFAULT: "#fc8181", hover: "#e53e3e" },
        border: { DEFAULT: "#E3DFC4", 2: "#CAC6A0" },
        muted: { DEFAULT: "#8B8768", 2: "#6B6850" },
        "verde-claro": "#D9DEBB",
        marfim: "#F3F0D8",
        amarelo: "#E5AE3E",
        terroso: "#BC7440",
      },
    },
  },
  plugins: [],
};
