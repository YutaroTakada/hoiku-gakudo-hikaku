"""台東区の公式ページから保育施設・こどもクラブ・放課後子供教室を集める。"""
import csv, io, re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from lib import F, U, fid, clean, nfkc, span, hm, class_range, fetch_text, TODAY

BASE = "https://www.city.taito.lg.jp"
H = BASE + "/kosodatekyouiku/kosodate/mokutei/hoiku_youjikyouiku/hoikutakuji"
G = BASE + "/kosodatekyouiku/kosodate/mokutei/gakkou_houkago"
SRC = {
    "hoiku_top": H + "/hoikuen/index.html",
    "public": H + "/hoikuen/kyokahoikuen/kurituhoikuen.html",
    "private": H + "/hoikuen/kyokahoikuen/kyokahoikuen.html",
    "ninsho": H + "/ninshohoikusho/ichiranpyo.html",
    "vacancy": H + "/hoikuen/hoikuennyuen/getureininnzuu.html",
    "hoikuryo": H + "/hoikuen/hoikuennyuen/hoikuryo.html",
    "apply": H + "/hoikuen/hoikuennyuen/hoikuenmousikomi.html",
    "ninsho_fee": H + "/ninshohoikusho/hoikuryoujyosei.html",
    "club_list": G + "/kodomoclub/ichiran.html",
    "club_about": G + "/kodomoclub/about.html",
    "club_apply": G + "/kodomoclub/riyoshinsei.html",
    "club_guide": G + "/kodomoclub/riyoshinsei.files/R9riyouannai.pdf",
    "houkago": G + "/houkago/kodomokyoushitu.html",
    "schools_csv": BASE + "/kusei/online/opendata/seikatu/shisethutizujouhou.files/sisetu_06.csv",
}


def soup(url):
    return BeautifulSoup(fetch_text(url), "html.parser")


def tables(url):
    s = soup(url)
    out = []
    for t in s.find_all("table"):
        h = t.find_previous(["h2", "h3", "h4"])
        cap = t.find("caption")
        rows = []
        for tr in t.find_all("tr"):
            cells = []
            for c in tr.find_all(["td", "th"]):
                a = c.find("a")
                href = urljoin(url, a.get("href")) if a and a.get("href") else None
                cells.append((clean(c.get_text(" ", strip=True)), href))
            rows.append(cells)
        out.append((clean(h.get_text()) if h else "", clean(cap.get_text()) if cap else "", rows))
    return out


def base_record(typ, category, management, name, listed=None):
    return {
        "id": fid("taito", typ, name),
        "ward": "taito",
        "category": category,
        "type": typ,
        "management": management,
        "name": name,
        "listedName": listed or name,
    }


def vacancy_map():
    """台東区「入園可能人数」表 -> {園名: {byAge, total}}"""
    s = soup(SRC["vacancy"])
    txt = s.get_text(" ")
    m = re.search(r"令和(\d+)年(\d+)月入園可能人数", txt)
    label = f"令和{m.group(1)}年{m.group(2)}月入園の入園可能人数" if m else "入園可能人数"
    upd = re.search(r"更新日：(\d{4})年(\d{1,2})月(\d{1,2})日", txt)
    as_of = f"{upd.group(1)}-{int(upd.group(2)):02d}-{int(upd.group(3)):02d}" if upd else None
    res = {}
    for _, _, rows in tables(SRC["vacancy"]):
        if not rows:
            continue
        head = [c[0] for c in rows[0]]
        for r in rows[1:]:
            if len(r) != len(head):
                continue
            name = nfkc(r[0][0])
            by = {}
            total = None
            for h, (v, _) in zip(head[1:], r[1:]):
                n = int(v) if v.isdigit() else None
                if h == "計" or "計" in h:
                    total = n
                else:
                    a = re.match(r"(\d)歳", h)
                    if a:
                        by[a.group(1)] = n
            res[name] = {"byAge": by or None, "total": total, "label": label, "asOf": as_of}
    return res


def _norm(s):
    s = nfkc(s).lstrip("★").replace(" ", "")
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def vac_field(vac, name):
    key = _norm(name)
    v = None
    for k in vac:
        if _norm(k) == key:
            v = vac[k]
    return F(v, SRC["vacancy"]) if v else U("区の入園可能人数表に記載なし")


def hoiku_common(rec, vac):
    rec["fees"] = {
        "table": F(SRC["hoikuryo"], SRC["hoikuryo"]),
        "basic": F("基本保育料は無償（延長保育料を除く）", SRC["vacancy"]),
        "own": U(),
    }
    rec["application"] = {
        "method": F("台東区（保育課）へ申請。電子申請・郵送・窓口", SRC["apply"]),
        "deadline": F("令和9年4月入園：窓口は令和8年11月27日まで、郵送・電子は令和8年11月13日まで（年度途中は毎月締切あり）", SRC["apply"]),
    }
    rec["pickup"] = U()
    rec["vacancy"] = vac_field(vac, rec["listedName"])


