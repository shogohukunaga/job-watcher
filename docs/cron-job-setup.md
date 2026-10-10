# 無料で10分ごとに起動する設定

cron-job.org が10分ごとに GitHub に実行を依頼し、これまでどおり GitHub Actions が案件を確認します。
PCの電源を切っていても動きます。応募は本人が行い、下書きは無料の `template` のまま使います。

## 1. cron-job.org に登録する

[管理画面](https://console.cron-job.org/) で無料アカウントを作り、確認メールの認証を済ませます。
パスワード・トークンはチャットへ貼らず、本人が設定画面に直接入力してください。

## 2. このリポジトリ専用の GitHub トークンを作る

[Fine-grained personal access tokens](https://github.com/settings/personal-access-tokens) を開き、Generate new token を選びます。

| 設定 | 値 |
|---|---|
| Token name | `job-watcher-cron` |
| Resource owner | `shogohukunaga` |
| Expiration | 90日など、本人が管理できる期限 |
| Repository access | Only select repositories → `job-watcher` のみ |
| Repository permissions | Actions → Read and write |

Metadata の読み取りは自動で付きます。Contents の書き込み権限や他リポジトリへの権限は不要です。
トークンの発行と、下記の Authorization 欄への入力は本人が行います。

## 3. cron-job.org でジョブを作る

Cronjobs → Create cronjob から設定します。

| 設定 | 値 |
|---|---|
| Title | 新着案件チェック（10分ごと） |
| URL | `https://api.github.com/repos/shogohukunaga/job-watcher/actions/workflows/watch.yml/dispatches` |
| Execution schedule | Every 10 minutes |
| Request method | POST |
| Request body | `{"ref":"main"}` |

Advanced 側のヘッダー設定に以下を登録します。Authorization の値を本人が貼り付けます。

| Header name | Value |
|---|---|
| Authorization | `Bearer ` に続けて発行したトークン（空白1個を挟む） |
| Accept | `application/vnd.github+json` |
| Content-Type | `application/json` |
| X-GitHub-Api-Version | `2022-11-28` |

まずは無効のまま保存します。初めての疎通確認では本文を
`{"ref":"main","inputs":{"dry_run":true}}` にして実行すると、メール送信も既読変更もしません。
確認後に本文を `{"ref":"main"}` に戻して有効化します。

失敗時・失敗からの復旧時・自動停止時の通知を有効にしてください。毎回成功した通知は不要です。

## 4. 動いたことを確認し、GitHub の定期実行を止める

1. cron-job.org のテスト実行が HTTP `204` で成功することを確認します。
2. [GitHub Actions](https://github.com/shogohukunaga/job-watcher/actions/workflows/watch.yml) で
   `workflow_dispatch` の実行が成功し、両サイトの取得が成功していることを確認します。
   cron-job.org の成功だけでは案件チェックやメール送信の成功までは分かりません。
3. 本文を通常用へ戻して有効化し、約10分間隔の定期実行を2回確認します。
   新着があると本人宛てに通常の通知メールが届きます。
4. リポジトリの Settings → Secrets and variables → Actions → **Variables** に
   `EXTERNAL_SCHEDULER_ENABLED` を値 `true` で登録します。
   これにより GitHub 標準の schedule からの処理だけをスキップし、重複するチェックを止めます。
   手動実行や cron-job.org からの実行は続きます。

**外部の定期実行を確認する前に、この変数を true にしないでください。**
元に戻す場合は変数を削除するか `false` にします。
Actions 全体の「Disable workflow」は使いません。外部からの起動も止まってしまいます。

## トークンの更新・トラブル時

- トークンが期限切れになる前に本人が更新し、cron-job.org の Authorization を入れ替えてテストします。
- HTTP 401：トークンの期限切れ・取り消し・貼り付けを確認します。
- HTTP 403/404：対象リポジトリ、Actions の Read and write、URLを確認します。
- HTTP 422：Request body と `main`、入力名を確認します。
- HTTP 204 でも GitHub 側が失敗：Actions のログでサイト取得・メール送信・既読保存を確認します。
- cron-job.org が停止・未設定の間は `EXTERNAL_SCHEDULER_ENABLED` を `false` に戻します。

GitHub の起動待ちやサイト側の拒否があるため、10分ごとの取得を保証する仕組みではありません。
403 を回避するためのプロキシなどは使いません。

公式資料： [cron-job.org FAQ](https://cron-job.org/en/faq/) ／
[GitHub の workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
