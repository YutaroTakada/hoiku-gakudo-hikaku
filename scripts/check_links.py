"""リンク切れチェック。

python3 scripts/check_links.py external            # データ内の出どころ・公式リンク
python3 scripts/check_links.py internal <base_url>  # 公開サイト内のリンク（全ページを辿る）
"""
import glob, json, re, shutil, subprocess, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urldefrag

# ブラウザ相当の User-Agent。ボット向けの UA だと 403 を返すサイトがあるため。
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "ja,en;q=0.8"}


def curl_status(url):
    """Python で接続できなかったとき（証明書の中間CA不足・古い暗号設定など）に curl で確かめ直す。
    ここでは中身を使わず、ページがあるかどうかだけを見る（そのため証明書の検証は省く）。
    ブラウザは足りない中間証明書を自分で取りに行くので、Python では失敗しても普通に開けるサイトがある。"""
    try:
        out = subprocess.run(
            ["curl", "-sS", "-L", "-k", "-o", "/dev/null", "--max-time", "40", "--ciphers", "DEFAULT@SECLEVEL=0",
             "-A", UA, "-H", f"Accept-Language: {HEADERS['Accept-Language']}", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        return f"ERR curl: {e}"[:100]
    code = out.stdout.strip()
    if code.isdigit() and code != "000":
        return int(code)
    return f"ERR curl: {out.stderr.strip()[:80]}"


def status(url):
    first = None
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 400, 501):
                continue
            return e.code
        except Exception as e:  # noqa: BLE001
            if method == "HEAD":
                continue
            first = f"ERR {type(e).__name__}: {str(getattr(e, 'reason', e))[:80]}"
    if first and "Name or service not known" not in first and shutil.which("curl"):
        st = curl_status(url)
        if isinstance(st, int):
            return st
    return first or "ERR"


def walk(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "source" and v:
                acc.add(v)
            elif isinstance(v, str) and v.startswith("http"):
                acc.add(v)
            else:
                walk(v, acc)
    elif isinstance(o, list):
        for v in o:
            walk(v, acc)


def external():
    urls = set()
    for p in glob.glob("data/facilities/*.json"):
        walk(json.load(open(p)), urls)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda u: (u, status(u)), sorted(urls)))
    other = [(u, s) for u, s in res if s != 200]
    dead = [(u, s) for u, s in other if s in (404, 410)]
    print(f"外部リンク {len(res)}件 / 200 {len(res) - len(other)}件 / リンク切れ(404・410) {len(dead)}件 / その他 {len(other) - len(dead)}件")
    for u, s in other:
        print(("リンク切れ" if (u, s) in dead else "要確認（ボット拒否・接続エラーなど）"), s, u)
    return dead


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in ("href", "src"):
            if a.get(k) and tag in ("a", "link", "script", "img"):
                self.links.append(a[k])


def fetch_page(u, tries=3):
    """公開サイトのページを取る。GitHub Pages が一時的に 5xx を返すことがあるので、少し待って取り直す。"""
    for n in range(tries):
        try:
            req = urllib.request.Request(u, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.headers.get("Content-Type", ""), r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code < 500 or n == tries - 1:
                return e.code
        time.sleep(5 * (n + 1))


def internal(base):
    base = base.rstrip("/") + "/"
    seen, todo, bad, pages = set(), [base], [], 0
    while todo:
        u = todo.pop()
        if u in seen:
            continue
        seen.add(u)
        got = fetch_page(u)
        if isinstance(got, int):
            bad.append((got, u))
            continue
        ctype, body = got
        pages += 1
        if "html" not in ctype:
            continue
        p = Links()
        p.feed(body)
        for h in p.links:
            full = urldefrag(urljoin(u, h))[0].split("?")[0]
            if full.startswith(base) and full not in seen:
                todo.append(full)
    print(f"内部URL {pages}件を取得 / エラー {len(bad)}件")
    for s, u in bad:
        print(s, u)
    return bad


if __name__ == "__main__":
    if sys.argv[1] == "external":
        sys.exit(1 if external() else 0)
    else:
        sys.exit(1 if internal(sys.argv[2]) else 0)
