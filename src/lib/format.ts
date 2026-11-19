import { TYPES, type Facility, type Field } from "./schema";

export const WARDS = { adachi: "足立区", taito: "台東区" } as const;
export const CATEGORIES = { hoiku: "保育園", gakudo: "学童・放課後" } as const;
export const STALE_DAYS = 90;
export const BUILD_DATE = new Date();

export const href = (p: string) => import.meta.env.BASE_URL.replace(/\/$/, "") + p;
export const typeLabel = (f: Facility) => TYPES[f.type];

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

export const yen = (n: number) => (n === 0 ? "無料" : `${n.toLocaleString("ja-JP")}円`);

export function mapUrl(f: Facility): string {
  const w = WARDS[f.ward];
  const addr = f.address.value?.split("（")[0].split(" ／ ")[0].replace(/^第.園舎：/, "") ?? "";
  // 家庭的保育は個人宅のため町名だけで検索する
  const q = f.type === "katei" ? `東京都${w}${addr}` : `${f.name} 東京都${w}${addr}`;
  return "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(q);
}

export function rangeText(f: Facility): string | null {
  const r = f.ageRange.value;
  if (!r) return null;
  return f.category === "hoiku" ? `${r.min}〜${r.max}歳児` : `${r.min}〜${r.max}年生`;
}

export function vacancyText(f: Facility): string | null {
  const v = f.vacancy.value;
  if (!v) return null;
  if (v.total === null) return v.totalText ?? null;
  if (v.byAge) {
    const parts = Object.entries(v.byAge)
      .filter(([, n]) => (n ?? 0) > 0)
      .map(([a, n]) => (f.category === "hoiku" ? `${a}歳児${n}` : `${a}年${n}`));
    return v.total > 0 ? `計${v.total}人（${parts.join("・")}）` : "0人";
  }
  return v.totalText ?? `${v.total}人`;
}

/** 年齢別の内訳（0 も含めて全部） */
export function vacancyByAge(f: Facility): string | null {
  const v = f.vacancy.value;
  if (!v?.byAge) return null;
  const r = f.ageRange.value;
  const parts = Object.entries(v.byAge).filter(([a]) => !r || (+a >= r.min && +a <= r.max)).map(([a, n]) => `${a}歳児 ${n === null ? "募集なし/記載なし" : n + "人"}`);
  return parts.join("、");
}

export function vacancyAsOf(f: Facility): string {
  const v = f.vacancy.value;
  if (!v) return "";
  return `${v.label}${v.asOf ? `・${jpDate(v.asOf)}時点` : ""}`;
}

/** 最も遅いお迎え時刻（延長を含む）。並べ替え用。 */
export function latestEnd(f: Facility): string | null {
  const c = [f.hours.extensionEnd.value, f.hours.weekdayEnd.value].filter(Boolean) as string[];
  if (!c.length) return null;
  return c.sort((a, b) => toMin(b) - toMin(a))[0];
}
export const toMin = (t: string) => {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
};

export function hasExtension(f: Facility): boolean {
  const v = f.hours.extension.value;
  return !!v && !v.startsWith("なし");
}

export function monthlyFee(f: Facility): number | null {
  if (f.category === "gakudo") return f.fees.monthly?.value ?? null;
  // 認可・地域型・こども園は区の基本保育料が無料（延長料金などは別）
  if (f.fees.basic?.value && /無料|無償/.test(f.fees.basic.value)) return 0;
  return null;
}

export type Row = { group: string; label: string; text: string | null; source: string | null; checked: string | null; note?: string; stale: boolean; link?: string };

function row(group: string, label: string, fld: Field<unknown> | undefined, text?: (v: any) => string | null, link?: boolean): Row | null {
  if (!fld) return null;
  const t = fld.value === null ? null : text ? text(fld.value) : String(fld.value);
  return {
    group,
    label,
    text: t,
    source: fld.source,
    checked: fld.checked,
    note: fld.note,
    stale: fld.value !== null && isStale(fld.checked),
    link: link && fld.value ? String(fld.value) : undefined,
  };
}

