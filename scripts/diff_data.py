"""週次チェックで集め直したデータと main のデータを比べ、実質的な変化を Markdown で書き出す。

使い方: python3 scripts/diff_data.py <前のdata/facilities> <新しいdata/facilities> <出力.md>
- 確認日（checked）だけの変化は無視する。それ以外（値・出どころ・注記）が変わった施設だけを書く。
- 実質的な変化があれば標準出力に changed=true、なければ changed=false を出す（GITHUB_OUTPUT 用）。
"""
import glob, json, os, sys

WARD = {"adachi": "足立区", "taito": "台東区"}
TYPE = {
    "ninka": "認可保育所", "kodomoen": "認定こども園", "shokibo": "小規模保育", "jigyosho": "事業所内保育",
    "katei": "家庭的保育（保育ママ）", "ninsho": "東京都認証保育所", "gakudo_ku": "区の学童（公設）",
    "gakudo_min": "民設の学童", "houkago": "放課後子ども教室",
}
LABEL = {
    "name": "施設名", "listedName": "区の一覧での表記", "management": "運営", "type": "種別", "category": "区分",
    "address": "住所", "station": "最寄り駅", "phone": "電話", "ages": "対象", "ageRange": "対象（年齢・学年の範囲）",
    "capacity": "定員", "hours.weekday": "平日の時間", "hours.weekdayEnd": "平日の終了時刻",
    "hours.extension": "延長", "hours.extensionEnd": "延長の終了時刻", "hours.saturday": "土曜",
    "hours.vacation": "長期休み", "fees.table": "区の保育料表", "fees.basic": "保育料", "fees.own": "施設ごとの実費",
    "fees.extensionFee": "延長料金", "fees.monthly": "月額", "fees.snack": "おやつ代", "fees.extension": "延長料金",
    "pickup": "送迎", "vacancy": "空き", "application.method": "申込方法", "application.deadline": "締切",
    "links.official": "公式リンク", "links.intro": "施設紹介", "notice": "お知らせ", "operator": "運営者",
}
LIMIT = 60000  # PR 本文・コメント 1件あたりの上限（GitHub は 65536 文字）


def load(d):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        for r in json.load(open(p)):
            out[r["id"]] = r
    return out


def is_field(o):
    return isinstance(o, dict) and "checked" in o and "value" in o


def fields(r, prefix=""):
    """施設1件を {パス: 値} に平らにする。確認日は落とす。"""
    out = {}
    for k, v in r.items():
        p = f"{prefix}.{k}" if prefix else k
        if is_field(v):
            out[p] = {kk: vv for kk, vv in v.items() if kk != "checked"}
        elif isinstance(v, dict):
            out.update(fields(v, p))
        else:
            out[p] = {"value": v}
    return out


def show(v, unit="歳"):
    if v is None:
        return "未確認"
    if isinstance(v, dict) and "label" in v and "byAge" in v:
        ages = v.get("byAge") or {}
        per = " / ".join(f"{a}{unit}:{'—' if n is None else n}" for a, n in sorted(ages.items()))
        total = v.get("totalText") or ("—" if v.get("total") is None else v["total"])
        return f"{v['label']} 計{total}" + (f"（{per}）" if per else "") + (f"・{v['asOf']}時点" if v.get("asOf") else "")
    if isinstance(v, dict) and set(v) == {"min", "max"}:
        return f"{v['min']}〜{v['max']}"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def cell(f, unit="歳"):
    s = show(f.get("value"), unit)
    if f.get("note"):
        s += f"（注記: {f['note']}）"
    return s.replace("|", "｜").replace("\n", " ")


def head(r):
    return f"{WARD.get(r['ward'], r['ward'])}・{TYPE.get(r['type'], r['type'])}「{r['name']}」（`{r['id']}`）"


def src(*fs):
    urls = []
    for f in fs:
        u = f and f.get("source")
        if u and u not in urls:
            urls.append(u)
    return " / ".join(urls) if urls else "—"


def main(old_dir, new_dir, out_path):
    old, new = load(old_dir), load(new_dir)
    blocks = []
    added = [i for i in new if i not in old]
    removed = [i for i in old if i not in new]
    changed = []
    for i in new:
        if i in old:
            a, b = fields(old[i]), fields(new[i])
            diffs = [(k, a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
            if diffs:
                changed.append((i, diffs))
    for i in added:
        r = new[i]
        blocks.append(f"### 追加 {head(r)}\n- 住所: {cell(r['address'])}\n- 出どころ: {src(r['address'], r['phone'])}\n")
    for i in removed:
        r = old[i]
        blocks.append(f"### 削除 {head(r)}\n- 区の一覧から見つからなくなりました（前の住所: {cell(r['address'])}）\n- 前の出どころ: {src(r['address'])}\n")
    for i, diffs in changed:
        lines = [f"### 変更 {head(new[i])}", "| 項目 | 前 | 後 | 出どころ |", "|---|---|---|---|"]
        for k, a, b in diffs:
            a, b = a or {"value": None}, b or {"value": None}
            unit = "年" if new[i]["category"] == "gakudo" else "歳"
            if a.get("value") == b.get("value") and a.get("note") == b.get("note"):
                what = f"出どころURLだけ変更（前: {a.get('source') or '—'}）"
                lines.append(f"| {LABEL.get(k, k)} | {what} | {cell(b, unit)} | {src(b)} |")
            else:
                lines.append(f"| {LABEL.get(k, k)} | {cell(a, unit)} | {cell(b, unit)} | {src(b, a)} |")
        blocks.append("\n".join(lines) + "\n")

    has = bool(blocks)
    summary = (
        f"週次チェックで区の公式ページを読み直した結果、確認日以外の変化がありました。\n\n"
        f"- 追加 {len(added)}件 / 削除 {len(removed)}件 / 変更 {len(changed)}件（全{len(new)}件中）\n"
        f"- 「前」は main の値、「後」は今回集め直した値です。値が空のものはサイトで「未確認」と表示されます。\n"
        f"- このPRをマージすると公開サイトに反映されます。マージ前に内容を確認してください。\n\n"
    )
    parts, cur = [], summary
    for b in blocks:
        if len(cur) + len(b) > LIMIT:
            parts.append(cur)
            cur = "（続き）\n\n"
        cur += b + "\n"
    parts.append(cur)
    if len(parts) > 1:
        parts[0] += f"\n\n変更点が多いため、続きを {len(parts) - 1} 件のコメントに分けて載せています。\n"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    for n, p in enumerate(parts):
        with open(out_path if n == 0 else f"{out_path}.{n}", "w") as f:
            f.write(p)
    print(f"changed={'true' if has else 'false'}")
    print(f"parts={len(parts)}")
    print(f"summary=追加{len(added)} 削除{len(removed)} 変更{len(changed)}", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
