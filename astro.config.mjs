import { defineConfig } from "astro/config";

// GitHub Pages（https://yutarotakada.github.io/hoiku-gakudo-hikaku/）で配信する静的サイト
export default defineConfig({
  site: "https://yutarotakada.github.io",
  base: "/hoiku-gakudo-hikaku",
  trailingSlash: "always",
  output: "static",
  build: { format: "directory" },
});
