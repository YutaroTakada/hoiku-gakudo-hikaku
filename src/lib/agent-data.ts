/**
 * AI エージェントや検索エンジンが読むためのデータ。
 * すべて静的ファイルとして書き出すので、利用者の住所や子どもの情報はこのサイトに届かない。
 */
import sources from "../../data/sources.json";
import { PREFECTURES, SITE, areaName, category, typeLabel } from "../config/site";
import { facilities } from "./data";
import { activeAreas } from "./regions";
import { STALE_DAYS, absUrl, fullAddress, latestEnd, shortAddress } from "./format";
import type { Facility } from "./schema";

export const API = {
  version: "v1",
  guide: "/agents/",
  index: "/api/v1/index.json",
  list: (area: string, cat: string) => `/api/v1/areas/${area}/${cat}.json`,
  age: (area: string, cat: string, age: number | string) => `/api/v1/areas/${area}/${cat}/age-${age}.json`,
  facility: (id: string) => `/api/v1/facilities/${id}.json`,
};

/** データを読むときの決まり。案内ページ・llms.txt・index.json で共通に使う。 */
export const AGENT_RULES = [
  "null は「未確認」です。「なし」「0」として扱わず、未確認と伝えてください。",
  "空き（vacancy）は自治体の発表時点の目安です。対象月（intakeMonth）の値なので、ほかの月（たとえば翌年4月）の空きとして伝えないでください。intakeMonth が null なら対象月は不明です。",
  "保育園の年齢は「歳児クラス」です。入園する年度の4月1日時点の満年齢で決まるので、今の月齢のまま選ばないでください。学童の数字は学年です。",
  "距離を出すときは location を使ってください。街区の代表点で、建物の位置ではありません。location が null の施設は除外せず「距離不明」として示してください。",
  "家庭的保育（type: katei）は個人宅のため住所を町名までにしています。番地や自宅を推測しないでください。",
  `答えには施設ページの URL と確認日を添えてください。確認日から${STALE_DAYS}日を過ぎた値は「古い可能性あり」と伝えてください。`,
  "このサイトは申込や見学予約を受け付けていません。申込の前に自治体と施設で確認するよう伝え、施設への連絡は利用者本人の確認を取ってから行ってください。",
  "利用者の住所や子どもの情報をこのサイトの URL に含めないでください。距離の計算はエージェント側で行えます。",
];

export const jsonResponse = (body: unknown) =>
  new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json; charset=utf-8" } });

/** 「令和8年12月入所の募集人数」のような表記から対象月（2026-12）を取り出す。書かれていなければ null。 */
export function intakeMonth(label: string | null | undefined): string | null {
  const m = label?.match(/令和(\d+)年(\d+)月(?:入所|入園)/);
  return m ? `${2018 + Number(m[1])}-${m[2].padStart(2, "0")}` : null;
}

/** 同じ値を1回だけ載せるための表（{ s0: 値, s1: 値 }）を作る */
function refTable<T>(prefix: string) {
  const ids = new Map<string, string>();
  const table: Record<string, T> = {};
  const ref = (key: string, value: T) => {
    let id = ids.get(key);
    if (!id) {
      id = `${prefix}${ids.size}`;
      ids.set(key, id);
      table[id] = value;
    }
    return id;
  };
  return { ref, table };
}

const ageMatch = (f: Facility, age: number) => {
  const r = f.ageRange.value;
  if (!r) return "unknown" as const;
  return r.min <= age && age <= r.max ? ("yes" as const) : ("no" as const);
};

