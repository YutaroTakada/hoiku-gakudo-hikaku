import areasJson from "./areas.json";
import catalog from "./catalog.json";

/** サイト全体の設定。区名・種別名は areas.json / catalog.json から作る。 */
export const SITE = {
  name: "保育園・学童 比較",
  repo: "https://github.com/YutaroTakada/hoiku-gakudo-hikaku",
  /** 確認日からこの日数を過ぎた値に「古い可能性あり」と出す */
  staleDays: 90,
  /** 比較に入れられる施設の数 */
  maxCompare: 4,
} as const;

export type Area = (typeof areasJson.areas)[number];
export type Category = (typeof catalog.categories)[number];
export type TypeDef = (typeof catalog.types)[number];

export const AREAS: Area[] = areasJson.areas;
export const AREA_IDS = AREAS.map((a) => a.id) as [string, ...string[]];
export const areaName = (id: string) => AREAS.find((a) => a.id === id)?.name ?? id;
/** 「A区・B区」のような並び（設定から作る） */
export const AREA_LIST = AREAS.map((a) => a.name).join("・");

export const CATEGORIES: Category[] = catalog.categories;
export const CATEGORY_IDS = CATEGORIES.map((c) => c.id) as [string, ...string[]];
export const category = (id: string) => CATEGORIES.find((c) => c.id === id)!;

export const TYPES: TypeDef[] = catalog.types;
export const TYPE_IDS = TYPES.map((t) => t.id) as [string, ...string[]];
export const typeLabel = (id: string) => TYPES.find((t) => t.id === id)?.label ?? id;
export const typeCategory = (id: string) => TYPES.find((t) => t.id === id)?.category;

export const MANAGEMENTS = catalog.managements as [string, ...string[]];

/** 出どころURLのホスト名から表示名を引く */
export function sourceLabel(url: string): string {
  const h = new URL(url).hostname;
  for (const a of AREAS) {
    const m = (a.sourceHosts as Record<string, string>)[h];
    if (m) return m;
  }
  return h.replace(/^www\./, "");
}
