# デザインの決まり

**Astryx の取り入れ方：トークンとパターンだけを CSS 変数として移植した（React アイランドは使わない）。** React 19 と Astryx の部品を載せると一覧で数十KB（gzip）増えるが、移植なら CSS 約3.8KB・JS 約3.4KBで済み、ビルドも依存も今のまま（Astro＋素の HTML）で保守できるため。

## 写したもの（Astryx 既定テーマ → `src/styles/global.css`）

| 種類 | 値 |
|---|---|
| 余白 | `--spacing-*`（4px 刻み） |
| 角丸 | 中身 4 / 部品 8 / 入れ物 12（入れ子は外 = 内 + 余白） |
| 影 | `--shadow-high` は浮く面（絞り込みシート・比較バー）だけ。カードは細い枠のみ |
| 色の役割 | 本文 `#0a1317`、補助 `#4e606f`、地 `#f1f4f7`＋白い面、hover/pressed は面に重ねる薄い overlay、シートの下敷き `#01122866` |
| フォーカス | 2px の基調色、3px 離す |
| 動き | `--ease-standard`（減速のみ、跳ねない）175〜230ms。`prefers-reduced-motion` で止める |
| 文字 | 本文16px（mobile-typography：M = max(B, 16)）、12 / 14 / 16 / 20 / 24、太さ 400 と 600 |

部品の形：Button（primary / secondary / ghost、高さ44px）、BottomSheet（`<dialog>`、PCでは左の列）、Item（行全体が押せる一覧）、MetadataList（ラベル＋値）、EmptyState（0件のときに条件を1つずつ外すボタン）、Banner（お知らせ）。

## サイト独自の決まり

- 色：基調はティール `#16655f` の1色相。強調は「古い可能性あり」の茶 `#753f07` だけ。すべて CSS 変数。
- 明度比（白地）：本文 18.8、補助 6.5、基調 6.9、強調 8.5。未確認のダッシュ `#7d8a96` は記号のみで 3.5（文字の「未確認」は補助色）。
- 「未確認」は薄いダッシュ「—」＋小さな注記。「古い可能性あり」は12pxの文字だけ。
- タップ領域は 44px 以上。
- 区名・種別・カテゴリ・表示項目は `src/config/` から作る。画面の文言に区名を書かない。

## 設定ファイル

- `src/config/areas.json` … エリア（区）。足すときはここ＋ `scripts/<id>.py` ＋ `data/facilities/<id>-<カテゴリ>.json`。
- `src/config/catalog.json` … カテゴリ（一覧ページ）と種別、運営区分。
- `src/config/fields.ts` … 一覧の要約・並べ替え、詳細と比較の行、絞り込み。
- `src/config/site.ts` … サイト名、比較の上限、古いとみなす日数。
