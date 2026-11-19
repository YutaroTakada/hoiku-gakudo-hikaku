# 保育園・学童 比較（足立区・台東区）

足立区と台東区の保育施設・学童保育・放課後子ども教室を、区の公式情報で比べるサイトです。

公開先: https://yutarotakada.github.io/hoiku-gakudo-hikaku/

## しくみ

- `scripts/collect.py` … 区の公式ページ・PDF・CSV・オープンデータから施設データを集め、`data/facilities/*.json` に書き出します。
  - 公式ページで確かめられない値は `null`（サイトでは「未確認」）。推測で埋めません。
  - すべての値に出どころ URL（`source`）と確認日（`checked`）を付けます。
  - 前回より件数が3割以上減ったら、取得失敗とみなして書き出さずに止まります。
- `src/lib/schema.ts` … 施設データのスキーマ。ビルド時に全件を検証し、不正なデータが1件でもあればビルドが失敗します。
- Astro で静的サイトを生成し、GitHub Actions で GitHub Pages に公開します。
- 週次チェック：毎週月曜 6:00（日本時間）に GitHub Actions が `collect.py` を実行し、変わったデータをコミットして公開し直します。

## 手元で動かす

```sh
npm ci
npm run dev          # http://localhost:4321/hoiku-gakudo-hikaku/

# データを集め直す（poppler-utils の pdftotext が必要）
python3 -m pip install -r scripts/requirements.txt
python3 scripts/collect.py
```

## 方針

- 口コミ・評価・ランキングは載せません。施設ごとに「見学で聞くこと」を置きます。
- 確認日から90日を過ぎた値には「古い可能性あり」と出します。
- 施設や区役所へのメール・電話での問い合わせはしません。
