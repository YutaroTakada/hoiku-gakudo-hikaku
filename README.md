# 保育園・学童 比較

自治体の公式情報から、保育園・学童の時間・料金・空きを並べて比べる静的サイト。

公開先: https://yutarotakada.github.io/hoiku-gakudo-hikaku/

## 構成

| 場所 | 中身 |
|---|---|
| `src/config/` | エリア（市区町村）・カテゴリ・種別・表示項目・絞り込みの設定。画面とスキーマはここから作る |
| `data/facilities/*.json` | 施設データ（`scripts/collect.py` が書き出す） |
| `src/lib/schema.ts` | スキーマ。ビルド時に全件を検証し、1件でも不正ならビルドが止まる |
| `src/pages/` | `/`・`/p/<都道府県id>/`・`/a/<エリアid>/<カテゴリid>/`・`/f/<id>/`・`/compare/`・`/about/` |
| `scripts/` | 収集（`collect.py` と市区町村ごとの `<id>.py`）・差分（`diff_data.py`）・リンク確認（`check_links.py`） |
| `docs/DESIGN.md` | デザインの決まり（Astryx から写したトークン） |
| `docs/IMAGES-DESIGN.md` | 街区照合と施設画像の仕組み |

一覧の検索・絞り込み・並べ替えは URL のクエリに残る（例 `/a/<エリアid>/hoiku/?age=1&vac=1&sort=end`）。比較に入れた施設（4件まで）は端末の localStorage に残る。

旧 `/hoiku/`・`/gakudo/` は地域を指定した URL を新しい一覧へ転送する。地域の指定がなく、掲載地域が複数ある場合はトップへ移動する。

## 市区町村を足す

1. 必要なら `src/config/areas.json` の `prefectures` に都道府県を追加し、`areas` にその id を `prefecture` として指定した市区町村を追加する
2. `scripts/<id>.py` に `collect_hoiku()` と `collect_gakudo()` を書く
3. `python3 scripts/collect.py` で `data/facilities/<id>-*.json` を作る。施設が1件以上ある地域・カテゴリだけが公開される

## 手元で動かす

```sh
npm ci
npm run dev    # http://localhost:4321/hoiku-gakudo-hikaku/
npm run build

python3 -m pip install -r scripts/requirements.txt   # poppler-utils の pdftotext も必要
python3 scripts/collect.py
python3 scripts/locate.py --all  # 位置と地図を全件再生成
```

## 方針

- すべての値に出どころと確認日。確認できない値は「未確認」。推測で埋めない
- 確認日から90日を過ぎた値は「古い可能性あり」
- 口コミ・評価・ランキングなし。施設や自治体への問い合わせはしない
- 週次チェック（`weekly-check.yml`）は値が変わったときだけPRを出す。main への反映は人がマージしたときだけ
