import { facilitySchema, type Facility } from "./schema";

/** data/facilities/*.json を読み、スキーマで検証する。1件でも不正ならビルドを止める。 */
const files = import.meta.glob("../../data/facilities/*.json", { eager: true, import: "default" }) as Record<string, unknown[]>;

function load(): Facility[] {
  const out: Facility[] = [];
  const errors: string[] = [];
  const ids = new Set<string>();
  for (const [path, list] of Object.entries(files)) {
    if (!Array.isArray(list)) {
      errors.push(`${path}: 配列ではありません`);
      continue;
    }
    list.forEach((raw, i) => {
      const r = facilitySchema.safeParse(raw);
      if (!r.success) {
        const name = (raw as { name?: string })?.name ?? `#${i}`;
        errors.push(`${path} ${name}: ${r.error.issues.map((x) => `${x.path.join(".")} ${x.message}`).join("; ")}`);
        return;
      }
      if (ids.has(r.data.id)) errors.push(`${path}: id 重複 ${r.data.id}`);
      ids.add(r.data.id);
      out.push(r.data);
    });
  }
  if (errors.length) throw new Error(`施設データの検証に失敗しました（${errors.length}件）\n` + errors.slice(0, 30).join("\n"));
  if (out.length === 0) throw new Error("施設データが0件です");
  return out;
}

export const facilities: Facility[] = load();
export const byId = new Map(facilities.map((f) => [f.id, f]));
