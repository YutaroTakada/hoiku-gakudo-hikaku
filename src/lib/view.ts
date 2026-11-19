import { ROWS, labelFor } from "../config/fields";
import type { Facility } from "./schema";
import { isStale } from "./format";

export type Row = {
  group: string;
  label: string;
  text: string | null;
  source: string | null;
  checked: string | null;
  note?: string;
  stale: boolean;
  link?: string;
};

/** 詳細と比較で共通に使う表示行。値がないものは text=null（「未確認」と出す）。 */
export function rows(f: Facility): Row[] {
  const out: Row[] = [];
  for (const d of ROWS) {
    if (d.categories && !d.categories.includes(f.category)) continue;
    if (d.when && !d.when(f)) continue;
    const fld = d.get(f);
    if (!fld) continue;
    const text = fld.value === null ? null : d.fmt ? d.fmt(fld.value, f) : String(fld.value);
    let link: string | undefined;
    if (text !== null && d.link === "url") link = String(fld.value);
    if (text !== null && d.link === "tel") link = "tel:" + String(fld.value).replace(/[^0-9+]/g, "");
    out.push({
      group: d.group,
      label: labelFor(d.label, f.category),
      text,
      source: fld.source,
      checked: fld.checked,
      ...(fld.note ? { note: fld.note } : {}),
      stale: fld.value !== null && isStale(fld.checked),
      ...(link ? { link } : {}),
    });
  }
  return out;
}

/** 見学で聞くこと。口コミや評価の代わりに、自分で確かめるための問い。 */
export function checklist(f: Facility): string[] {
  if (f.category === "gakudo") {
    const base = [
      "学校からの移動の付き添い。雨の日はどうなるか",
      "一人で帰れる時刻と、お迎えが要る時刻",
      "おやつの内容と費用、アレルギーへの対応",
      "長期休みの昼食（お弁当か、注文できるか）",
      "宿題の時間。習い事への途中外出",
      "1室の人数と職員の人数",
      "災害時・急な休校のときの連絡と引き渡し",
    ];
    if (f.type === "gakudo_min") base.push("月額以外の費用（入会金・教材費・行事費）", "自宅までの送りの有無と料金");
    if (f.type === "houkago") base.push("学童保育室との違い（時間・おやつ・長期休み）", "雨の日の活動場所");
    return base;
  }
  const base = [
    "通う時間帯の様子（朝の受け入れ、夕方のお迎え）",
    "延長保育の空きと、使える年齢",
    "給食・離乳食・アレルギーへの対応",
    "持ち物と、施設で用意するもの（おむつ・布団・着替え）",
    "保育料以外の費用（行事費・教材費・おむつのサブスク）",
    "園庭の有無。ないなら外遊びの場所",
    "病気のときの連絡と、お迎えを求められる目安",
    "災害時の避難先と引き渡し",
  ];
  if (f.type === "shokibo" || f.type === "katei" || f.type === "jigyosho") base.push("3歳からの転園先（連携施設）");
  if (f.type === "ninsho") base.push("月額保育料と、区の助成後の実際の負担額", "契約と退所の手続き");
  if (f.type === "kodomoen") base.push("入園料・制服などの初期費用", "土曜日の開所");
  return base;
}
