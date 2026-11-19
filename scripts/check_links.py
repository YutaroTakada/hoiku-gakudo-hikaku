"""リンク切れチェック。

python3 scripts/check_links.py external            # データ内の出どころ・公式リンク
python3 scripts/check_links.py internal <base_url>  # 公開サイト内のリンク（全ページを辿る）
"""
import glob, json, re, sys, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urldefrag

UA = "Mozilla/5.0 (compatible; hoiku-gakudo-hikaku-linkcheck/1.0)"


def status(url):
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 400, 501):
                continue
            return e.code
        except Exception as e:  # noqa: BLE001
            if method == "HEAD":
                continue
            return f"ERR {type(e).__name__}: {str(getattr(e, 'reason', e))[:80]}"
    return "ERR"


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


def internal(base):
    base = base.rstrip("/") + "/"
    seen, todo, bad, pages = set(), [base], [], 0
    while todo:
        u = todo.pop()
        if u in seen:
            continue
        seen.add(u)
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                ctype = r.headers.get("Content-Type", "")
                body = r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            bad.append((e.code, u))
            continue
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
