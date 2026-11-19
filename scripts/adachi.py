"""足立区の公式ページ・PDF・CSVから保育施設・学童保育室・放課後子ども教室を集める。"""
import csv, io, re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from lib import F, U, fid, clean, nfkc, span, hm, fetch_text, fetch_bytes, pdf_text, grid_tables

A = "https://www.city.adachi.tokyo.jp"
SRC = {
    "ninka_list": A + "/kodomo-unei/k-kyoiku/kosodate/hoikuen-ichiran.html",
    "bosyu": A + "/kodomo-unei/bosyuuninnzuu.html",
    "shokibo": A + "/kodomo-nyuuen/k-kyoiku/kosodate/hoikujo-shokibo.html",
    "mama": A + "/kodomo-nyuuen/k-kyoiku/kosodate/hoikujo-mama-shigoto.html",
    "ninsho": A + "/kodomo-nyuuen/k-kyoiku/kosodate/hoikujo-hoikujo.html",
    "ninsho_aki": A + "/kodomo-nyuuen/k-kyoiku/kosodate/hoikujo-h2404-02aki.html",
    "hoikuryo": A + "/kodomo-unei/k-kyoiku/kosodate/hoikuen-hoikuryo.html",
    "apply4": A + "/kodomo-unei/4gatusinsei.html",
    "online": A + "/kodomo-unei/denshishinsei.html",
    "xlsx": A + "/documents/69389/00_ninka-hoikushisetu_1.xlsx",
    "gakudo_annai": A + "/k-gakudou/01gakudou_annnai.html",
    "gakudo_aki": A + "/k-gakudou/05_gakudo_akiyoho.html",
    "gakudo_r9": A + "/k-gakudou/r9nyuusitusinnsei.html",
    "gakudo_encho": A + "/k-gakudou/k-kyoiku/kosodate/g-encho.html",
    "houkago_guide": A + "/juku/gakudou_houkago.html",
    "houkago_page": A + "/seshonen/k-kyoiku/kyoiku/k-kyoshitsu.html",
    "houkago_list": "https://www.kousya.jp/kids-classroom/kids-ichiran/",
    "schools_csv": A + "/documents/4032/2025_syo.csv",
    "kodomoen_csv": A + "/documents/2954/kuritsukodomoen2023csv.csv",
}
NAME_KW = ("保育", "園", "ナーサリー", "ルーム", "キッズ", "こども", "NURSERY", "ハウス", "スクール", "Nursery")


def find_link(page, pattern):
    s = BeautifulSoup(fetch_text(page), "html.parser")
    for a in s.find_all("a"):
        h = a.get("href") or ""
        if re.search(pattern, h):
            return urljoin(page, h)
    raise RuntimeError(f"{page} に {pattern} のリンクが見つかりません")


def kana(s):
    s = nfkc(s).replace(" ", "").replace("　", "")
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def rec0(typ, category, management, name, listed):
    return {"id": fid("adachi", typ, listed), "ward": "adachi", "category": category, "type": typ,
            "management": management, "name": name, "listedName": listed}


def full_names():
    """区オープンデータ（保育施設一覧データ）の正式名称と住所。"""
    import openpyxl, tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as f:
        f.write(fetch_bytes(SRC["xlsx"]))
        f.flush()
        wb = openpyxl.load_workbook(f.name)
    out = []
    for ws in wb:
        for r in list(ws.iter_rows(values_only=True))[1:]:
            if r[3]:
                out.append({"kubun": r[1], "name": nfkc(r[3]), "address": nfkc(r[6] or "")})
    return out


def match_full(short, fulls):
    k = kana(short)
    for f in fulls:
        fk = kana(f["name"])
        if fk == k or fk in (k + "保育園", k + "保育所", k + "こども園"):
            return f
    return None


