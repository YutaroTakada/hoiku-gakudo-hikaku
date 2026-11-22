import type { APIRoute } from "astro";
import sources from "../../data/sources.json";
import { API } from "../lib/agent-data";
import { facilities } from "../lib/data";
import { absUrl } from "../lib/format";
import { activeAreas, activePrefectures } from "../lib/regions";

export const GET: APIRoute = () => {
  const paths = [
    "/",
    "/about/",
    API.guide,
    ...activePrefectures.map((p) => `/p/${p.id}/`),
    ...activeAreas.flatMap((a) => a.categories.map((c) => `/a/${a.id}/${c.id}/`)),
    ...facilities.map((f) => `/f/${f.id}/`),
  ];
  const urls = paths.map((p) => `<url><loc>${absUrl(p)}</loc><lastmod>${sources.collectedAt}</lastmod></url>`).join("");
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>\n`;
  return new Response(xml, { headers: { "Content-Type": "application/xml; charset=utf-8" } });
};
