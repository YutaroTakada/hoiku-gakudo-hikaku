"""新座市の公式ページ・PDFから保育施設と放課後児童保育室を集める。

- 施設の一覧と番号：保育園・認定こども園の一覧PDF、小規模保育施設の一覧PDF
- 施設ごとの値：地域別の施設案内PDF（住所・電話・HP・定員・保育年齢・開園時間・3歳児以上給食費）
- 空き：保育施設待機児童数一覧PDF（毎月1日現在）の「募集」列
- 家庭保育室：認可外保育施設及び家庭保育室等のページの「市内家庭保育室」表
- 放課後児童保育室：放課後児童保育室一覧ページ（建物ごと）＋ご案内ページ
推測で値を埋めない。読めない値は U()（未確認）。
"""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from lib import F, U, fid, clean, nfkc, fetch_text, pdf_text

BASE = "https://www.city.niiza.lg.jp"
K = BASE + "/site/kosodate"
SRC = {
    "hoiku_top": K + "/shinaihoikujoichiran.html",
    "vacancy_page": K + "/taikizidou3.html",
    "apply": K + "/hoikusisetugoannai9.html",
    "katei": K + "/kateihoikushitsuichiran.html",
    "gakudo_list": K + "/hokagojidohoikushitsuichiran.html",
    "gakudo_about": K + "/houkago-annai.html",
    "gakudo_apply": K + "/hoikugakudouuketsuke.html",
    "gakudo_pickup": K + "/sougei.html",
}
AREA = "niiza"


def soup(url):
    return BeautifulSoup(fetch_text(url), "html.parser")


def main_body(s):
    return s.find(id="main_body") or s


def attachments(page):
    """ページ本文の PDF リンクを (表示名, 絶対URL) で返す。"""
    s = main_body(soup(page))
    out = []
    for a in s.find_all("a"):
        h = a.get("href") or ""
        if "/uploaded/attachment/" in h and h.endswith(".pdf"):
            out.append((clean(a.get_text()), urljoin(page, h)))
    return out


def pick(links, *words):
    for name, url in links:
        if all(w in name for w in words):
            return url
    return None


def page_says(url, value, needles):
    """固定の要約文を、ページ本文に根拠の文言がすべて残っているときだけ使う。
    年度が替わるなどして記載が変わったら未確認にする（古い期限を新しい確認日で載せない）。"""
    text = re.sub(r"[\s\u200b]", "", nfkc(main_body(soup(url)).get_text()))
    lost = [n for n in needles if n not in text]
    if lost:
        print(f"新座市: {url} の記載が変わったため申込期限は未確認:", lost)
        return U("市のページの記載が変わったため再確認が必要")
    return F(value, url)


def base_record(typ, category, management, name, listed=None):
    return {
        "id": fid(AREA, typ, name),
        "ward": AREA,
        "category": category,
        "type": typ,
        "management": management,
        "name": name,
        "listedName": listed or name,
    }


def zen2han(s):
    return nfkc(s)


def phone(s):
    s = nfkc(s)
    m = re.search(r"(0\d{1,3})\s*[\(（-]\s*(\d{2,4})\s*[\)）-]\s*(\d{3,4})", s)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def squash(s):
    """PDF の字間スペース（日本語の間）を詰める。"""
    s = nfkc(s)
    return re.sub(r"(?<=[^\x00-\x7f])\s+(?=[^\x00-\x7f])", "", s).strip()


# ───────── 一覧PDF（番号→施設名・公立かどうか・種別） ─────────

LIST_AGE = {}


def facility_list(urls):
    """一覧PDFの表から {番号: (名前, 公立か, 種別)} を作る。種別はPDFごと（名前が「認定こども園」で始まれば認定こども園）。"""
    res = {}
    for url, default_type in urls:
        text = pdf_text(url)
        on = False
        for raw in text.split("\n"):
            line = nfkc(raw)
            if re.search(r"【(保育園|認定こども園|小規模保育施設)】", line):
                on = True
            if not on:
                continue
            # 1行に2列分並ぶ：「№ 施設名 月齢」。施設名は数字で始まらない
            for m in re.finditer(r"(?:^|\s)(\d{1,2})\s+([^\d\s][^~]*?)\s+(\d+か月~|\d+歳児クラス~|\d+日目~|開設予定)", line):
                no, name = int(m.group(1)), squash(m.group(2))
                public = "(公立)" in name
                name = name.replace("(公立)", "").strip()
                typ = "kodomoen" if name.startswith("認定こども園") else default_type
                res.setdefault(no, (name, public, typ))
                LIST_AGE.setdefault(no, m.group(3).replace("~", "〜"))
    return res


