/** Paleta e tipografia da marca Lume — cores MEDIDAS nas imagens da
 * identidade visual (ver static/dist/styles.css, que é o fallback em uso
 * enquanto o build do Tailwind não roda). Títulos: Roca Two (paga; arquivos
 * em static/fonts/), com Fraunces "SOFT" de substituta. Textos: Livvic. */
module.exports = {
  content: ["./templates/**/*.html", "./apps/**/templates/**/*.html"],
  theme: {
    extend: {
      fontFamily: {
        heading: ['"Roca Two"', "Fraunces", "Georgia", "serif"],
        body: ["Livvic", "Segoe UI", "sans-serif"],
      },
      colors: {
        "verde-oliva": "#949C56",   // Vitalidade — principal
        "verde-claro": "#E5E8C5",   // Tranquilidade
        marfim: "#F5EFCB",          // Clareza
        amarelo: "#EFC15A",         // Luz
        terroso: "#C17D46",         // Proximidade
        "verde-escuro": "#545936",  // texto/títulos
        "verde-profundo": "#60663C",
        bg: "#E5E8C5",
        text: "#545936",
        primary: { DEFAULT: "#545936", hover: "#444929" },
        sidebar: { from: "#545936", to: "#60663C", active: "#6E7443" },
        secondary: { DEFAULT: "#E5E8C5", hover: "#C9CE9C" },
        accent: { DEFAULT: "#C17D46", hover: "#8A4E22" },
        danger: { DEFAULT: "#A9442B", hover: "#8C3520" },
        border: { DEFAULT: "#DCD6AE", 2: "#C3BE8F" },
        muted: { DEFAULT: "#7C7D5A", 2: "#62653F" },
      },
    },
  },
  plugins: [],
};
