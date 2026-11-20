import { AREAS, CATEGORIES, PREFECTURES } from "../config/site";
import { facilities } from "./data";

/** 設定順を保ち、実データのある地域とカテゴリだけを公開する。 */
export const activeAreas = AREAS.map((area) => {
  const list = facilities.filter((f) => f.ward === area.id);
  const categories = CATEGORIES.map((category) => ({ ...category, count: list.filter((f) => f.category === category.id).length })).filter((c) => c.count > 0);
  return { ...area, count: list.length, categories };
}).filter((area) => area.count > 0);

export const activePrefectures = PREFECTURES.map((prefecture) => {
  const areas = activeAreas.filter((area) => area.prefecture === prefecture.id);
  return { ...prefecture, areas, count: areas.reduce((sum, area) => sum + area.count, 0) };
}).filter((prefecture) => prefecture.count > 0);