# ---------- 募集人数PDF ----------
def bosyu():
    url = find_link(SRC["bosyu"], r"ninka_shokibo\.pdf$")
    txt = pdf_text(url)
    asof = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})現在", txt)
    month = re.search(r"令和(\d+)年(\d+)月入所募集分", txt)
    label = f"令和{month.group(1)}年{month.group(2)}月入所の募集人数" if month else "募集人数"
    as_of = f"{asof.group(1)}-{int(asof.group(2)):02d}-{int(asof.group(3)):02d}" if asof else None
    lines = txt.split("\n")
    res = {}
    pend = None
    for ln in lines:
        ln = nfkc(ln)
        if pend:
            ln = pend + " " + ln
            pend = None
        if re.search(r"(私立|区立こ|区立|公民|小規模)\s*$", ln):
            pend = ln
            continue
        m = re.search(r"(私立|区立こ|区立|公民|小規模)\s+(.+?)\s*\((\d+)\)\s*(.*)$", ln)
        if not m:
            continue
        kubun, name, cap, rest = m.group(1), m.group(2).strip(), int(m.group(3)), m.group(4)
        toks = rest.split()
        ages = toks[:6]
        by = {}
        for i, t in enumerate(ages):
            by[str(i)] = int(t) if t.isdigit() else None
        zero = toks[6] if len(toks) > 6 else None
        ext = toks[7] if len(toks) > 7 else None
        nums = [v for v in by.values() if v is not None]
        has = [i for i, t in enumerate(ages) if t.isdigit()]
        res[kana(name)] = {
            "kubun": kubun, "name": name, "cap": cap,
            "vac": {"byAge": by, "total": sum(nums), "label": label, "asOf": as_of},
            "range": {"min": min(has), "max": max(has)} if has else None,
            "zero": zero, "ext": ext, "url": url,
        }
    return res


def kodomoen_pdf():
    url = find_link(SRC["bosyu"], r"kodomoen\.pdf$")
    txt = pdf_text(url)
    res = []
    hours = {}
    for ln in txt.split("\n"):
        ln2 = nfkc(ln)
        m = re.match(r"\s*(\S+幼稚園)\s+((?:[-－–―]|\d+)(?:\s+(?:[-－–―]|\d+)){5})\s+(午前.+?)(?:\s{2,}(×))?\s*$", ln2)
        if m:
            vals = m.group(2).split()
            by = {str(i): (int(v) if v.isdigit() else None) for i, v in enumerate(vals)}
            has = [i for i, v in enumerate(vals) if v.isdigit()]
            res.append({"name": m.group(1), "byAge": by, "open": clean(m.group(3)), "satClosed": bool(m.group(4)),
                        "range": {"min": min(has), "max": max(has)} if has else None})
            continue
        m = re.match(r"\s*(\S+幼稚園)\s+(午前.+?時(?:\s*\d+\s*分)?から午後.+?時(?:\s*\d+\s*分)?)\s{2,}(午前.+)$", ln2)
        if m:
            hours[m.group(1)] = (clean(m.group(2)), clean(m.group(3)))
    return res, hours, url


# ---------- 保育 ----------
def hoiku_fees(rec, mg):
    rec["fees"] = {
        "table": F(SRC["hoikuryo"], SRC["hoikuryo"]),
        "basic": F("基本保育料は無料（延長保育料などは別）", SRC["hoikuryo"]),
        "own": U(),
    }
    if mg == "公立":
        rec["fees"]["extensionFee"] = F("区立園の延長保育料（18:30〜19:30）：月額1,000円（A・B階層）／4,000円（C・D階層）", SRC["hoikuryo"])


def hoiku_apply(rec):
    rec["application"] = {
        "method": F("足立区（保育・入園課）へ申込。オンライン申請または区役所窓口", SRC["apply4"]),
        "deadline": F("令和9年4月一次募集：令和8年10月26日〜11月26日。二次募集：令和9年2月1日〜2月14日（窓口は2月12日まで）。年度途中は入所希望月ごとに締切あり", SRC["online"]),
    }


