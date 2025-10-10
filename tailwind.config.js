/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./templates/**/*.html",           // proje kökünde templates
    "./**/templates/**/*.html",        // app içi templates + partials
    "./**/*.py",                       // Django template stringleri
    "./static/js/**/*.js",             // nav JS içindeki class’lar
    "./static_src/**/*.css",           // input css
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require("tailwindcss-rtl"),        // RTL varyantları için
  ],
};
