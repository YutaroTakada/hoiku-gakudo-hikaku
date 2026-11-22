import type { APIRoute } from "astro";
import { facilityPayload, jsonResponse } from "../../../../lib/agent-data";
import { facilities } from "../../../../lib/data";
import type { Facility } from "../../../../lib/schema";

export function getStaticPaths() {
  return facilities.map((f) => ({ params: { id: f.id }, props: { f } }));
}

export const GET: APIRoute = ({ props }) => jsonResponse(facilityPayload((props as { f: Facility }).f));