# ───────── 地域別PDF（施設ごとの値） ─────────

AGE_HEAD = re.compile(r"定員\s+0歳\s+1歳\s+2歳\s+3歳\s+4歳\s+5歳")


def region_blocks(url, region):
    lines = [nfkc(x) for x in pdf_text(url).split("\n")]
    anchors = [i for i, l in enumerate(lines) if re.search(r"■住\s*所", l)]
    used = set()
    out = []
    for k, i in enumerate(anchors):
        end = anchors[k + 1] - 3 if k + 1 < len(anchors) else len(lines)
        # 番号：住所行の前後で、この地域の「地域-番号」のうち最も近いもの
        best = None
        for j in range(max(0, i - 3), min(len(lines), i + 3)):
            # 「■」より左の施設名側だけを見る。住所の番地（2-31-7 など）は拾わない
            for m in re.finditer(r"(?<![\d:\-])([1-6])\s*-\s*(\d{1,2})(?![\d:]|\s*-\s*\d)", lines[j].split("■")[0]):
                if int(m.group(1)) != region or int(m.group(2)) in used:
                    continue
                d = abs(j - i)
                if best is None or d < best[0]:
                    best = (d, int(m.group(2)))
        no = best[1] if best else None
        if no is not None:
            used.add(no)
        out.append((no, lines[max(0, i - 4):end], i - max(0, i - 4)))
    return out


def block_lines(block, at):
    """住所行の前後の行を (住所行からの距離, 左側の文字) で返す。隣り合う2行・3行をつないだものも入れる（施設名が2行に分かれる場合）。"""
    idx = list(range(max(0, at - 4), min(len(block), at + 4)))
    left = {i: name_key(block[i].split("■")[0]) for i in idx}
    out = []
    for i in idx:
        out.append((abs(i - at), left[i]))
        if i + 1 in left:
            out.append((min(abs(i - at), abs(i + 1 - at)) + 0.5, left[i] + left[i + 1]))
        if i + 2 in left:
            out.append((min(abs(i - at), abs(i + 2 - at)) + 0.7, left[i] + left[i + 1] + left[i + 2]))
    return out


def match_name(block, at, names):
    """施設名で照合。ほかの候補名に含まれる短い名前（「新座保育園」と「まなびぐら新座保育園」など）は外し、住所行に近いものを選ぶ。"""
    found = {}
    for d, text in block_lines(block, at):
        for n, (name, _, _) in names.items():
            keys = {name_key(name), name_key(re.sub(r"^(保育園|認定こども園)", "", name))}
            if any(k and k in text for k in keys):
                found[n] = min(found.get(n, 99), d)
    keys = {n: name_key(names[n][0]) for n in found}
    keep = [n for n in found if not any(n != m and keys[n] in keys[m] and found[m] <= found[n] + 1.5 for m in found)]
    if not keep:
        return None
    near = min(found[n] for n in keep)
    return max((n for n in keep if found[n] <= near + 1), key=lambda n: (len(keys[n]), -found[n]))


