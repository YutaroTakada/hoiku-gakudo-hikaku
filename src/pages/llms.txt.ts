import type { APIRoute } from "astro";
import { agentGuideText } from "../lib/agent-data";

export const GET: APIRoute = () =>
  new Response(agentGuideText(), { headers: { "Content-Type": "text/plain; charset=utf-8" } });