def collect_hoiku():
    vac = vacancy_map()
    out = []
    # 公立保育園（区の各園ページ）
    s = soup(SRC["public"])
    main = s.find(id="tmp_contents") or s
    for a in main.find_all("a"):
        href = a.get("href") or ""
        if "/kusei/shisetsu/hoikusho/kuritsu/" not in href:
            continue
        name = clean(a.get_text())
        url = urljoin(SRC["public"], href)
        p = soup(url)
        txt = "\n".join(x.strip() for x in (p.find(id="tmp_contents") or p).get_text("\n").split("\n") if x.strip())

        def after(label):
            m = re.search(label + r"\n(.+)", txt)
            return clean(m.group(1)) if m else None

        rec = base_record("ninka", "hoiku", "公立", name)
        addr = after("住所")
        rec["address"] = F(addr, url) if addr else U()
        ph = re.search(r"電話：?([\d-]+)", txt)
        rec["phone"] = F(ph.group(1), url) if ph else U()
        rec["station"] = U()
        age = after("保育実施年齢")
        rec["ages"] = F(age, url) if age else U()
        rec["ageRange"] = F(class_range(age), url) if age and class_range(age) else U()
        cap = re.search(r"定員\n(\d+)", txt)
        rec["capacity"] = F(int(cap.group(1)), url) if cap else U()
        m = re.search(r"一般保育\s*\n?(.+?)（", txt)
        sp, end = span(m.group(1)) if m else (None, None)
        ext = re.search(r"延長保育\s*\n?(午後\d+時(?:\d+分)?まで)", txt)
        rec["hours"] = {
            "weekday": F(sp + "（最長）", url) if sp else U(),
            "weekdayEnd": F(end, url) if end else U(),
            "extension": F(clean(ext.group(1)), url, "延長保育には定員があり、利用できない場合あり") if ext else U(),
            "extensionEnd": F(hm(ext.group(1)), url) if ext else U(),
            "saturday": U(),
        }
        rec["links"] = {"official": F(url, url), "intro": U()}
        hoiku_common(rec, vac)
        out.append(rec)
    # 石浜橋場こども園（区立こども園）
    name = "石浜橋場こども園"
    rec = base_record("kodomoen", "hoiku", "公立", name)
    rec.update({
        "address": F("橋場1丁目35番1号", SRC["hoiku_top"]),
        "phone": U(), "station": U(), "ages": U(), "ageRange": U(), "capacity": U(),
        "hours": {"weekday": U(), "weekdayEnd": U(), "extension": U(), "extensionEnd": U(), "saturday": U()},
        "links": {"official": F("https://taito.ed.jp/swas/index.php?id=1380019", SRC["public"]), "intro": U()},
    })
    hoiku_common(rec, vac)
    out.append(rec)

    # 私立・公設民営・地域型（区の一覧表）
    for head, cap, rows in tables(SRC["private"]):
        if "公設民営" in head:
            typ_default, mg = None, "公設民営"
        elif "私立" in head:
            typ_default, mg = None, "民間"
        elif "小規模" in head:
            typ_default, mg = "shokibo", "民間"
        elif "事業所内" in head:
            typ_default, mg = "jigyosho", "民間"
        elif "家庭的" in head:
            typ_default, mg = "katei", "民間"
        else:
            continue
        i = 0
        while i < len(rows):
            r = rows[i]
            if len(r) < 6 or r[0][0] in ("保育園名",) or not r[1][0]:
                i += 1
                continue
            short = rows[i + 1][0][0] if i + 1 < len(rows) and len(rows[i + 1]) == 1 else None
            listed = r[0][0]
            name = listed.lstrip("★")
            typ = typ_default or ("kodomoen" if "こども園" in name else "ninka")
            rec = base_record(typ, "hoiku", mg, name, listed)
            rec["address"] = F(r[1][0], SRC["private"])
            ph = r[2][0]
            rec["phone"] = F(ph if ph.startswith("0") else "03-" + ph, SRC["private"])
            rec["station"] = U()
            rec["ages"] = F(r[3][0], SRC["private"], "年齢は当該年度4月1日時点")
            cr = class_range(r[3][0])
            rec["ageRange"] = F(cr, SRC["private"]) if cr else U()
            capm = re.match(r"(\d+)", r[4][0])
            rec["capacity"] = F(int(capm.group(1)), SRC["private"], r[4][0] if "（" in r[4][0] else None) if capm else U()
            if typ == "katei":
                sp, end = span(r[5][0])
                rec["hours"] = {
                    "weekday": F(sp, SRC["private"], "保育提供時間") if sp else U(),
                    "weekdayEnd": F(end, SRC["private"]) if end else U(),
                    "extension": U(), "extensionEnd": U(), "saturday": U(),
                }
                intro = r[6][1] if len(r) > 6 else None
            else:
                sp, end = span(r[5][0])
                ext = r[6][0]
                extend = hm(ext) if re.search(r"\d", ext) else None
                rec["hours"] = {
                    "weekday": F(sp + "（保育標準時間）", SRC["private"], f"保育短時間：{short}" if short else None) if sp else U(),
                    "weekdayEnd": F(end, SRC["private"]) if end else U(),
                    "extension": F(ext if extend else "なし", SRC["private"], "延長保育は状況により利用できない場合あり"),
                    "extensionEnd": F(extend, SRC["private"]) if extend else U(),
                    "saturday": U(),
                }
                intro = r[7][1] if len(r) > 7 else None
            off = r[0][1]
            rec["links"] = {
                "official": F(off, SRC["private"]) if off else U(),
                "intro": F(intro, SRC["private"]) if intro else U(),
            }
            hoiku_common(rec, vac)
            out.append(rec)
            i += 2 if short else 1

    # 認証保育所
    for head, cap, rows in tables(SRC["ninsho"]):
        for r in rows[1:]:
            if len(r) < 8:
                continue
            listed = r[1][0]
            rec = base_record("ninsho", "hoiku", "民間", listed)
            rec["address"] = F(re.sub(r"^台東区", "", r[2][0]), SRC["ninsho"])
            rec["phone"] = F("03-" + r[3][0] if not r[3][0].startswith("0") else r[3][0], SRC["ninsho"])
            rec["station"] = U()
            rec["ages"] = F(r[5][0], SRC["ninsho"])
            cr = class_range(r[5][0])
            rec["ageRange"] = F(cr, SRC["ninsho"]) if cr else U()
            capm = re.match(r"(\d+)", r[4][0])
            rec["capacity"] = F(int(capm.group(1)), SRC["ninsho"]) if capm else U()
            sp, end = span(r[6][0])
            rec["hours"] = {
                "weekday": F(sp + "（開園時間）", SRC["ninsho"]) if sp else U(),
                "weekdayEnd": F(end, SRC["ninsho"]) if end else U(),
                "extension": U(), "extensionEnd": U(), "saturday": U(),
            }
            rec["fees"] = {
                "table": U("認証保育所の保育料は施設ごとに異なる"),
                "basic": F("施設ごとに設定（区の保育料助成制度あり）", SRC["ninsho_fee"]),
                "own": U(),
            }
            rec["application"] = {
                "method": F("施設と直接契約", SRC["ninsho"].replace("ichiranpyo", "ninshohoikusho")),
                "deadline": U(),
            }
            rec["pickup"] = U()
            rec["vacancy"] = U("区の公表なし。施設に問い合わせ")
            off = r[1][1]
            rec["links"] = {"official": F(off, SRC["ninsho"]) if off else U(), "intro": U()}
            page_txt = nfkc(BeautifulSoup(fetch_text(SRC["ninsho"]), "html.parser").get_text("\n"))
            for line in page_txt.split("\n"):
                if "閉園" in line and nfkc(listed).replace(" ", "") in line.replace(" ", ""):
                    rec["notice"] = F(clean(line).lstrip("※"), SRC["ninsho"])
            out.append(rec)
    return out