def collect_hoiku():
    fulls = full_names()
    bos = bosyu()
    used = set()
    out = []

    def find_bos(short):
        k = kana(short)
        if k in bos:
            return k
        k2 = re.sub(r"(保育園|保育所)$", "", k)
        if k2 in bos:
            return k2
        cands = [b for b in bos if b.startswith(k2) or k2.startswith(re.sub(r"\(.*\)$", "", b))]
        cands = [b for b in cands if b not in used]
        return cands[0] if len(cands) == 1 else None

    def vacancy_for(short):
        k = find_bos(short)
        if k:
            used.add(k)
            b = bos[k]
            return F(b["vac"], b["url"], None if kana(b["name"]) == kana(short) else f"区の募集人数表での表記：{b['name']}"), b
        return U("区の募集人数表に記載なし"), None

    # 認可保育所一覧
    for head, cap, rows in grid_tables(SRC["ninka_list"]):
        if not rows or rows[0][0][0] != "区分":
            continue
        for r in rows[1:]:
            if len(r) < 6:
                continue
            kubun = r[0][0]
            raw = nfkc(r[1][0])
            m = re.match(r"(.+?)\s*\((\d+)\)", raw)
            if not m:
                continue
            short = m.group(1).strip()
            mg = {"区立": "公立", "公設民営": "公設民営"}.get(kubun, "民間")
            f = match_full(short, fulls)
            name = f["name"] if f else (short if any(k in short for k in NAME_KW) else short + "保育園")
            typ = "kodomoen" if "こども園" in name else "ninka"
            rec = rec0(typ, "hoiku", mg, name, short)
            L = SRC["ninka_list"]
            rec["address"] = F(r[2][0], L)
            rec["phone"] = F(r[3][0], L)
            rec["station"] = U()
            vac, b = vacancy_for(short)
            z = r[4][0]
            if z == "産":
                ages = "生後57日（産休明け）から"
            elif z == "満6":
                ages = "満6か月から"
            else:
                ages = "1歳児クラスから（0歳児保育の記載なし）"
            rec["ages"] = F(ages, L)
            rec["ageRange"] = F(b["range"], b["url"]) if b and b["range"] else U()
            rec["capacity"] = F(int(m.group(2)), L)
            ext = r[5][0] == "延"
            hours = {"weekday": U(), "weekdayEnd": U(),
                     "extension": F("あり" if ext else "なし（区の一覧に延長の印なし）", L, "0歳児は延長保育をしていない園あり" if ext else None),
                     "extensionEnd": U(), "saturday": U()}
            if mg == "公立" and ext:
                hours["extension"] = F("18:30〜19:30", SRC["hoikuryo"], "区立園の延長保育。満1歳以上が対象")
                hours["extensionEnd"] = F("19:30", SRC["hoikuryo"])
            rec["hours"] = hours
            hoiku_fees(rec, mg)
            if len(r) > 6 and r[6][0] == "〇":
                rec["fees"]["own"] = F("紙おむつのサブスクあり（料金は施設に確認）", L, "令和8年10月9日時点の実施状況")
            hoiku_apply(rec)
            rec["pickup"] = U()
            rec["vacancy"] = vac
            rec["links"] = {"official": U(), "intro": F(r[1][1], L) if r[1][1] else U()}
            out.append(rec)

    kcsv = {}
    for row in csv.DictReader(io.StringIO(fetch_text(SRC["kodomoen_csv"]).lstrip("\ufeff"))):
        n = nfkc(row["保育施設名称"])
        part = (nfkc(row.get("備考") or "") + "：") if row.get("備考") else ""
        kcsv.setdefault(n, []).append((part + nfkc(row["住所２"]), "03-" + nfkc(row["電話番号"])))

    # 募集人数表にだけある区立認定こども園など
    for k, b in bos.items():
        if k in used or b["kubun"] == "小規模":
            continue
        mg = {"区立": "公立", "区立こ": "公立", "公民": "公設民営"}.get(b["kubun"], "民間")
        f = match_full(b["name"], fulls)
        name = f["name"] if f else b["name"]
        typ = "kodomoen" if "こども園" in name else "ninka"
        rec = rec0(typ, "hoiku", mg, name, b["name"])
        rec["address"] = F(f["address"], SRC["xlsx"], "区オープンデータ（令和6年3月時点）") if f and f["address"] else U()
        rec["phone"] = U()
        if b["name"] in kcsv:
            rec["address"] = F(" ／ ".join(a for a, _ in kcsv[b["name"]]), SRC["kodomoen_csv"], "区オープンデータ（区立認定こども園、2023年）")
            rec["phone"] = F(" ／ ".join(p for _, p in kcsv[b["name"]]), SRC["kodomoen_csv"])
        rec["station"] = U()
        rec["ages"] = F("生後57日から" if b["zero"] == "生後57日" else ("満6か月から" if b["zero"] and "6" in b["zero"] else "1歳児クラスから"), b["url"])
        rec["ageRange"] = F(b["range"], b["url"]) if b["range"] else U()
        rec["capacity"] = F(b["cap"], b["url"])
        rec["hours"] = {"weekday": U(), "weekdayEnd": U(),
                        "extension": F("あり" if b["ext"] == "あり" else "なし", b["url"]),
                        "extensionEnd": U(), "saturday": U()}
        hoiku_fees(rec, mg)
        hoiku_apply(rec)
        rec["pickup"] = U()
        rec["vacancy"] = F(b["vac"], b["url"])
        rec["links"] = {"official": U(), "intro": U()}
        used.add(k)
        out.append(rec)

    # 私立認定こども園（長時間利用）
    kos, khours, kurl = kodomoen_pdf()
    for k in kos:
        f = match_full(k["name"], fulls)
        rec = rec0("kodomoen", "hoiku", "民間", k["name"], k["name"])
        rec["address"] = F(f["address"], SRC["xlsx"], "区オープンデータ（令和6年3月時点）") if f and f["address"] else U()
        rec["phone"] = U()
        rec["station"] = U()
        rg = k["range"]
        rec["ages"] = F(f"{rg['min']}歳児クラスから（長時間利用）" if rg else "長時間利用", kurl)
        rec["ageRange"] = F(rg, kurl) if rg else U()
        rec["capacity"] = U()
        std = khours.get(k["name"])
        sp, end = span(std[0]) if std else (None, None)
        rec["hours"] = {
            "weekday": F(sp + "（保育標準時間）", kurl, f"保育短時間：{std[1]}") if sp else U(),
            "weekdayEnd": F(end, kurl) if end else U(),
            "extension": F(f"開所時間 {k['open']}", kurl),
            "extensionEnd": F(span(k["open"])[1], kurl) if span(k["open"])[1] else U(),
            "saturday": F("開所しない", kurl) if k["satClosed"] else U(),
        }
        hoiku_fees(rec, "民間")
        rec["fees"]["own"] = F("入園料（10万円前後）や制服・教材費などがかかることあり", kurl)
        hoiku_apply(rec)
        rec["application"]["method"] = F("足立区へ申込。事前に園で説明を受け「施設確認証明書」を添付", kurl)
        rec["pickup"] = U()
        rec["vacancy"] = F({"byAge": k["byAge"], "total": sum(v for v in k["byAge"].values() if v), "label": bos and next(iter(bos.values()))["vac"]["label"], "asOf": next(iter(bos.values()))["vac"]["asOf"]}, kurl)
        rec["links"] = {"official": U(), "intro": U()}
        out.append(rec)

    # 小規模保育
    for head, cap, rows in grid_tables(SRC["shokibo"]):
        if not rows or "施設名" not in [c[0] for c in rows[0]]:
            continue
        hd = [c[0] for c in rows[0]]
        ix = {k: hd.index(k) for k in ("施設名", "施設住所", "電話番号", "定員", "種類", "預り開始月齢", "保育施設紹介")}
        for r0 in rows[1:]:
            if len(r0) < len(hd) or not r0[0][0].isdigit():
                continue
            r = [r0[0], r0[ix["施設名"]], r0[ix["施設住所"]], r0[ix["電話番号"]], r0[ix["定員"]], r0[ix["種類"]], r0[ix["預り開始月齢"]], r0[ix["保育施設紹介"]]]
            name = re.sub(r"[（(]外部サイトへリンク[)）]", "", r[1][0]).strip()
            L = SRC["shokibo"]
            rec = rec0("shokibo", "hoiku", "民間", name, name)
            rec["address"] = F(r[2][0], L)
            rec["phone"] = F(r[3][0], L)
            rec["station"] = U()
            rec["ages"] = F(f"{r[6][0]}から2歳児クラスまで", L)
            rec["ageRange"] = F({"min": 0, "max": 2}, L)
            rec["capacity"] = F(int(r[4][0]), L, f"{r[5][0]}型") if r[4][0].isdigit() else U()
            rec["hours"] = {"weekday": U("区の案内は「7:30〜18:30（一部施設を除く）」。施設ごとの時間は未確認"),
                            "weekdayEnd": U(), "extension": U(), "extensionEnd": U(),
                            "saturday": U("土曜保育は各施設に相談（区の案内）")}
            hoiku_fees(rec, "民間")
            hoiku_apply(rec)
            rec["pickup"] = U()
            vac, _ = vacancy_for(name)
            if vac["value"] is None:
                for kk, b in bos.items():
                    if b["kubun"] == "小規模" and (kk in kana(name) or kana(name) in kk):
                        vac = F(b["vac"], b["url"])
                        used.add(kk)
                        break
            rec["vacancy"] = vac
            rec["links"] = {"official": F(r[1][1], L) if r[1][1] else U(), "intro": F(r[7][1], L) if len(r) > 7 and r[7][1] else U()}
            out.append(rec)

    # 認証保育所
    aki = {}
    for head, cap, rows in grid_tables(SRC["ninsho_aki"]):
        if rows and rows[0] and rows[0][0][0] == "地区":
            hd = [c[0].replace(" ", "") for c in rows[0]]
            atxt = nfkc(BeautifulSoup(fetch_text(SRC["ninsho_aki"]), "html.parser").get_text(" "))
            mm = re.search(r"令和(\d+)年(\d+)月(\d+)日\s*(\d+)時に更新", atxt)
            as_of = f"{2018 + int(mm.group(1))}-{int(mm.group(2)):02d}-{int(mm.group(3)):02d}" if mm else None
            for r in rows[1:]:
                if len(r) < 11:
                    continue
                by = {}
                for i in range(6):
                    v = r[5 + i][0]
                    by[str(i)] = int(v) if v.isdigit() else None
                nums = [v for v in by.values() if v is not None]
                aki[kana(r[2][0])] = {"byAge": by if nums else None, "total": sum(nums) if nums else None,
                                      "totalText": None if nums else "区の表では空き数の記載なし",
                                      "label": "認証保育所の空き状況", "asOf": as_of}
    for head, cap, rows in grid_tables(SRC["ninsho"]):
        if not rows or rows[0][0][0] != "地区":
            continue
        for r in rows[1:]:
            if len(r) < 5:
                continue
            L = SRC["ninsho"]
            raw = re.sub(r"[（(]外部サイトへリンク[)）]", "", r[2][0]).strip()
            m = re.match(r"(.+?)\s*[（(]([^）)]*歳[^）)]*)[)）]\s*$", raw)
            name, agenote = (m.group(1).strip(), m.group(2)) if m else (raw, None)
            typ_ab = r[1][0]
            rec = rec0("ninsho", "hoiku", "民間", name, raw)
            rec["address"] = F(r[3][0], L)
            rec["phone"] = F("03-" + re.sub(r"[()（）\s]", "", r[4][0]).replace(")", "-") if r[4][0].startswith("(") else r[4][0], L)
            if r[4][0].startswith("("):
                p = re.sub(r"\s", "", r[4][0])
                mm = re.match(r"\((\d+)\)(\d+)", p)
                rec["phone"] = F(f"03-{mm.group(1)}-{mm.group(2)}" if mm else p, L)
            rec["station"] = U()
            if agenote:
                rec["ages"] = F(agenote, L)
                nums = [int(x) for x in re.findall(r"(\d)歳", agenote)]
                rec["ageRange"] = F({"min": nums[0], "max": nums[-1]}, L) if len(nums) >= 2 else U()
            elif typ_ab == "A":
                rec["ages"] = F("0歳児から就学前まで（A型）", L)
                rec["ageRange"] = F({"min": 0, "max": 5}, L)
            else:
                rec["ages"] = F("0歳児から2歳児まで（B型）", L)
                rec["ageRange"] = F({"min": 0, "max": 2}, L)
            rec["capacity"] = U()
            rec["hours"] = {"weekday": U("13時間開所が基本（区の案内）。施設ごとの時間は未確認"), "weekdayEnd": U(), "extension": U(), "extensionEnd": U(), "saturday": U()}
            rec["fees"] = {"table": U("認証保育所の保育料は施設ごとに異なる"), "basic": F("施設ごとに設定。直接問い合わせ", L), "own": U()}
            rec["application"] = {"method": F("施設に直接連絡して契約", L), "deadline": U()}
            rec["pickup"] = U()
            a = aki.get(kana(name)) or aki.get(kana(raw))
            rec["vacancy"] = F(a, SRC["ninsho_aki"]) if a else U("区の空き状況表に記載なし")
            rec["links"] = {"official": F(r[2][1], L) if r[2][1] and "google" not in r[2][1] else U(),
                            "intro": F(r[6][1], L) if len(r) > 6 and r[6][1] else U()}
            out.append(rec)

    # 家庭的保育（保育ママ）
    url = find_link(SRC["bosyu"], r"mama\.pdf$")
    txt = pdf_text(url)
    asof = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", txt)
    month = re.search(r"令和(\d+)年(\d+)月入所募集分", nfkc(txt))
    for ln in txt.split("\n"):
        ln = nfkc(ln)
        m = re.search(r"(\S+)\s+(\S+)\s*\((\d)\)\s+(\S+)\s+(\d+)\s+(\d+|-|－)\s+(\d+|-|－)\s+(\d+|-|－)\s+(\d{1,2}:\d{2}[～~]\d{1,2}:\d{2})\s*([◆◇])?", ln)
        if not m:
            continue
        person = f"{m.group(1)} {m.group(2)}"
        town = re.sub(r"[\d\-－].*$", "", m.group(4))
        name = f"保育ママ {person}"
        rec = rec0("katei", "hoiku", "民間", name, person)
        rec["address"] = F(town, url, "個人宅のため町名まで表示。詳しくは区の一覧へ")
        rec["phone"] = F("区の「保育施設利用申込案内」の保育ママ一覧に掲載", SRC["mama"])
        rec["station"] = U()
        rec["ages"] = F("生後57日から2歳児クラスまで", SRC["mama"])
        rec["ageRange"] = F({"min": 0, "max": 2}, SRC["mama"])
        rec["capacity"] = F(int(m.group(3)), url)
        sp, end = span(m.group(9))
        rec["hours"] = {"weekday": F(sp, url, "開所時間"), "weekdayEnd": F(end, url),
                        "extension": F("なし（月ぎめ延長保育は行っていない）", SRC["hoikuryo"]), "extensionEnd": U(),
                        "saturday": U("土曜日保育は各保育ママに問い合わせ（区の案内）")}
        hoiku_fees(rec, "民間")
        rec["fees"]["own"] = F("給食：" + ("自園調理" if m.group(10) == "◆" else "外部搬入" if m.group(10) == "◇" else "記載なし"), url)
        hoiku_apply(rec)
        rec["pickup"] = U()
        by = {}
        for i, g in enumerate((m.group(6), m.group(7), m.group(8))):
            by[str(i)] = int(g) if g.isdigit() else None
        rec["vacancy"] = F({"byAge": by, "total": int(m.group(5)), "label": f"令和{month.group(1)}年{month.group(2)}月入所の募集人数" if month else "募集人数",
                            "asOf": f"{asof.group(1)}-{int(asof.group(2)):02d}-{int(asof.group(3)):02d}" if asof else None}, url)
        rec["links"] = {"official": F(SRC["mama"], SRC["mama"]), "intro": U()}
        out.append(rec)
    return out