def parse_block(block, at):
    """地域別PDFの施設1件分から値を読む。読めないものは None。"""
    text = "\n".join(block)
    v = {}
    m = re.search(r"■住\s*所\s*[:：]\s*(?:〒\s*\d{3}-\d{4})?\s*(.+?)(?:\s{3,}|■|$)", block[at])
    if m:
        raw = re.sub(r"^埼玉県", "", m.group(1).strip())
        if re.search(r"新 座 市", raw):  # 1文字ずつ空白が入っている行は空白を全部詰める
            raw = re.sub(r"\s+", "", raw)
        raw = re.sub(r"\s*(-|－|丁目)\s*", r"\1", raw).replace("－", "-")
        raw = re.sub(r"(\d+)丁目(\d)", r"\1-\2", raw)
        raw = re.sub(r"^新座市\s*", "", raw)
        # 番地まで（町名＋数字とハイフン）と建物名を分ける。建物名の前は空白1つ
        mm = re.match(r"^(\D+?)\s*(\d+(?:-\d+)*)\s*(.*)$", raw)
        if mm and re.fullmatch(r"[^\d\s]+", mm.group(1)):
            bld = re.sub(r"\s+", "", mm.group(3))
            v["address"] = mm.group(1) + mm.group(2) + (" " + bld if bld else "")
    for l in block:
        if "■電" in l and "phone" not in v:
            p = phone(l.split("FAX")[0].split("■FAX")[0])
            if p:
                v["phone"] = p
        if "■ホームページ" in l and "hp" not in v:
            m = re.search(r"■ホームページ\s*[:：]\s*([A-Za-z0-9:/._~%?#=&+-]+)", l)
            if m and re.match(r"(https?://|[a-z0-9-]+\.[a-z])", m.group(1)):
                u = m.group(1)
                v["hp"] = u if u.startswith("http") else "https://" + u
    # 運営法人：見出し近くの括弧書き
    for l in block[: at + 4]:
        m = re.search(r"[（(]\s*((?:社\s*会\s*福\s*祉\s*法\s*人|株\s*式\s*会\s*社|学\s*校\s*法\s*人|有\s*限\s*会\s*社|一\s*般|特\s*定|合\s*同|新\s*座\s*市)[^）)]*?)\s*[）)]", l)
        if m:
            v["operator"] = squash(m.group(1))
            break
    # 定員と年齢別定員
    for k, l in enumerate(block):
        if AGE_HEAD.search(l):
            for l2 in block[k + 1:k + 4]:
                m = re.search(r"\(\s*(\d+)\s*名\s*\)\s+(.*)", l2)
                if m:
                    v["capacity"] = int(m.group(1))
                    cells = re.findall(r"(\d+)\s*名|(－|-|―)", m.group(2))[:6]
                    if len(cells) == 6:
                        v["ageCaps"] = [int(a) if a else 0 for a, _ in cells]
                    break
            # 認定こども園：「保育園」の行の次に年齢別定員、その次に「(定員 N 名)」（保育利用）
            if "capacity" not in v:
                for j in range(k + 1, min(len(block), k + 8)):
                    if re.match(r"^\s*保育園\b", block[j]) and j + 2 < len(block):
                        cells = re.findall(r"(\d+)\s*名|(?<!\S)(－|-|―)(?!\S)", block[j + 1])[:6]
                        mc = re.search(r"\(定員\s*(\d+)\s*名\)", block[j + 2])
                        if mc and len(cells) == 6:
                            v["capacity"] = int(mc.group(1))
                            v["capacityNote"] = "保育利用の定員"
                            v["ageCaps"] = [int(a) if a else 0 for a, _ in cells]
                        break
            # 開園時間（定員の見出し行から数行に出る）
            for l2 in block[k:k + 9]:
                m = re.search(r"平日\s+(\d{1,2}:\d{2})\s*~\s*(\d{1,2}:\d{2})", l2)
                if m and "open" not in v:
                    v["open"] = (m.group(1), m.group(2))
                m = re.search(r"土曜\s+(\d{1,2}:\d{2})\s*~\s*(\d{1,2}:\d{2})", l2)
                if m and "sat" not in v:
                    v["sat"] = f"{m.group(1)}〜{m.group(2)}"
                if re.search(r"土曜保育なし", l2) and "sat" not in v:
                    v["sat"] = "土曜保育なし"
            break
    m = re.search(r"保育年齢\s+(?:生後)?(\d+\s*(?:か月|日目|歳児クラス))\s*(?:~|から)", text)
    if m:
        v["ageStart"] = re.sub(r"\s+", "", m.group(1)) + "〜"
    m = re.search(r"3歳児(?:クラス)?以上給食費\s+(保育利用\s*)?([\d,]+\s*円\s*/\s*月)", text)
    if m:
        v["lunch"] = ("保育利用 " if m.group(1) else "") + re.sub(r"\s+", "", m.group(2))
    return v


# ───────── 空き（待機児童数一覧PDFの「募集」） ─────────

def vacancy_map():
    links = attachments(SRC["vacancy_page"])
    url = next((u for n, u in links if "待機児童数一覧" in n), None)
    if not url:
        return {}, None, None
    text = pdf_text(url)
    m = re.search(r"令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日現在", nfkc(text))
    as_of = f"{2018 + int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    lines = [nfkc(x) for x in text.split("\n")]
    res = {}
    current = [None, None]
    for k, l in enumerate(lines):
        # 施設名の行：見出し直前（次行が「入所児童数」）
        if k + 1 < len(lines) and "入所児童数" in lines[k + 1] and l.strip() and not l.strip().startswith(("【", "年齢")):
            names = [squash(x) for x in re.split(r"\s{3,}", l.strip()) if x.strip()]
            if any(x.endswith("計") or "総合計" in x for x in names):
                current = [None, None]
                continue
            current = (names + [None])[:2]
            for n in current:
                if n:
                    res.setdefault(n, {})
            continue
        m = re.match(r"^\s*([0-5])\s+(.*)$", l)
        if m and current[0]:
            nums = re.findall(r"\d[\d,]*", l)
            sides = [nums[0:10], nums[10:20]]
            for side, n in zip(sides, current):
                if n and len(side) == 10:
                    res[n][side[0]] = int(side[5].replace(",", ""))
    return {n: d for n, d in res.items() if d}, url, as_of