def club_common(rec):
    g = SRC["club_guide"]
    rec["ages"] = F("台東区内に住む小学生（1〜6年生）", SRC["club_about"])
    rec["ageRange"] = F({"min": 1, "max": 6}, SRC["club_about"])
    rec["hours"] = {
        "weekday": F("放課後〜18:00", g),
        "weekdayEnd": F("18:00", g),
        "extension": F("18:00〜19:00（延長育成。保護者のお迎えが前提）", g),
        "extensionEnd": F("19:00", g),
        "saturday": F("8:00〜18:00（延長19:00まで）", g),
        "vacation": F("8:00〜18:00（延長19:00まで）", g),
    }
    rec["fees"] = {
        "monthly": F(4000, g, "育成料。減免制度あり"),
        "snack": F(2000, g),
        "extension": F("月額1,000円（延長育成料）", g),
    }
    rec["pickup"] = F("1年生は17時まで、2年生以上は18時まで一人帰り可。それ以降は保護者のお迎えが必要。施設から自宅への送りの記載なし", g)
    rec["application"] = {
        "method": F("電子申請、または第1希望のこどもクラブへ書面申請", SRC["club_apply"]),
        "deadline": F("令和9年4月利用開始：令和8年12月15日まで（以降も受付、空きがあれば決定）。年度途中は利用希望月の前月10日締切", SRC["club_apply"]),
    }
    rec["vacancy"] = U("区の公表なし")


