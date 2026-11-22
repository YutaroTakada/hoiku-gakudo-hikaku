import type { APIRoute } from "astro";
import { jsonResponse, listPayload } from "../../../../../lib/agent-data";
import { activeAreas } from "../../../../../lib/regions";

export function getStaticPaths() {
  return activeAreas.flatMap((a) => a.categories.map((c) => ({ params: { area: a.id, category: c.id } })));
}

export const GET: APIRoute = ({ params }) => jsonResponse(listPayload(params.area!, params.category!));