/** 詳細と比較で共通に使う表示行。値がないものは text=null（「未確認」と出す）。 */
export function rows(f: Facility): Row[] {
  const H = "預かり時間";
  const P = "料金";
  const r: (Row | null)[] = [
    row("基本情報", "住所", f.address),
    row("基本情報", "最寄り駅", f.station),
    row("基本情報", "電話", f.phone),
    f.operator ? row("基本情報", "運営事業者", f.operator) : null,
    row("対象と定員", f.category === "hoiku" ? "対象年齢" : "対象学年", f.ages),
    row("対象と定員", "定員", f.capacity, (v) => `${v}人`),
    row(H, "平日の基本時間", f.hours.weekday),
    row(H, "延長", f.hours.extension),
    row(H, "延長の終わり", f.hours.extensionEnd),
    row(H, "土曜", f.hours.saturday),
    f.category === "gakudo" ? row(H, "長期休み", f.hours.vacation ?? { value: null, source: null, checked: null }) : null,
  ];
  if (f.category === "hoiku") {
    r.push(
      row(P, "保育料", f.fees.basic ?? { value: null, source: null, checked: null }),
      row(P, "区の保育料表", f.fees.table ?? { value: null, source: null, checked: null }, () => "区のページを開く", true),
      row(P, "延長保育料", f.fees.extensionFee ?? { value: null, source: null, checked: null }),
      row(P, "施設独自の費用", f.fees.own ?? { value: null, source: null, checked: null }),
    );
  } else {
    r.push(
      row(P, "月額", f.fees.monthly ?? { value: null, source: null, checked: null }, (v) => yen(v)),
      row(P, "おやつ代", f.fees.snack ?? { value: null, source: null, checked: null }, (v) => `月額${yen(v)}`),
      row(P, "延長料金", f.fees.extension ?? { value: null, source: null, checked: null }),
    );
  }
  r.push(
    row("送迎", f.category === "gakudo" ? "お迎え・送り" : "送迎", f.pickup),
    row("空き状況", "区の公表値", f.vacancy, () => vacancyText(f)),
    ...(f.vacancy.value?.byAge ? [row("空き状況", "年齢別", f.vacancy, () => vacancyByAge(f))] : []),
    row("空き状況", "発表", f.vacancy, () => vacancyAsOf(f)),
    row("申込", "申込方法", f.application.method),
    row("申込", "締切", f.application.deadline),
    row("リンク", "公式ページ", f.links.official, () => "開く", true),
    row("リンク", "区の施設紹介", f.links.intro, () => "開く", true),
  );
  return r.filter(Boolean) as Row[];
}

/** 見学で聞くこと。口コミや評価の代わりに、自分で確かめるための問い。 */
export function checklist(f: Facility): string[] {
  if (f.category === "gakudo") {
    const base = [
      "学校からの移動は誰が付き添うか。雨の日はどうなるか",
      "帰りは一人で帰れるのは何時までか。お迎えが必要になる時刻",
      "おやつの内容と費用、アレルギーへの対応",
      "長期休みの昼食（お弁当か、注文できるか）",
      "宿題の時間があるか。習い事への途中外出はできるか",
      "1室の人数と職員の人数",
      "災害時や急な休校のときの連絡と引き渡しの方法",
    ];
    if (f.type === "gakudo_min") base.push("月額以外にかかる費用（入会金・教材費・行事費）", "自宅までの送りのサービスがあるか。料金");
    if (f.type === "houkago") base.push("学童保育室との違い（時間・おやつ・長期休み）", "雨の日の活動場所");
    return base;
  }
  const base = [
    "通う時間帯の様子（朝の受け入れ、夕方のお迎え）",
    "延長保育の空きと、使える年齢",
    "給食・離乳食・アレルギーへの対応",
    "おむつ、布団、着替えなど持ち物と、施設で用意するもの",
    "保育料以外にかかる費用（行事費・教材費・おむつのサブスクなど）",
    "園庭の有無。ないなら外遊びの場所",
    "病気のときの連絡と、お迎えを求められる目安",
    "災害時の避難先と引き渡しの方法",
  ];
  if (f.type === "shokibo" || f.type === "katei" || f.type === "jigyosho") base.push("3歳からの転園先（連携施設）があるか");
  if (f.type === "ninsho") base.push("月額保育料と、区の助成を受けた後の実際の負担額", "契約と退所の手続き");
  if (f.type === "kodomoen") base.push("入園料・制服などの初期費用", "土曜日の開所");
  return base;
}