def collect_gakudo():
    out = []
    for head, cap, rows in tables(SRC["club_list"]):
        if cap not in ("公設民営", "民設民営"):
            continue
        mg = "公設民営" if cap == "公設民営" else "民間"
        typ = "gakudo_ku" if cap == "公設民営" else "gakudo_min"
        for r in rows[1:]:
            if len(r) < 5:
                continue
            listed = r[0][0]
            name = listed if ("クラブ" in listed or "キッズ" in listed) else listed + "こどもクラブ"
            if cap == "民設民営" and "こどもクラブ" not in name and "クラブ" not in name:
                name = listed + "こどもクラブ"
            if listed == "アスク浅草橋":
                name = "アスク浅草橋こどもクラブ"
            rec = base_record(typ, "gakudo", mg, name, listed)
            page = r[0][1]
            rec["address"] = F(r[3][0] + (f"（{r[2][0]}）" if r[2][0] and "---" not in r[2][0] else ""), SRC["club_list"])
            ph = r[4][0]
            rec["phone"] = F(ph if ph.startswith("0") else "03-" + ph, SRC["club_list"])
            st = U()
            if page:
                t = soup(page)
                tx = "\n".join(x.strip() for x in (t.find(id="tmp_contents") or t).get_text("\n").split("\n") if x.strip())
                m = re.search(r"交通\n((?:・.+\n?)+)", tx)
                if m:
                    lines = [l.lstrip("・") for l in m.group(1).strip().split("\n") if "駅" in l]
                    if lines:
                        st = F(" / ".join(lines), page)
            rec["station"] = st
            rec["capacity"] = F(int(r[1][0]), SRC["club_list"], "定員は変更になることがあります") if r[1][0].isdigit() else U()
            club_common(rec)
            off = r[5][1] if len(r) > 5 and r[5][1] else None
            rec["links"] = {"official": F(page, SRC["club_list"]) if page else U(), "intro": F(off, SRC["club_list"]) if off else U()}
            if listed == "浅草橋":
                rec["notice"] = F("令和9年3月まで柳北スポーツプラザ（浅草橋5丁目1番8号）に仮移転中", SRC["club_list"])
            out.append(rec)

    # 放課後子供教室
    schools = {}
    raw = fetch_text(SRC["schools_csv"])
    for row in csv.DictReader(io.StringIO(raw.lstrip("\ufeff"))):
        schools[nfkc(row["名称"])] = nfkc(row["所在地"])
    for head, cap, rows in tables(SRC["houkago"]):
        for r in rows[1:]:
            if len(r) != 3 or "放課後子供教室" not in r[0][0]:
                continue
            name = r[0][0]
            school = name.replace("放課後子供教室", "")
            rec = base_record("houkago", "gakudo", "公立", name)
            addr = schools.get(school)
            if addr and "仮校舎" not in addr:
                rec["address"] = F(f"{addr}（{school}内）", SRC["schools_csv"], "学校の所在地（台東区オープンデータ、令和4年4月時点）")
            else:
                rec["address"] = F(f"{school}内", SRC["houkago"])
            rec["phone"] = F(r[1][0], SRC["houkago"])
            rec["station"] = U()
            rec["ages"] = F("その学校の全児童", SRC["houkago"])
            rec["ageRange"] = F({"min": 1, "max": 6}, SRC["houkago"])
            rec["capacity"] = U("定員の記載なし")
            rec["hours"] = {
                "weekday": F("放課後〜16:45または18:00", SRC["houkago"], "学校との協議で変更あり"),
                "weekdayEnd": F("18:00", SRC["houkago"], "16:45までの日もあり"),
                "extension": F("なし", SRC["houkago"]),
                "extensionEnd": U(),
                "saturday": F("実施なし（土日祝・年末年始は除く）", SRC["houkago"]),
                "vacation": F("8:00〜16:45または18:00", SRC["houkago"]),
            }
            rec["fees"] = {
                "monthly": F(0, SRC["houkago"], "無料（保険代のみ自己負担、年間800円予定）"),
                "snack": U("おやつの記載なし"),
                "extension": F("なし", SRC["houkago"]),
            }
            rec["pickup"] = U()
            rec["application"] = {
                "method": F("随時受付。各放課後子供教室へ問い合わせ", SRC["houkago"]),
                "deadline": F("随時", SRC["houkago"]),
            }
            rec["vacancy"] = U("定員制ではない")
            rec["operator"] = F(r[2][0], SRC["houkago"])
            rec["links"] = {"official": F(SRC["houkago"], SRC["houkago"]), "intro": U()}
            out.append(rec)
    return out