/** 地域×カテゴリの一覧。age を渡すとその年齢を受け入れる施設（対象年齢が未確認の施設も含む）に絞る。 */
export function listPayload(areaId: string, categoryId: string, age?: number) {
  const area = activeAreas.find((a) => a.id === areaId)!;
  const c = category(categoryId);
  const all = facilities
    .filter((f) => f.ward === areaId && f.category === categoryId)
    .sort((a, b) => a.name.localeCompare(b.name, "ja"));
  const list = age === undefined ? all : all.filter((f) => ageMatch(f, age) !== "no");
  // 施設ごとに同じ文字列を繰り返さないよう、空きの出どころ・締切・種別名はファイル先頭の表にまとめる
  const vacancyInfo = refTable<{ label: string; intakeMonth: string | null; asOf: string | null; checked: string | null; source: string | null }>("v");
  const deadlines = refTable<{ text: string; source: string | null; checked: string | null }>("d");

  const items = list.map((f) => {
    const v = f.vacancy.value;
    const d = f.application.deadline;
    const forAge = age === undefined ? undefined : v?.byAge?.[String(age)] ?? null;
    return {
      id: f.id,
      name: f.name,
      type: f.type,
      management: f.management,
      address: fullAddress(f),
      location: f.location.value ? { lat: f.location.value.lat, lng: f.location.value.lng } : null,
      ageRange: f.ageRange.value,
      capacity: f.capacity.value,
      latestPickup: latestEnd(f),
      extension: f.hours.extension.value,
      ...(f.category === "gakudo" ? { monthlyFeeYen: f.fees.monthly?.value ?? null, pickup: f.pickup.value } : {}),
      vacancy: v
        ? {
            total: v.total,
            ...(v.totalText ? { totalText: v.totalText } : {}),
            ...(age === undefined ? { byAge: v.byAge } : {}),
            ref: vacancyInfo.ref([f.vacancy.source, v.label, v.asOf, f.vacancy.checked].join("|"), {
              label: v.label,
              intakeMonth: intakeMonth(v.label),
              asOf: v.asOf,
              checked: f.vacancy.checked,
              source: f.vacancy.source,
            }),
          }
        : null,
      deadlineRef: d.value ? deadlines.ref(d.value, { text: d.value, source: d.source, checked: d.checked }) : null,
      ...(age === undefined ? {} : { ageMatch: ageMatch(f, age), vacancyForAge: forAge }),
    };
  });

  return {
    apiVersion: API.version,
    area: { id: area.id, name: area.name, prefecture: PREFECTURES.find((p) => p.id === area.prefecture)?.name ?? "" },
    category: { id: c.id, label: c.label, ageUnit: c.ageUnit },
    ...(age === undefined ? {} : { age }),
    collectedAt: sources.collectedAt,
    guide: absUrl(API.guide),
    rules: absUrl(API.index),
    urlTemplates: { page: absUrl("/f/{id}/").replace("%7Bid%7D", "{id}"), detail: absUrl(API.facility("{id}")).replace("%7Bid%7D", "{id}") },
    counts: {
      items: items.length,
      withoutLocation: items.filter((x) => !x.location).length,
      ...(age === undefined
        ? { withVacancy: items.filter((x) => (x.vacancy?.total ?? 0) > 0).length }
        : {
            ageUnknown: items.filter((x) => x.ageMatch === "unknown").length,
            withVacancyForAge: items.filter((x) => (x.vacancyForAge ?? 0) > 0).length,
            // 合計には空きがあるが、この年齢の空きかどうかは公表値から分からない施設（画面の「空きあり」にはこれも含まれる）
            withVacancyAgeNotPublished: items.filter((x) => x.vacancyForAge === null && (x.vacancy?.total ?? 0) > 0).length,
            vacancyForAgeUnknown: items.filter((x) => x.vacancyForAge === null).length,
          }),
    },
    types: Object.fromEntries([...new Set(items.map((x) => x.type))].map((t) => [t, typeLabel(t)])),
    vacancyInfo: vacancyInfo.table,
    deadlines: deadlines.table,
    items,
  };
}

/** 1施設の全項目。各値に value / source / checked がつく。 */
export function facilityPayload(f: Facility) {
  const { image: _image, ...rest } = f;
  const area = activeAreas.find((a) => a.id === f.ward);
  return {
    apiVersion: API.version,
    page: absUrl(`/f/${f.id}/`),
    rules: absUrl(API.index),
    prefecture: PREFECTURES.find((p) => p.id === area?.prefecture)?.name ?? "",
    areaName: areaName(f.ward),
    typeLabel: typeLabel(f.type),
    addressFull: fullAddress(f),
    vacancyIntakeMonth: intakeMonth(f.vacancy.value?.label),
    facility: rest,
  };
}