def name_key(s):
    return re.sub(r"[\s・･]", "", nfkc(s))


def vac_key(s):
    """待機児童数一覧と施設一覧の表記ゆれ（第二/第2、「保育室」「保育園」の前置き、「(保育利用定員)」）をそろえる。"""
    k = name_key(s).replace("第二", "第2")
    k = re.sub(r"\(保育利用定員\)$", "", k)
    return re.sub(r"^(保育園|保育室|認定こども園)", "", k)


def vac_field(vac, url, as_of, name, ages):
    d = None
    for n, x in vac.items():
        if vac_key(n) == vac_key(name):
            d = x
    if not d:
        return U("市の待機児童数一覧に記載なし")
    by = {a: d.get(a) for a in sorted(d) if ages is None or int(a) in ages}
    total = sum(x for x in by.values() if x is not None)
    return F({"byAge": by, "total": total, "label": "募集", "asOf": as_of}, url,
             "市の待機児童数一覧の「募集」列（年齢別）。総定員を超える場合などは入所できないことがあります")


# ───────── 保育施設 ─────────

TYPE_BY_SECTION = {"保育園": "ninka", "認定こども園": "kodomoen", "小規模保育施設": "shokibo"}


def collect_hoiku():
    links = attachments(SRC["hoiku_top"])
    list_hoiku = pick(links, "保育園", "一覧")
    list_small = pick(links, "小規模保育施設", "一覧")
    new_pdf = pick(links, "施設概要")
    regions = []
    for r in range(1, 7):
        u = pick(links, f"地域{r}")
        if u:
            regions.append((r, u))
    if not (list_hoiku and list_small and len(regions) == 6):
        raise SystemExit("新座市：施設一覧・地域別PDFのリンクが見つかりません")
    names = facility_list([(list_hoiku, "ninka"), (list_small, "shokibo")])
    blocks, problems = {}, []
    sources = regions + ([(0, new_pdf)] if new_pdf else [])
    for r, u in sources:
        for no, block, at in region_blocks(u, r):
            # 施設名で照合（番号は確認に使う）
            hit = match_name(block, at, names)
            if hit is None:
                problems.append(f"{u} 地域{r} 番号{no}: 施設名が一覧と一致しない")
                continue
            if r and no != hit:
                # 番号と施設名の両方が一致したときだけ使う（取り違えで別施設の値を載せない）
                problems.append(f"{u} 地域{r}: 番号{no}と施設名（{names[hit][0]}=番号{hit}）が食い違うため使わない（値は未確認）")
                continue
            if hit in blocks and r:
                problems.append(f"{u} 地域{r}: {names[hit][0]} が2回見つかったため2件目は使わない")
            blocks.setdefault(hit, (u, block, at))
    for p in problems:
        print("新座市:", p)
    missing = [names[n][0] for n in names if n not in blocks]
    if missing:
        print("新座市: 施設案内PDFで見つからない施設（値は未確認）:", missing)
    vac, vac_url, as_of = vacancy_map()
    fee_url = pick(attachments(SRC["apply"]), "保育料について")
    hoiku_deadline = page_says(
        SRC["apply"],
        "令和9年4月入所（一次選考）：令和8年9月1日〜11月19日（郵送は保育課必着、電子は23時59分まで）。二次選考：令和9年1月4日〜29日",
        ["令和9年4月1日から", "4月1日入所の申込期間", "令和8年9月1日(火曜日)~11月19日(木曜日)<保育課必着>", "令和9年1月4日(月曜日)~同月29日(金曜日)"])
    out = []
    for no in sorted(names):
        name, public, typ = names[no]
        rec = base_record(typ, "hoiku", "公立" if public else "民間", name)
        src, block, at = blocks.get(no, (None, None, None))
        v = parse_block(block, at) if block else {}
        # 照合の確かめ：施設案内の「保育年齢」と一覧の「月齢」が食い違えば、その施設の値は使わない
        if v and LIST_AGE.get(no) not in (None, "開設予定") and v.get("ageStart") != LIST_AGE[no]:
            print(f"新座市: {name} の保育年齢が一覧（{LIST_AGE[no]}）と施設案内（{v.get('ageStart')}）で食い違うため値を使いません")
            src, v = None, {}
        S = src
        rec["address"] = F(v["address"], S) if v.get("address") else U()
        rec["phone"] = F(v["phone"], S) if v.get("phone") else U()
        rec["station"] = U()
        if v.get("operator"):
            rec["operator"] = F(v["operator"], S)
        caps = v.get("ageCaps")
        ages = None
        if caps:
            ages = [a for a, c in enumerate(caps) if c > 0]
        start = v.get("ageStart")
        rec["ages"] = F(start + ("（0〜2歳児クラス）" if typ == "shokibo" else ""), S, "市の施設案内の「保育年齢」") if start else U()
        if ages:
            rec["ageRange"] = F({"min": min(ages), "max": max(ages)}, S, "年齢別定員がある年齢")
        else:
            rec["ageRange"] = U()
        rec["capacity"] = F(v["capacity"], S, v.get("capacityNote")) if v.get("capacity") else U()
        if v.get("open"):
            a, b = v["open"]
            rec["hours"] = {
                "weekday": F(f"{a}〜{b}（開園時間）", S, "延長保育の時間を含む開園時間。保育短時間・標準時間の区分は施設案内PDFを参照"),
                "weekdayEnd": F(b, S, "開園時間の終わり（延長保育を含む）"),
                "extension": U("延長保育の時間帯と料金は施設案内PDFの表を参照"),
                "extensionEnd": U(),
                "saturday": F(v["sat"], S) if v.get("sat") else U(),
            }
        else:
            rec["hours"] = {"weekday": U(), "weekdayEnd": U(), "extension": U(), "extensionEnd": U(),
                            "saturday": F(v["sat"], S) if v.get("sat") else U()}
        rec["fees"] = {
            "table": F(fee_url, fee_url) if fee_url else U(),
            "basic": F("3〜5歳児クラスは無償化により保育料なし。0〜2歳児クラスは市区町村民税所得割額により決定", fee_url) if fee_url else U(),
            "own": F(f"3歳児以上給食費 {v['lunch']}", S) if v.get("lunch") else U(),
        }
        rec["pickup"] = U()
        rec["vacancy"] = vac_field(vac, vac_url, as_of, name, set(ages) if ages else None) if vac_url else U()
        rec["application"] = {
            "method": F("新座市保育課へ申請。郵送・電子申請が原則（窓口は予約制）", SRC["apply"]),
            "deadline": hoiku_deadline,
        }
        rec["links"] = {
            "official": F(v["hp"], S) if v.get("hp") else U(),
            "intro": F(S, SRC["hoiku_top"]) if S else U(),
        }
        out.append(rec)
    out += collect_katei()
    return out


