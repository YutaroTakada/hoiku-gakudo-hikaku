/**
 * 表示する項目の定義。ラベル・並び順・どのカテゴリで出すか・並べ替えや絞り込みに使うかをここで決める。
 * 画面（一覧・詳細・比較）とデータ（比較ページが読む /data/<id>.json）はここから作る。
 */
import { AREAS, MANAGEMENTS, TYPES } from "./site";
import type { Facility, Field } from "../lib/schema";
import {
  hasExtension, latestEnd, latestEndField, monthlyFee, monthlyFeeField, pickupYes, rangeText, toMin,
  vacancyAsOf, vacancyByAge, vacancyShort, vacancyText, vacancyTotal, yen,
} from "../lib/format";

/** カテゴリごとに変えられるラベル */
type Label = string | Record<string, string>;
export const labelFor = (l: Label, cat: string) => (typeof l === "string" ? l : l[cat] ?? Object.values(l)[0]);
const inCat = (cats: string[] | undefined, cat: string) => !cats || cats.includes(cat);
const NONE: Field<unknown> = { value: null, source: null, checked: null };

/* ───────── 要約（一覧のカードと詳細の冒頭） ───────── */

export type SummaryDef = {
  key: string;
  label: Label;
  categories?: string[];
  /** 出どころ・確認日を引くフィールド */
  field: (f: Facility) => Field<unknown>;
  text: (f: Facility) => string | null;
  /** 並べ替えに使う数値。sort があるときに使う */
  num?: (f: Facility) => number | null;
  sort?: { label: Label; dir: "asc" | "desc" };
};

export const SUMMARY: SummaryDef[] = [
  { key: "age", label: { hoiku: "対象", gakudo: "学年" }, field: (f) => f.ageRange, text: (f) => rangeText(f, true) },
  {
    key: "end", label: "預かり", field: latestEndField,
    text: (f) => (latestEnd(f) ? `〜${latestEnd(f)}` : null),
    num: (f) => (latestEnd(f) ? toMin(latestEnd(f)!) : null),
    sort: { label: "終わりが遅い順", dir: "desc" },
  },
  {
    key: "cap", label: "定員", categories: ["hoiku"], field: (f) => f.capacity,
    text: (f) => (f.capacity.value ? `${f.capacity.value}人` : null), num: (f) => f.capacity.value,
    sort: { label: "定員が多い順", dir: "desc" },
  },
  {
    key: "fee", label: "月額", categories: ["gakudo"], field: monthlyFeeField,
    text: (f) => (monthlyFee(f) === null ? null : yen(monthlyFee(f)!)), num: monthlyFee,
    sort: { label: "月額が安い順", dir: "asc" },
  },
  {
    key: "vac", label: "空き", field: (f) => f.vacancy, text: vacancyShort, num: vacancyTotal,
    sort: { label: "空きが多い順", dir: "desc" },
  },
];
export const summaryFor = (cat: string) => SUMMARY.filter((s) => inCat(s.categories, cat));

/* ───────── 詳細と比較の行 ───────── */

export type RowDef = {
  group: string;
  label: Label;
  categories?: string[];
  get: (f: Facility) => Field<unknown> | undefined;
  /** 値の表示。省略時は String(value) */
  fmt?: (v: any, f: Facility) => string | null;
  /** 値をリンクにする（url: 値のURL、tel: 電話） */
  link?: "url" | "tel";
  /** 出す条件（省略時は常に出す） */
  when?: (f: Facility) => boolean;
};

