"""足立区・台東区の公式情報から施設データを集め、data/facilities/*.json に書き出す。

使い方: python3 scripts/collect.py
- 推測で値を埋めない。公式ページで確認できない項目は value=null（サイトでは「未確認」）。
- 前回より件数が大きく減ったら、取得の失敗とみなして書き出さずに止まる。
"""
import json, os, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import adachi, taito  # noqa: E402
from lib import TODAY, U  # noqa: E402
from check_links import status  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "facilities")
TYPE_ORDER = ["ninka", "kodomoen", "shokibo", "jigyosho", "katei", "ninsho", "gakudo_ku", "gakudo_min", "houkago"]


def sources(obj, acc):
    if isinstance(obj, dict):
        if "source" in obj and obj.get("source"):
            acc[obj["source"]] += 1
        for v in obj.values():
            sources(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            sources(v, acc)


def drop_dead_links(results):
    """区の一覧に載っている施設サイト等のURLが 404/410 なら外す（未確認にする）。"""
    targets = {}
    for recs in results.values():
        for r in recs:
            for k in ("official", "intro"):
                u = r["links"][k]["value"]
                if u:
                    targets.setdefault(u, []).append((r, k))
    with ThreadPoolExecutor(8) as ex:
        res = dict(zip(targets, ex.map(status, targets)))
    for u, st in res.items():
        if st in (404, 410):
            for r, k in targets[u]:
                r["links"][k] = U(f"区の一覧にあるURLが{st}のため外しました（{TODAY}）")
            print("リンク切れのため外した:", st, u)


def main():
    os.makedirs(OUT, exist_ok=True)
    sets = {
        "adachi-hoiku": adachi.collect_hoiku,
        "adachi-gakudo": adachi.collect_gakudo,
        "taito-hoiku": taito.collect_hoiku,
        "taito-gakudo": taito.collect_gakudo,
    }
    results = {}
    for key, fn in sets.items():
        recs, seen = [], {}
        for r in fn():
            if r["id"] in seen and seen[r["id"]] == json.dumps(r["address"], ensure_ascii=False):
                continue  # 区の一覧で同じ施設が2回載っている場合
            seen[r["id"]] = json.dumps(r["address"], ensure_ascii=False)
            recs.append(r)
        ids = Counter(r["id"] for r in recs)
        dup = [i for i, c in ids.items() if c > 1]
        if dup:
            raise SystemExit(f"{key}: id が重複しています {dup}")
        recs.sort(key=lambda r: (TYPE_ORDER.index(r["type"]), r["name"]))
        path = os.path.join(OUT, f"{key}.json")
        if os.path.exists(path):
            old = json.load(open(path))
            if len(recs) < len(old) * 0.7:
                raise SystemExit(f"{key}: 件数が {len(old)} → {len(recs)} に減りました。取得失敗の可能性があるため中止します")
        results[key] = recs
    drop_dead_links(results)
    acc = Counter()
    for key, recs in results.items():
        with open(os.path.join(OUT, f"{key}.json"), "w") as f:
            json.dump(recs, f, ensure_ascii=False, indent=1)
            f.write("\n")
        sources(recs, acc)
        print(key, len(recs), dict(Counter(r["type"] for r in recs)))
    with open(os.path.join(ROOT, "data", "sources.json"), "w") as f:
        json.dump({"collectedAt": TODAY, "sources": [{"url": u, "fields": n} for u, n in sorted(acc.items())]}, f, ensure_ascii=False, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
