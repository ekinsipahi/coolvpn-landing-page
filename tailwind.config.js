/** @type {import('tailwindcss').Config} */

// Blog kategori renkleri şablonda `bg-{{ category.accent }}-500/10` gibi
// KURULARAK üretiliyor; Tailwind'in tarayıcısı böyle parçalı sınıfları
// göremediği için burada açıkça listeleniyor. Yeni bir accent eklersen
// (blog/models.py BlogCategory.accent) buraya da ekle.
const ACCENTS = ["sky", "fuchsia", "indigo", "emerald", "amber", "rose", "teal", "violet"];
const accentSafelist = ACCENTS.flatMap((c) => [
  `bg-${c}-500/10`,
  `text-${c}-600`,
  `text-${c}-700`,
  `dark:text-${c}-400`,
]);

module.exports = {
  darkMode: "class",
  content: [
    "./templates/**/*.html",           // proje kökünde templates
    "./**/templates/**/*.html",        // app içi templates + partials
    "./**/*.py",                       // Django template stringleri
    "./static/js/**/*.js",             // nav JS içindeki class'lar
    "./static_src/**/*.css",           // input css
  ],
  safelist: accentSafelist,
  theme: {
    extend: {},
  },
  plugins: [
    require("tailwindcss-rtl"),        // RTL varyantları için
  ],
};