/** データの入口。地域の一覧と読み方の決まり。 */
export function indexPayload() {
  return {
    name: SITE.name,
    description: "自治体の公式情報から集めた保育園・学童のデータ。値ごとに出どころと確認日があります。",
    apiVersion: API.version,
    collectedAt: sources.collectedAt,
    staleAfterDays: STALE_DAYS,
    guide: absUrl(API.guide),
    rules: AGENT_RULES,
    fields: {
      location: "街区の代表点の緯度経度。null は距離不明",
      ageRange: "受け入れる年齢（保育園は歳児クラス、学童は学年）",
      latestPickup: "延長を含めて最も遅い預かりの終わり（HH:MM）",
      type: "施設の種別。名前は同じファイルの types にある",
      "vacancy.byAge": "全件ファイルのみ。年齢別の空き。キーは歳児クラスまたは学年",
      "vacancy.ref": "同じファイルの vacancyInfo のキー。発表の名前、対象月（intakeMonth: YYYY-MM）、発表日、確認日、出どころがある",
      deadlineRef: "同じファイルの deadlines のキー",
      vacancyForAge: "年齢別ファイルのみ。その年齢の空き。null は年齢別の値が未公表で、vacancy.total が1以上でもその年齢の空きとは限らない",
      ageMatch: "年齢別ファイルのみ。yes または unknown（対象年齢が未確認）",
    },
    areas: activeAreas.map((a) => ({
      id: a.id,
      name: a.name,
      prefecture: PREFECTURES.find((p) => p.id === a.prefecture)?.name ?? "",
      categories: a.categories.map((c) => ({
        id: c.id,
        label: c.label,
        count: c.count,
        page: absUrl(`/a/${a.id}/${c.id}/`),
        data: absUrl(API.list(a.id, c.id)),
        byAge: Object.fromEntries(c.ages.map((n) => [String(n), absUrl(API.age(a.id, c.id, n))])),
      })),
    })),
  };
}

/** エージェントに渡す頼み方の文例 */
export const agentPrompt = () =>
  [
    `${absUrl(API.guide)} の決まりを読み、このサイトのデータを使って候補を出してください。`,
    "",
    "・住んでいる町：〇〇区〇〇町",
    "・子どもの生まれた年月：〇年〇月",
    "・入園したい時期：〇年〇月",
    "・お迎えの時刻：〇時〇分まで",
    "",
    "家から近い順に5園、距離・対象クラス・空きとその対象月・預かりの終わり・施設ページのURLを表にしてください。未確認の項目は未確認と書いてください。",
  ].join("\n");

/** llms.txt の本文 */
export function agentGuideText() {
  const lines = [
    `# ${SITE.name}`,
    "",
    "> 自治体の公式情報から集めた保育園・学童のデータ。値ごとに出どころと確認日があります。",
    "",
    "## データ",
    "",
    `- [データの入口](${absUrl(API.index)}): 地域の一覧と項目の説明`,
  ];
  for (const a of activeAreas) {
    for (const c of a.categories) lines.push(`- [${a.name}の${c.label}](${absUrl(API.list(a.id, c.id))}): ${c.count}件`);
  }
  lines.push("", "## 読むときの決まり", "", ...AGENT_RULES.map((r) => `- ${r}`), "");
  return lines.join("\n");
}

/** 施設ページの構造化データ（schema.org ChildCare） */
export function facilityJsonLd(f: Facility) {
  const area = activeAreas.find((a) => a.id === f.ward);
  const street = shortAddress(f)?.replace(/^第.園舎：/, "");
  const loc = f.location.value;
  const official = f.links.official.value;
  return {
    "@context": "https://schema.org",
    "@type": "ChildCare",
    name: f.name,
    url: absUrl(`/f/${f.id}/`),
    address: {
      "@type": "PostalAddress",
      addressCountry: "JP",
      addressRegion: PREFECTURES.find((p) => p.id === area?.prefecture)?.name,
      addressLocality: area?.name,
      ...(street ? { streetAddress: street } : {}),
    },
    ...(loc ? { geo: { "@type": "GeoCoordinates", latitude: loc.lat, longitude: loc.lng } } : {}),
    // 家庭的保育は個人宅なので、検索エンジン向けのデータには電話番号を入れない
    ...(f.phone.value && f.type !== "katei" ? { telephone: f.phone.value } : {}),
    ...(official ? { sameAs: official } : {}),
  };
}
