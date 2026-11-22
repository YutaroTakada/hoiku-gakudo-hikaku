import type { APIRoute } from "astro";
import { jsonResponse, listPayload } from "../../../../../../lib/agent-data";
import { activeAreas } from "../../../../../../lib/regions";

/** JavaScript を実行しないエージェントでも年齢で絞れるよう、年齢ごとの一覧を書き出す */
export function getStaticPaths() {
  return activeAreas.flatMap((a) =>
    a.categories.flatMap((c) => c.ages.map((age) => ({ params: { area: a.id, category: c.id, age: String(age) } }))),
  );
}

export const GET: APIRoute = ({ params }) => jsonResponse(listPayload(params.area!, params.category!, Number(params.age)));
