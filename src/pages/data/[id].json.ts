import type { APIRoute } from "astro";
import { facilities } from "../../lib/data";
import { rows, WARDS, typeLabel, mapUrl } from "../../lib/format";

export function getStaticPaths() {
  return facilities.map((f) => ({ params: { id: f.id }, props: { f } }));
}

/** 比較ページが読む1施設分の表示データ */
export const GET: APIRoute = ({ props }) => {
  const f = (props as { f: (typeof facilities)[number] }).f;
  const body = {
    id: f.id,
    name: f.name,
    ward: WARDS[f.ward],
    category: f.category,
    type: typeLabel(f),
    management: f.management,
    map: mapUrl(f),
    rows: rows(f),
  };
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json; charset=utf-8" } });
};
