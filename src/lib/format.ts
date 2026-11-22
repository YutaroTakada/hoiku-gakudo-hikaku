import { AREAS, PREFECTURES, SITE, category } from "../config/site";
import type { Facility, Field } from "./schema";

export const BUILD_DATE = new Date();
export const STALE_DAYS = SITE.staleDays;

export const href = (p: string) => import.meta.env.BASE_URL.replace(/\/$/, "") + p;

export function isStale(checked: string | null, now = BUILD_DATE): boolean {
  if (!checked) return false;
  const d = new Date(checked + "T00:00:00+09:00");
  return (now.getTime() - d.getTime()) / 86400000 > STALE_DAYS;
}

export function jpDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return `${y}年${m}月${d}日`;
}
/** 確認日の短い表記（2026/11/20） */
export const shortDate = (iso: string | null | undefined) => (iso ? iso.replaceAll("-", "/") : "");

export const yen = (n: number) => (n === 0 ? "無料" : `${n.toLocaleString("ja-JP")}円`);
export const toMin = (t: string) => {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
};

/** 住所の表示用（括弧書きの補足を落とす） */
export const shortAddress = (f: Facility) => f.address.value?.split("（")[0].split(" ／ ")[0] ?? null;

/** 「東京都足立区」のような都道府県＋市区町村 */
export function areaPrefix(areaId: string): string {
  const a = AREAS.find((x) => x.id === areaId);
  return a ? `${PREFECTURES.find((p) => p.id === a.prefecture)?.name ?? ""}${a.name}` : "";
}

/**
 * 都道府県と市区町村を補った住所。データの住所は町名から始まり、同じ町名が別の区にもあるため、
 * 地域の文脈なしで読まれる場所（詳細・比較・機械向けデータ）ではこちらを使う。園舎が複数あれば園舎ごとに補う。
 */
export function fullAddress(f: Facility): string | null {
  const v = f.address.value;
  if (!v) return null;
  const pre = areaPrefix(f.ward);
  return v
    .split(" ／ ")
    .map((part) => {
      const m = part.match(/^(第.園舎：)(.*)$/);
      return m ? `${m[1]}${pre}${m[2]}` : `${pre}${part}`;
    })
    .join(" ／ ");
}

/** サイトの絶対 URL */
export const absUrl = (p: string) => new URL(href(p), import.meta.env.SITE).href;

export function mapUrl(f: Facility): string {
  const pre = areaPrefix(f.ward);
  const addr = (shortAddress(f) ?? "").replace(/^第.園舎：/, "");
  // 家庭的保育は個人宅のため町名だけで検索する
  const q = f.type === "katei" ? `${pre}${addr}` : `${f.name} ${pre}${addr}`;
  return "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(q);
}

export function rangeText(f: Facility, short = false): string | null {
  const r = f.ageRange.value;
  if (!r) return null;
  const c = category(f.category);
  return `${r.min}〜${r.max}${short ? c.ageShort : c.ageUnit}`;
}

/** 延長を含めて最も遅い終わりの時刻と、その値のフィールド */
export function latestEndField(f: Facility): Field<string> {
  const c = [f.hours.extensionEnd, f.hours.weekdayEnd].filter((x) => x.value) as Field<string>[];
  if (!c.length) return f.hours.extensionEnd as Field<string>;
  return c.sort((a, b) => toMin(b.value!) - toMin(a.value!))[0];
}
export const latestEnd = (f: Facility) => latestEndField(f).value;

export function hasExtension(f: Facility): boolean {
  const v = f.hours.extension.value;
  return !!v && !v.startsWith("なし");
}
export const pickupYes = (f: Facility) => !!f.pickup.value && /(送りあり|送迎あり|送迎サービスあり)/.test(f.pickup.value);

export function monthlyFee(f: Facility): number | null {
  if (f.category === "gakudo") return f.fees.monthly?.value ?? null;
  // 認可・地域型・こども園は区の基本保育料が無料（延長料金などは別）
  if (f.fees.basic?.value && /無料|無償/.test(f.fees.basic.value)) return 0;
  return null;
}
export function monthlyFeeField(f: Facility): Field<unknown> {
  return (f.category === "gakudo" ? f.fees.monthly : f.fees.basic) ?? { value: null, source: null, checked: null };
}

/** 空きの合計（区の公表値）。記載がなければ null */
export const vacancyTotal = (f: Facility) => f.vacancy.value?.total ?? null;

/** 一覧のカード用の短い空き表記 */
export function vacancyShort(f: Facility): string | null {
  const v = f.vacancy.value;
  if (!v) return null;
  if (v.total === null) return "記載なし";
  return /以上/.test(v.totalText ?? "") ? `${v.total}人以上` : `${v.total}人`;
}

export function vacancyText(f: Facility): string | null {
  const v = f.vacancy.value;
  if (!v) return null;
  if (v.total === null) return v.totalText ?? null;
  if (v.byAge) {
    const unit = category(f.category).ageUnit;
    const parts = Object.entries(v.byAge)
      .filter(([, n]) => (n ?? 0) > 0)
      .map(([a, n]) => `${a}${unit}${n}`);
    return v.total > 0 ? `計${v.total}人（${parts.join("・")}）` : "0人";
  }
  return v.totalText ?? `${v.total}人`;
}

/** 年齢別の内訳（0 も含めて全部） */
export function vacancyByAge(f: Facility): string | null {
  const v = f.vacancy.value;
  if (!v?.byAge) return null;
  const r = f.ageRange.value;
  const unit = category(f.category).ageUnit;
  return Object.entries(v.byAge)
    .filter(([a]) => !r || (+a >= r.min && +a <= r.max))
    .map(([a, n]) => `${a}${unit} ${n === null ? "記載なし" : n + "人"}`)
    .join("、");
}

/** 年齢別の空き（一覧の絞り込み・表示の切り替え用）。"0:0 1:2" の形 */
export function vacancyAgesAttr(f: Facility): string {
  const b = f.vacancy.value?.byAge;
  if (!b) return "";
  return Object.entries(b)
    .filter(([, n]) => n !== null)
    .map(([a, n]) => `${a}:${n}`)
    .join(" ");
}

export function vacancyAsOf(f: Facility): string {
  const v = f.vacancy.value;
  if (!v) return "";
  return `${v.label}${v.asOf ? `・${jpDate(v.asOf)}時点` : ""}`;
}
