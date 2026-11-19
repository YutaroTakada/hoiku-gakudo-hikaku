#!/usr/bin/env python3
"""位置参照情報の街区 CSV ZIP をローカル照合する試作。施設データは変更しない。"""
import argparse
import collections
import csv
import io
import json
import random
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
    if facility['type'] == 'katei': return LABELS[4], None
    if not address: return LABELS[5], None
    ward = WARD_NAMES[facility['ward']]
    s = normalize(address)
    # 他区や他県の明示を黙って取り除かない。
    if re.search(r'(?:東京都)?[^\d-]+区', s):
        prefix, s = s.split('区', 1)
        if prefix not in (ward[:-1], '東京都' + ward[:-1]): return LABELS[3], None
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
        return LABELS[3], None
    if any(s.startswith(t) and (not t[-1:].isdigit() or len(s) == len(t) or s[len(t):].startswith('-')) for t in towns[ward]):
        return LABELS[2], None
    return LABELS[3], None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('zip', help='国交省 街区レベル位置参照情報の東京都 ZIP')
    p.add_argument('--seed', type=int, default=42, help='15件抽出の乱数シード')
    args = p.parse_args()
    blocks, towns = load_index(args.zip)
    results = []
    for path in sorted((ROOT / 'data/facilities').glob('*.json')):
        for f in json.loads(path.read_text(encoding='utf-8')):
            label, point = match(f, blocks, towns)
            results.append((f, label, point))
    counts = collections.Counter(r[1] for r in results)
    print(f'全 {len(results)} 件')
    for label in LABELS: print(f'{label}: {counts[label]}')
    print(f'\nランダム15件（seed={args.seed}、座標は街区代表点）')
    for f, label, point in random.Random(args.seed).sample(results, min(15, len(results))):
        detail = f'{point[0]}, {point[1]} / {WARD_NAMES[f["ward"]]}{point[2]}' if point else '座標なし'
        print(f'{f["id"]} | {WARD_NAMES[f["ward"]]} {f["address"]["value"]} | {label} | {detail}')


if __name__ == '__main__': main()
