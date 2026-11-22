import type { APIRoute } from "astro";
import { indexPayload, jsonResponse } from "../../../lib/agent-data";

export const GET: APIRoute = () => jsonResponse(indexPayload());
