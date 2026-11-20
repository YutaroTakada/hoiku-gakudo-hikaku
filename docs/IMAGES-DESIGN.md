# 施設画像と位置

施設写真は使わない。住居表示の街区まで一意に一致した施設だけ、街区代表点を中心とする地図を表示する。建物の位置ではない。地図を出さない種別と理由は `src/config/catalog.json` の `map`（既定は true）と `mapNote` で設定する。家庭的保育は住所を町名までにしているため照合しない。一致しない施設は種別の自作イラストを表示する。

`scripts/locate.py` は国土交通省の都道府県別（`src/config/areas.json` の `prefectures[].code` で選ぶ。東京都・埼玉県とも 2025年版＝令和7年版、配布版 24.0a）の[街区レベル位置参照情報](https://nlftp.mlit.go.jp/isj/)と住所を照合し、[地理院タイル（淡色地図）](https://maps.gsi.go.jp/development/ichiran.html)から z16・480×240 の WebP を生成する。グレースケールを白に寄せ、ピンは表示時に重ねる。ZIP とタイルは一時ディレクトリにキャッシュし、タイル取得は毎秒2枚以下。取得失敗時は処理を止める。

施設 JSON の `location` と `image` に出典・確認日を記録する。`collect.py` は同じ id・住所・種別の既存結果と画像を引き継ぎ、新規・住所変更を照合する。不要な地図は削除する。全件再生成は `python3 scripts/locate.py --all`。通常の `python3 scripts/locate.py` は既存結果を再利用する。ビルド時はスキーマ、位置と画像の整合性、画像ファイルの存在を検証する。

イラストは `public/img/illustration/` に置き、`src/config/catalog.json` の種別にキーを設定する。未設定時はカテゴリ共通の絵を使う。画像の出典は一覧・詳細・このサイトについてに表示する。地図画像自体へのリンクは設けない。

ズーム・サイズ・加工の設定を変えた場合は `python3 scripts/locate.py --all` で全件を再生成する。
