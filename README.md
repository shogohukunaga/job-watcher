# 新着案件ウォッチャー

クラウドワークスとママワークスを10分ごとにチェックし、キーワードに合う新着案件を
**提案文の下書き付きで Gmail に通知**します。応募は自分で行います（自動応募はしません）。

- 実行場所: GitHub Actions（PCの電源がオフでも動きます）
- 通知: Gmail（1回のチェックで見つかった新着をまとめて1通）
- 下書き: Claude API（案件1件あたり数円程度）

## 初期設定

### 1. Gmail のアプリパスワードを発行する
1. Googleアカウントで2段階認証を有効にする
2. https://myaccount.google.com/apppasswords で、アプリパスワード（16文字）を発行する

### 2. Anthropic の APIキーを発行する
https://console.anthropic.com/ で APIキーを発行します（クレジットのチャージが必要です）。
下書きが不要なら、この手順を飛ばして `config.yaml` の `draft: false` にしてください。

### 3. プロフィールを用意する
`profile.example.md` を参考に、提案文に使うスキル・実績・ポートフォリオURLを書きます。
**ここに書いていない実績は、下書きに書かれません。**

### 4. GitHub の Secrets に登録する
リポジトリの Settings → Secrets and variables → Actions → New repository secret で、次の値を登録します。

| 名前 | 中身 |
|---|---|
| `GMAIL_ADDRESS` | 送信に使う Gmail アドレス |
| `GMAIL_APP_PASSWORD` | 手順1のアプリパスワード |
| `ANTHROPIC_API_KEY` | 手順2の APIキー |
| `PROFILE_TEXT` | 手順3のプロフィールの本文をそのまま貼り付ける |
| `MAIL_TO`（任意） | 通知先を別のアドレスにしたい場合 |

### 5. 動作を確認する
Actions タブ →「新着案件チェック」→「Run workflow」で手動実行します。
**初回は、いま掲載されている案件を既読として登録するだけで、メールは届きません。** 2回目以降から新着が通知されます。

## キーワードの変更
`config.yaml` の `keywords`（通知したい言葉）と `exclude`（通知したくない言葉）を編集して push すると、次回のチェックから反映されます。
通知が多すぎるときは `exclude` を増やしてください。

## ローカルで試す（任意）
```
pip install -r requirements.txt
python watcher.py --dry-run      # 取得と絞り込みの結果を表示するだけ
python watcher.py --test 2       # 最新の該当案件2件で、下書き付きのテストメールを送る
```
`--test` を使う場合は、`.env.example` をコピーして `.env` を作り、`profile.md` も用意してください（どちらも GitHub には上がりません）。

## 注意
- サイトの負荷にならないよう、リクエストの間隔を1.5秒あけ、キーワード検索は新着順の1ページ目だけを見ています。
  ママワークスは robots.txt で検索URLが禁止されているため、パラメータなしのカテゴリ一覧だけを見ています。
- サイトの作りが変わると取得できなくなることがあります。3回続けて失敗すると、エラーメールが届きます。
- 下書きはあくまでたたき台です。内容を確認・修正してから送ってください。
