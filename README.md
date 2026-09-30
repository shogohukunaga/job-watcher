# 新着案件ウォッチャー

クラウドワークスとママワークスを10分ごとにチェックし、キーワードに合う新着案件を
**提案文の下書き付きで Gmail に通知**します。応募は自分で行います（自動応募はしません）。

- 実行場所: GitHub Actions（公開リポジトリなら無料。PCの電源がオフでも動きます）
- 通知: Gmail（無料。1回のチェックで見つかった新着をまとめて1通）
- 下書き: ひな形に案件名を差し込む方式（無料）。【】の部分を自分で埋めて使います

## 初期設定

### 1. Gmail のアプリパスワードを発行する
1. Googleアカウントで2段階認証を有効にする
2. https://myaccount.google.com/apppasswords で、アプリパスワード（16文字）を発行する

### 2. GitHub の Secrets に登録する
リポジトリの Settings → Secrets and variables → Actions → New repository secret で、次の値を登録します。

| 名前 | 中身 |
|---|---|
| `GMAIL_ADDRESS` | 送信に使う Gmail アドレス |
| `GMAIL_APP_PASSWORD` | 手順1のアプリパスワード |
| `PROPOSAL_TEMPLATE`（任意） | 自分用の提案文のひな形。`proposal_template.example.txt` をコピーし、名前・実績URL・稼働時間などを埋めて貼り付ける。`{title}` は案件名、`{site}` はサイト名、`{reward}` は報酬に置き換わる。登録しない場合は見本のひな形が使われる |
| `MAIL_TO`（任意） | 通知先を別のアドレスにしたい場合 |

### （任意・有料）AIで案件ごとの下書きを作る場合
`config.yaml` の `draft` を `ai` にし、Secret `ANTHROPIC_API_KEY`（https://console.anthropic.com/ で発行）と
`PROFILE_TEXT`（`profile.example.md` を参考にしたプロフィール）を登録します。案件1件あたり数円かかります。

### 3. 動作を確認する
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
`--test` を使う場合は、`.env.example` をコピーして `.env` を作ってください。自分用のひな形は `proposal_template.txt` に書けます（どちらも GitHub には上がりません）。

## 注意
- サイトの負荷にならないよう、リクエストの間隔を1.5秒あけ、キーワード検索は新着順の1ページ目だけを見ています。
  ママワークスは robots.txt で検索URLが禁止されているため、パラメータなしのカテゴリ一覧だけを見ています。
- サイトの作りが変わると取得できなくなることがあります。3回続けて失敗すると、エラーメールが届きます。
- 下書きはあくまでたたき台です。内容を確認・修正してから送ってください。
