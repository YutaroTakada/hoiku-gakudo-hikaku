"""共通の取得・整形ヘルパー。"""
import datetime, hashlib, os, re, subprocess, tempfile, unicodedata, urllib.request

UA = "Mozilla/5.0 (compatible; hoiku-gakudo-hikaku/1.0; +https://github.com/YutaroTakada/hoiku-gakudo-hikaku)"
TODAY = os.environ.get("CHECK_DATE") or datetime.date.today().isoformat()
CACHE = os.environ.get("FETCH_CACHE")  # 開発時だけ使うキャッシュ置き場

_fetched = {}


def fetch_bytes(url: str) -> bytes:
    if url in _fetched:
        return _fetched[url]
    path = None
    if CACHE:
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest())
        if os.path.exists(path):
            _fetched[url] = open(path, "rb").read()
            return _fetched[url]
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
    if path:
        open(path, "wb").write(b)
    _fetched[url] = b
    return b


def fetch_text(url: str) -> str:
    b = fetch_bytes(url)
    for enc in ("utf-8", "cp932"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "ignore")


def pdf_text(url: str) -> str:
    b = fetch_bytes(url)
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(b)
        f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, check=True).stdout.decode("utf-8")


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").strip()


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", nfkc(s)).strip()


def F(value, source, note=None):
    """出どころと確認日つきの値。"""
    d = {"value": value, "source": source, "checked": TODAY}
    if note:
        d["note"] = note
    return d


def U(note=None):
    """未確認。推測で埋めない。"""
    d = {"value": None, "source": None, "checked": None}
    if note:
        d["note"] = note
    return d


def fid(ward, typ, name):
    return f"{ward}-{typ}-" + hashlib.md5(f"{ward}|{typ}|{nfkc(name)}".encode()).hexdigest()[:8]


def hm(s: str):
    """'7時15分' / '7：30' / '午後6時' などを 'H:MM' に。"""
    s = nfkc(s)
    m = re.search(r"(午前|午後)?\s*(\d{1,2})\s*(?:時|:)\s*(\d{1,2})?", s)
    if not m:
        return None
    h = int(m.group(2))
    mi = int(m.group(3) or 0)
    if m.group(1) == "午後" and h < 12:
        h += 12
    return f"{h}:{mi:02d}"


def span(s: str):
    """'7時15分から18時15分' -> ('7:15〜18:15', '18:15')"""
    s = nfkc(s)
    parts = re.split(r"から|〜|～|~|-|ー", s)
    parts = [p for p in parts if re.search(r"\d", p)]
    if len(parts) < 2:
        return None, None
    a, b = hm(parts[0]), hm(parts[1])
    if not a or not b:
        return None, None
    return f"{a}〜{b}", b


def class_range(text: str):
    """保育実施年齢の文言からクラス年齢の範囲を出す（文言にない値は出さない）。"""
    t = nfkc(text).replace(" ", "")
    nums = [int(x) for x in re.findall(r"(\d)歳", t)]
    lo = 0
    if re.match(r"^(産休明|生後|\d+(ヵ月|か月|ヶ月|ケ月|カ月))", t):
        lo = 0
    elif nums:
        lo = nums[0]
    if "以上" in t:
        return {"min": lo, "max": 5}
    if "から" in t and nums:
        return {"min": lo, "max": nums[-1]}
    return None


def grid_tables(url):
    """ページ内の表を、rowspan を展開したセルの2次元配列で返す。セルは (text, href)。"""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    s = BeautifulSoup(fetch_text(url), "html.parser")
    out = []
    for t in s.find_all("table"):
        h = t.find_previous(["h2", "h3", "h4"])
        cap = t.find("caption")
        rows, carry = [], {}
        for tr in t.find_all("tr"):
            row, col = [], 0
            cells = tr.find_all(["td", "th"])
            ci = 0
            while ci < len(cells) or col in carry:
                if col in carry:
                    val, left = carry[col]
                    row.append(val)
                    if left <= 1:
                        del carry[col]
                    else:
                        carry[col] = (val, left - 1)
                    col += 1
                    continue
                c = cells[ci]
                ci += 1
                a = c.find("a")
                href = urljoin(url, a.get("href")) if a and a.get("href") else None
                val = (clean(c.get_text(" ", strip=True)), href)
                rs = int(c.get("rowspan", 1) or 1)
                cs = int(c.get("colspan", 1) or 1)
                for _ in range(cs):
                    row.append(val)
                    if rs > 1:
                        carry[col] = (val, rs - 1)
                    col += 1
            rows.append(row)
        out.append((clean(h.get_text()) if h else "", clean(cap.get_text()) if cap else "", rows))
    return out