# ---------- 学童 ----------
def gakudo_vacancy():
    res = {}
    txt = nfkc(BeautifulSoup(fetch_text(SRC["gakudo_aki"]), "html.parser").get_text(" "))
    m = re.search(r"令和(\d+)年\s*(\d+)月\s*(\d+)日\s*時点", txt)
    as_of = f"{2018 + int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    for head, cap, rows in grid_tables(SRC["gakudo_aki"]):
        for r in rows[1:]:
            if len(r) < 4:
                continue
            v = r[3][0]
            n = int(re.match(r"\d+", v).group()) if re.match(r"\d+", v) else None
            key = kana(re.sub(r"学童保育室$", "", r[0][0]))
            res[key] = {"byAge": None, "total": n, "totalText": v + "人" if n is not None else v, "label": "空き人数", "asOf": as_of}
    return res


def collect_gakudo():
    out = []
    csv_url = find_link(SRC["gakudo_annai"], r"\.csv$")
    raw = fetch_text(csv_url)
    vac = gakudo_vacancy()
    section = 0
    for row in csv.reader(io.StringIO(raw)):
        joined = ",".join(row)
        if "１ 区立" in joined or "1 区立" in nfkc(joined):
            section = 1
            continue
        if "民設民営学童保育室一覧" in joined:
            section = 2
            continue
        if not section or not any(row) or row[0].startswith("地域") or row[0].startswith("＊") or row[0].startswith("※"):
            continue
        row = [nfkc(c) for c in row] + [""] * 12
        if section == 1:
            short, capt, ext, addr, place, tel = row[3], row[4], row[5], row[6], row[8], row[9]
            if not short:
                continue
            short = re.sub(r"\s*\*\s*\d+$", "", short).strip()
            name = short + "学童保育室"
            mg, typ = "公立", "gakudo_ku"
        else:
            short, capt, ext, addr, tel = row[3].strip(), row[5], row[6], row[7], row[9]
            place = ""
            if not short:
                continue
            name = short if any(k in short for k in ("学童", "クラブ", "キッズ", "Mo-ne", "わくわく", "ひまわり")) else short + "学童保育室"
            mg, typ = "民間", "gakudo_min"
        L = csv_url
        rec = rec0(typ, "gakudo", mg, name, short)
        rec["address"] = F(addr.strip() + (f"（{place}）" if place else ""), L)
        tel = tel.strip()
        rec["phone"] = F(tel if tel.startswith("0") else "03-" + tel, L)
        rec["station"] = U()
        rec["ages"] = F("区内在住・在学の小学1〜6年生（週3日以上利用）", SRC["gakudo_annai"])
        rec["ageRange"] = F({"min": 1, "max": 6}, SRC["gakudo_annai"])
        cm = re.match(r"(?:(\d)室)?(\d+)", capt)
        rec["capacity"] = F(int(cm.group(2)), L, f"{cm.group(1)}室" if cm and cm.group(1) else None) if cm else U()
        has_ext = ext == "有"
        if section == 1:
            ga = SRC["gakudo_annai"]
            rec["hours"] = {
                "weekday": F("授業終了後〜18:00", ga), "weekdayEnd": F("18:00", ga),
                "extension": F("特別延長保育 18:00〜19:00、学校休業日の早朝 8:00〜8:30", SRC["gakudo_encho"]) if has_ext else F("なし（特別延長保育の実施室ではない）", L),
                "extensionEnd": F("19:00", SRC["gakudo_encho"]) if has_ext else U(),
                "saturday": F("8:30〜18:00", ga, "学校休業日の時間。開室は月〜土"),
                "vacation": F("8:30〜18:00", ga),
            }
            rec["fees"] = {
                "monthly": F(6000, ga, "保護者負担金。きょうだい入室は一番下以外半額。減免あり"),
                "snack": U(),
                "extension": F("月額3,000円（特別延長保育）", ga) if has_ext else F("なし", L),
            }
            rec["pickup"] = F("特別延長保育を使う場合は保護者または祖父母等のお迎えが必要。施設から自宅への送りの記載なし", ga) if has_ext else U()
        else:
            rec["hours"] = {"weekday": U(), "weekdayEnd": U(),
                            "extension": F("特別延長あり（内容は各室に確認）", L) if has_ext else U(),
                            "extensionEnd": U(), "saturday": U(), "vacation": U()}
            rec["fees"] = {"monthly": U("民設学童保育室のサービス内容は各室に問い合わせ（区の案内）"), "snack": U(), "extension": U()}
            rec["pickup"] = U()
        rec["application"] = {
            "method": F("所定の申請書類を第1希望の学童保育室に提出", SRC["gakudo_annai"]),
            "deadline": F("令和9年4月入室：一斉受付 令和8年11月4日〜11月25日、追加受付 令和9年2月16日〜2月24日（民設も同じ期間）", SRC["gakudo_r9"]),
        }
        v = vac.get(kana(short)) or vac.get(kana(name)) or vac.get(kana(re.sub(r"学童保育室$", "", name)))
        rec["vacancy"] = F(v, SRC["gakudo_aki"]) if v else U("区の空き情報に記載なし")
        rec["links"] = {"official": F(SRC["gakudo_annai"], SRC["gakudo_annai"]) if section == 1 else U(), "intro": U()}
        out.append(rec)

    # 放課後子ども教室
    pdf = find_link(SRC["houkago_list"], r"\.pdf$")
    txt = pdf_text(pdf)
    sch = {}
    for row in csv.DictReader(io.StringIO(fetch_text(SRC["schools_csv"]).lstrip("\ufeff"))):
        sch[nfkc(row["学校名"])] = nfkc(row["住所"])
    guide = SRC["houkago_guide"]
    for ln in txt.split("\n"):
        ln = nfkc(ln)
        m = re.match(r"\s*(\d+)\s+(\S+)\s+(?:(\d)[～~](\d)\s+(有|無)\s+(.*?))?(?:\s{2,}(\S.*))?$", ln)
        if not m or not m.group(2) or not (m.group(3) or "委託" in ln):
            continue
        school = m.group(2) + "小学校"
        name = f"{m.group(2)}小 放課後子ども教室"
        rec = rec0("houkago", "gakudo", "公立", name, m.group(2))
        a = sch.get(school)
        rec["address"] = F(f"{a}（{school}内）", SRC["schools_csv"], "学校の所在地（区オープンデータ）") if a else F(f"{school}内", pdf)
        rec["station"] = U()
        rec["capacity"] = U("定員制ではない（登録制）")
        model = "委託" in ln
        if model:
            op = re.search(r"】\s*(.+?)\s*℡\s*:?\s*([\d-]+)", ln)
            rec["phone"] = F(op.group(2), pdf) if op else U()
            rec["operator"] = F(op.group(1), pdf) if op else U()
            rec["ages"] = U("学校により異なる")
            rec["ageRange"] = U()
            rec["hours"] = {
                "weekday": F("9:00〜17:00（学童保育室と一体運用のモデル校）", guide), "weekdayEnd": F("17:00", guide),
                "extension": F("なし", guide), "extensionEnd": U(),
                "saturday": F("9:00〜17:00", guide), "vacation": F("9:00〜17:00（昼食は学校でとれない）", guide),
            }
        else:
            rec["phone"] = F("03-5813-3732（足立区生涯学習振興公社）", pdf)
            g1, g2 = int(m.group(3)), int(m.group(4))
            plan = (m.group(7) or "").strip()
            rec["ages"] = F(f"{g1}〜{g2}年生（曜日：{m.group(6).strip()}）" + (f"／今後：{plan}" if plan else ""), pdf)
            rec["ageRange"] = F({"min": g1, "max": g2}, pdf)
            rec["hours"] = {
                "weekday": F("授業終了後〜おおむね17:00（給食のある日の月〜金）", guide), "weekdayEnd": F("17:00", guide),
                "extension": F("なし", guide), "extensionEnd": U(),
                "saturday": F("実施なし", guide), "vacation": F("実施なし（学校休業日は休み）", guide),
            }
        rec["fees"] = {"monthly": F(0, guide, "無料"), "snack": U(), "extension": F("なし", guide)}
        rec["pickup"] = U()
        rec["application"] = {"method": F("登録制（各小学校の児童が対象）", guide), "deadline": U()}
        rec["vacancy"] = U("定員制ではない")
        rec["links"] = {"official": F(SRC["houkago_page"], SRC["houkago_page"]), "intro": F(pdf, pdf)}
        out.append(rec)
    return out
