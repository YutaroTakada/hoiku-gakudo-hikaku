import type { APIRoute } from "astro";
import { absUrl } from "../lib/format";

/** robots.txt はドメインの最上位でだけ有効。独自ドメインに移すと、この内容がそのまま効く。 */
export const GET: APIRoute = () =>
  new Response(`User-agent: *\nAllow: /\n\nSitemap: ${absUrl("/sitemap.xml")}\n`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