def collect_katei():
    """家庭保育室（市と委託契約を結ぶ認可外保育施設）。ページの「市内家庭保育室」表。"""
    s = main_body(soup(SRC["katei"]))
    out = []
    for t in s.find_all("table"):
        cap = t.find("caption")
        h = t.find_previous(["h2", "h3", "h4"])
        title = clean(cap.get_text()) if cap else (clean(h.get_text()) if h else "")
        if "市内家庭保育室" not in title:
            continue
        for tr in t.find_all("tr")[1:]:
            c = [clean(x.get_text(" ", strip=True)) for x in tr.find_all(["td", "th"])]
            if len(c) < 4 or not c[0]:
                continue
            name, addr, tel, target = c[:4]
            rec = base_record("kateihoikushitsu", "hoiku", "民間", name)
            S = SRC["katei"]
            a = re.sub(r"\s+", "", nfkc(addr)).replace("－", "-")
            rec["address"] = F(re.sub(r"^(埼玉県)?新座市", "", a), S)
            rec["phone"] = F(nfkc(tel).strip(), S) if tel else U()
            rec["station"] = U()
            rec["ages"] = F(target, S)
            m = re.match(r"(\d)から(\d)歳児まで", nfkc(target))
            rec["ageRange"] = F({"min": int(m.group(1)), "max": int(m.group(2))}, S) if m else U()
            rec["capacity"] = U()
            rec["hours"] = {"weekday": U(), "weekdayEnd": U(), "extension": U(), "extensionEnd": U(), "saturday": U()}
            rec["fees"] = {"table": U(), "basic": F("保育料は施設へ確認。市の保育料補助あり（要件あり）", S), "own": U()}
            rec["pickup"] = U()
            rec["vacancy"] = U("市の待機児童数一覧の対象外")
            rec["application"] = {"method": F("施設へ直接申し込む", S), "deadline": U()}
            rec["links"] = {"official": U(), "intro": U()}
            out.append(rec)
    return out


