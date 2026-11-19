#!/usr/bin/env python3
"""位置参照情報と施設住所を照合し、地図画像を生成する。"""
import argparse
import collections
import csv
import io
import json
import math
import os
import tempfile
import time
import urllib.request
from datetime import date
from PIL import Image
import re
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WARD_NAMES = {'adachi': '足立区', 'taito': '台東区'}
LABELS = ('住居一致', '街区一致', '町字まで（不採用）', '区外・不一致（不採用）', '保育ママ（対象外）', '住所なし')


def normalize(s):
    s = unicodedata.normalize('NFKC', s or '')
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\s+', '', s).translate(str.maketrans('‐‑‒–—―−ー', '--------'))
    digits = {'〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    def kanji_num(m):
        t = m.group(1)
        if '十' in t:
            a, b = t.split('十'); n = (digits.get(a, 1) if a else 1) * 10 + (digits.get(b, 0) if b else 0)
        else:
            n = digits[t]
        return str(n) + '丁目'
    s = re.sub(r'([〇零一二三四五六七八九十]+)丁目', kanji_num, s)
    return s.replace('丁目', '-').replace('番地の', '-').replace('番地', '-').replace('番', '-').replace('号', '')


def load_index(path):
    blocks, towns = collections.defaultdict(set), collections.defaultdict(set)
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.endswith('.csv')]
        if len(names) != 1: raise ValueError('ZIP 内に CSV が1つ必要です')
        with io.TextIOWrapper(z.open(names[0]), encoding='cp932', newline='') as f:
            for row in csv.DictReader(f):
                ward = row['市区町村名']
                if ward not in WARD_NAMES.values(): continue
                town = normalize(row['大字・丁目名'] + row['小字・通称名'])
                towns[ward].add(town.rstrip('-'))
                if row['住居表示フラグ'] != '1' or row['代表フラグ'] != '1' or row['更新前履歴フラグ'] != '0': continue
                block = unicodedata.normalize('NFKC', row['街区符号・地番'])
                if not block.isdigit(): continue
                key = (ward, town.rstrip('-'), str(int(block)))
                blocks[key].add((row['緯度'], row['経度'], row['大字・丁目名'] + row['小字・通称名'] + block + '番'))
    return blocks, towns


def match(facility, blocks, towns):
    address = facility['address']['value']
    if not address: return LABELS[5], None
    ward = WARD_NAMES[facility['ward']]
    s = normalize(address)
    # 他区や他県の明示を黙って取り除かない。
    if re.search(r'(?:東京都)?[^\d-]+区', s):
        prefix, s = s.split('区', 1)
        if prefix not in (ward[:-1], '東京都' + ward[:-1]): return "区外または住所を解析できないため不採用", None
    elif s.startswith('東京都'): s = s[3:]
    candidates = []
    for town in towns[ward]:
        if not s.startswith(town): continue
        rest = s[len(town):]
        # 丁目の末尾を削って比較するため区切り必須。町名と数字は直結してよい。
        if town[-1:].isdigit() and rest and not rest.startswith('-'): continue
        rest = rest.lstrip('-')
        m = re.match(r'(\d+)(?=-|$|[^\d])', rest)
        if m:
            for point in blocks.get((ward, town, str(int(m.group(1)))), set()):
                candidates.append((len(town), point))
    if candidates:
        longest = max(x[0] for x in candidates)
        points = {x[1] for x in candidates if x[0] == longest}
        if len(points) == 1: return LABELS[1], points.pop()
        return "複数の街区候補があるため不採用", None
    if any(s.startswith(t) and (not t[-1:].isdigit() or len(s) == len(t) or s[len(t):].startswith('-')) for t in towns[ward]):
        return LABELS[2], None
    return "住所を解析できないか街区が一致しないため不採用", None


ZIP_URL = "https://nlftp.mlit.go.jp/isj/dls/data/24.0a/13000-24.0a.zip"
GSI = "https://maps.gsi.go.jp/development/ichiran.html"
UA = "hoiku-gakudo-hikaku (https://github.com/YutaroTakada/hoiku-gakudo-hikaku)"
CACHE = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "hoiku-gakudo-hikaku-cache"
TYPES = {t["id"]: t for t in json.loads((ROOT / "src/config/catalog.json").read_text())["types"]}
MAPS = ROOT / "public/img/map"
MAP_ZOOM = 16
MAP_WIDTH, MAP_HEIGHT = 480, 240
MAP_CONTRAST = 0.6
last_fetch = 0.0