const B = "基本情報", A = "対象と定員", H = "預かり時間", P = "料金", V = "空き状況", J = "申込", K = "リンク";
export const ROWS: RowDef[] = [
  { group: B, label: "住所", get: (f) => f.address },
  { group: B, label: "最寄り駅", get: (f) => f.station },
  { group: B, label: "電話", get: (f) => f.phone, link: "tel" },
  { group: B, label: "運営事業者", get: (f) => f.operator, when: (f) => !!f.operator },
  { group: A, label: { hoiku: "対象年齢", gakudo: "対象学年" }, get: (f) => f.ages },
  { group: A, label: "定員", get: (f) => f.capacity, fmt: (v) => `${v}人` },
  { group: H, label: "平日", get: (f) => f.hours.weekday },
  { group: H, label: "延長", get: (f) => f.hours.extension },
  { group: H, label: "延長の終わり", get: (f) => f.hours.extensionEnd },
  { group: H, label: "土曜", get: (f) => f.hours.saturday },
  { group: H, label: "長期休み", categories: ["gakudo"], get: (f) => f.hours.vacation ?? NONE },
  { group: P, label: "保育料", categories: ["hoiku"], get: (f) => f.fees.basic ?? NONE },
  { group: P, label: "区の保育料表", categories: ["hoiku"], get: (f) => f.fees.table ?? NONE, fmt: () => "区のページ", link: "url" },
  { group: P, label: "延長保育料", categories: ["hoiku"], get: (f) => f.fees.extensionFee ?? NONE },
  { group: P, label: "施設独自の費用", categories: ["hoiku"], get: (f) => f.fees.own ?? NONE },
  { group: P, label: "月額", categories: ["gakudo"], get: (f) => f.fees.monthly ?? NONE, fmt: (v) => yen(v) },
  { group: P, label: "おやつ代", categories: ["gakudo"], get: (f) => f.fees.snack ?? NONE, fmt: (v) => `月額${yen(v)}` },
  { group: P, label: "延長料金", categories: ["gakudo"], get: (f) => f.fees.extension ?? NONE },
  { group: "送迎", label: { hoiku: "送迎", gakudo: "お迎え・送り" }, get: (f) => f.pickup },
  { group: V, label: "区の公表値", get: (f) => f.vacancy, fmt: (_, f) => vacancyText(f) },
  { group: V, label: "年齢別", get: (f) => f.vacancy, fmt: (_, f) => vacancyByAge(f), when: (f) => !!f.vacancy.value?.byAge },
  { group: V, label: "発表", get: (f) => f.vacancy, fmt: (_, f) => vacancyAsOf(f) },
  { group: J, label: "申込方法", get: (f) => f.application.method },
  { group: J, label: "締切", get: (f) => f.application.deadline },
  { group: K, label: "公式ページ", get: (f) => f.links.official, fmt: () => "開く", link: "url" },
  { group: K, label: "区の施設紹介", get: (f) => f.links.intro, fmt: () => "開く", link: "url" },
];

/* ───────── 絞り込み ───────── */

export type Option = { value: string; label: string };
export type FilterDef =
  /** 1つ選ぶ（すべて／A／B） */
  | { key: string; kind: "one"; label: Label; attr: (f: Facility) => string; options: (cat: string) => Option[] }
  /** 複数選ぶ（初めは全部選択） */
  | { key: string; kind: "many"; label: Label; attr: (f: Facility) => string; options: (cat: string) => Option[] }
  /** 年齢・学年（対象範囲に入るか。空きありと組み合わせるとその年齢の空きを見る） */
  | { key: string; kind: "age"; label: Label }
  /** オン・オフの条件。test が true の施設だけ残す */
  | { key: string; kind: "flag"; label: string; test: (f: Facility) => boolean; byAge?: boolean };

export const FILTERS: FilterDef[] = [
  { key: "area", kind: "one", label: "エリア", attr: (f) => f.ward, options: () => AREAS.map((a) => ({ value: a.id, label: a.name })) },
  { key: "age", kind: "age", label: { hoiku: "年齢", gakudo: "学年" } },
  // byAge：年齢を選んでいるときは、その年齢の空き（区の年齢別の公表値）で見る
  { key: "vac", kind: "flag", label: "空きあり", test: (f) => (vacancyTotal(f) ?? 0) > 0, byAge: true },
  { key: "ext", kind: "flag", label: "延長あり", test: hasExtension },
  { key: "pickup", kind: "flag", label: "送迎あり", test: pickupYes },
  {
    key: "type", kind: "many", label: "種別", attr: (f) => f.type,
    options: (cat) => TYPES.filter((t) => t.category === cat).map((t) => ({ value: t.id, label: t.label })),
  },
  { key: "mg", kind: "many", label: "運営", attr: (f) => f.management, options: () => MANAGEMENTS.map((m) => ({ value: m, label: m })) },
];