# ───────── 放課後児童保育室 ─────────

def collect_gakudo():
    s = main_body(soup(SRC["gakudo_list"]))
    S = SRC["gakudo_list"]
    A = SRC["gakudo_about"]
    about = clean(main_body(soup(A)).get_text(" "))
    if "午後7時まで" not in about or "午前8時から午後6時まで" not in about or "1年生から4年生" not in about:
        raise SystemExit("新座市：放課後児童保育室のご案内の文言が変わりました。確認してください")
    fee_ok = "月額0円から12,000円まで" in about
    pickup_text = clean(main_body(soup(SRC["gakudo_pickup"])).get_text(" "))
    gakudo_deadline = page_says(
        SRC["gakudo_apply"],
        "令和9年4月入室：令和8年10月1日〜11月19日（郵送は保育課必着、電子は23時59分まで）",
        ["令和9年4月1日から", "放課後児童保育室への入所・入室", "令和8年10月1日(木曜日)から11月19日(木曜日)までに保育課必着",
         "令和8年10月1日(木曜日)から11月19日(木曜日)23時59分まで"])
    out = []
    for h in s.find_all("h2"):
        room = clean(h.get_text())
        if "放課後児童保育室" not in room:
            continue
        # 見出しから次の h2 までの要素
        parts, sub = [], None
        for el in h.find_all_next():
            if el.name == "h2":
                break
            if el.name in ("p", "div", "td", "li") and el.find(["p", "div"]) is None:
                t = clean(el.get_text(" "))
                if not t:
                    continue
                m = re.match(r"^【(第\d)[（(]?(.*?)[）)]?】$", t)
                if m:
                    sub = (m.group(1), m.group(2))
                    continue
                if "住所" in t:
                    parts.append((sub, t))
        seen = set()
        for sub, t in parts:
            m = re.search(r"住所\s*(\S+)", t)
            if not m or (sub, m.group(1)) in seen:
                continue
            seen.add((sub, m.group(1)))
            tels = re.findall(r"0\d{1,3}-\d{2,4}-\d{3,4}", t)
            name = room + (f" {sub[0]}" if sub else "")
            listed = name + (f"（{sub[1]}）" if sub and sub[1] else "")
            rec = base_record("gakudo_ku", "gakudo", "公立", name, listed)
            rec["address"] = F(m.group(1), S)
            rec["phone"] = F(" ／ ".join(tels), S) if tels else U()
            rec["station"] = U()
            rec["capacity"] = U()
            rec["ages"] = F("新座市に住民登録がある、又は市内公立小学校に通学する小学1〜4年生", A)
            rec["ageRange"] = F({"min": 1, "max": 4}, A)
            rec["hours"] = {
                "weekday": F("放課後〜19:00", A),
                "weekdayEnd": F("19:00", A),
                "extension": U(),
                "extensionEnd": U(),
                "saturday": F("8:00〜18:00", A),
                "vacation": F("8:00〜19:00（学校休業日）", A),
            }
            rec["fees"] = {
                "basic": F("月額0円〜12,000円（世帯の市町村民税の所得割額等で決定）", A) if fee_ok else U(),
                "monthly": U(),
                "snack": U(),
                "extension": U(),
            }
            rec["pickup"] = F("保護者のお迎えが原則。車でのお迎えは不可", SRC["gakudo_pickup"]) if "保護者のお迎えを原則" in pickup_text else U()
            rec["vacancy"] = U("市の公式ページで空き人数の掲載を確認できませんでした")
            rec["application"] = {
                "method": F("新座市保育課へ電子申請または郵送（窓口受付なし）", SRC["gakudo_apply"]),
                "deadline": gakudo_deadline,
            }
            rec["links"] = {"official": U(), "intro": U()}
            out.append(rec)
    if len(out) < 17:
        raise SystemExit(f"新座市：放課後児童保育室が {len(out)} 件しか読めません")
    return out
