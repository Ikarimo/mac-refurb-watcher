# mac-refurb-watcher

Apple認定整備済製品(日本ストア)を約5分おきに監視し、条件に合うMacが出た瞬間に
[ntfy.sh](https://ntfy.sh) 経由でスマホへプッシュ通知する。

## 仕組み

- GitHub Actions のcron (`*/5 * * * *`) で `monitor.py` を実行
  (混雑時は数分遅れることがある)
- [整備済Mac一覧](https://www.apple.com/jp/shop/refurbished/mac) に埋め込まれた
  `REFURB_GRID_BOOTSTRAP` JSONをパースして全在庫を取得
- `config.json` の条件(モデル/チップ/メモリ/価格上限)に一致する商品を抽出
- 前回実行時 (`state.json`) との差分で「新着」だけを通知
- 通知はntfyのトピックへ送信。クリックで商品ページに直行

## 監視条件の変更

`config.json` を編集してpushするだけ。

- `max_price`: 全体の価格上限(円)
- `rules[]`: `model`(macstudio / macmini / macbookpro / imac / macbookair)、
  `title_regex`(チップ名など)、`min_memory_gb`、`max_price`(ルール個別の上限)

## セットアップ

1. スマホに ntfy アプリを入れ、トピックを購読する
2. リポジトリの Settings → Secrets and variables → Actions → Variables に
   `NTFY_TOPIC` を設定
3. Actions を有効化(初回は手動で `workflow_dispatch` 実行して動作確認)

## テスト通知

```
NTFY_TOPIC=<topic> python monitor.py --test
```

## 注意

- ntfyのトピック名は実質パスワード。推測されにくいランダム名を使い、公開しない
- 通知が来たら商品ページを開いて **自分で** 購入する(購入は自動化しない)
- 公開リポジトリの場合、60日間コミットがないとcronが自動停止する
  (在庫変動でstate.jsonが定期的にコミットされるため実質問題になりにくい)