def fetch(url, path, tile=False):
    global last_fetch
    if path.exists(): return
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        if tile:
            time.sleep(max(0, 0.5 - (time.monotonic() - last_fetch)))
            last_fetch = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=45) as r:
                data = r.read()
            path.write_bytes(data)
            return
        except Exception:
            if attempt == 3: raise
            time.sleep(2 ** attempt)

def map_image(lat, lng):
    z = MAP_ZOOM
    scale = 256 * (2 ** z)
    x = (float(lng) + 180) / 360 * scale
    y = (1 - math.asinh(math.tan(math.radians(float(lat)))) / math.pi) / 2 * scale
    left, top = round(x - MAP_WIDTH / 2), round(y - MAP_HEIGHT / 2)
    canvas = Image.new("RGB", (MAP_WIDTH, MAP_HEIGHT))
    for tx in range(left // 256, (left + MAP_WIDTH - 1) // 256 + 1):
        for ty in range(top // 256, (top + MAP_HEIGHT - 1) // 256 + 1):
            path = CACHE / f"tiles/{z}/{tx}/{ty}.png"
            fetch(f"https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{tx}/{ty}.png", path, True)
            with Image.open(path) as tile: canvas.paste(tile.convert("RGB"), (tx * 256 - left, ty * 256 - top))
    canvas = canvas.convert("L").point([255 - round((255 - p) * MAP_CONTRAST) for p in range(256)])
    out = io.BytesIO()
    canvas.save(out, format="WEBP", quality=10, method=6)
    return out.getvalue()

def field(value, source=None, checked=None, note=None):
    result = {"value": value, "source": source, "checked": checked}
    if note: result["note"] = note
    return result

def enrich(results, old, force=False):
    today = date.today().isoformat()
    index = None
    pending = {}
    for records in results.values():
        for f in records:
            previous = old.get(f["id"])
            map_enabled = TYPES[f["type"]].get("map", True)
            map_note = TYPES[f["type"]].get("mapNote", "この種別は地図を表示しません")
            if (not force and previous and previous["address"]["value"] == f["address"]["value"]
                and previous["type"] == f["type"] and "location" in previous and "image" in previous
                and ((map_enabled and (previous["location"]["source"] is not None or previous["location"]["value"] is not None)) or (not map_enabled and previous["location"]["value"] is None and previous["image"]["value"] is None
                                     and previous["location"].get("note") == map_note))):
                f["location"], f["image"] = previous["location"], previous["image"]
                if f["image"]["value"] and not (MAPS / (f["id"] + ".webp")).is_file():
                    raise FileNotFoundError(f"既存の画像がありません: {f['id']}")
                continue
            if not map_enabled:
                label, point = map_note, None
            elif not f["address"]["value"]:
                label, point = "住所なし", None
            else:
                if index is None:
                    zip_path = CACHE / "13000-24.0a.zip"
                    fetch(ZIP_URL, zip_path)
                    index = load_index(zip_path)
                label, point = match(f, *index)
            if point:
                lat, lng, matched = point
                f["location"] = field({"lat": float(lat), "lng": float(lng), "level": "block", "matched": matched}, ZIP_URL, today, "街区代表点です")
                f["image"] = field({"kind": "map", "path": f"/img/map/{f['id']}.webp", "width": MAP_WIDTH, "height": MAP_HEIGHT}, GSI, today)
                pending[f["id"]] = map_image(lat, lng)
            else:
                f["location"] = field(None, None if not map_enabled else ZIP_URL, today, label)
                f["image"] = field(None, note=label)
    MAPS.mkdir(parents=True, exist_ok=True)
    for id, data in pending.items():
        (MAPS / (id + ".webp")).write_bytes(data)
    keep = {f["id"] + ".webp" for records in results.values() for f in records if f["image"]["value"]}
    for path in MAPS.glob("*.webp"):
        if path.name not in keep: path.unlink()

def main():
    parser = argparse.ArgumentParser(description="施設の街区照合と地図生成")
    parser.add_argument("--all", action="store_true", help="全件を再照合・再生成")
    args = parser.parse_args()
    paths = sorted((ROOT / "data/facilities").glob("*.json"))
    results = {p.stem: json.loads(p.read_text()) for p in paths}
    old = {f["id"]: f.copy() for records in results.values() for f in records}
    enrich(results, old, args.all)
    for p in paths:
        p.write_text(json.dumps(results[p.stem], ensure_ascii=False, indent=1) + "\n")
    counts = collections.Counter("地図" if f["image"]["value"] else f["location"].get("note", "不明") for records in results.values() for f in records)
    print(dict(counts))

if __name__ == "__main__": main()
