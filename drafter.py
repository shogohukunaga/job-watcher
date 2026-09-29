"""Claude API で提案文の下書きを作る"""
import anthropic

from sources.common import Job

MODEL = "claude-opus-5-5"

SYSTEM = """あなたはWeb制作フリーランスの営業を手伝うアシスタントです。
クラウドソーシングや求人サイトの案件に送る応募文（提案文）の下書きを日本語で書きます。

書き方:
- 冒頭で挨拶と名乗りを簡潔に。その直後の1〜2文で、募集文から読み取れる「相手が困っていること・実現したいこと」を自分の言葉で言い直す
- 次に、その案件で自分ならどう進めるか・何ができるかを具体的に書く（プロフィールにあるスキル・実績だけを根拠にする）
- 募集文に質問や応募条件（ポートフォリオ提出、稼働時間、見積もりなど）があれば漏れなく答える
- 最後に、進め方の確認や打ち合わせの提案で締める
- 全体で400〜600字程度。丁寧だが堅すぎない文体。箇条書きは必要な場合だけ
- プロフィールに無い実績・数字・経歴は絶対に作らない。必要なのに情報が無い箇所は【】で囲んだ空欄（例:【稼働可能時間】）にする
- 出力は応募文の本文のみ。前置きや解説は書かない"""


def make_draft(client: anthropic.Anthropic, job: Job, profile: str) -> str:
    lines = [f"サイト: {job.site_label}", f"タイトル: {job.title}"]
    if job.category:
        lines.append(f"職種・区分: {job.category}")
    if job.reward:
        lines.append(f"報酬: {job.reward}")
    lines += ["", "募集内容:", job.description or job.summary]
    job_text = "\n".join(lines)
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"<profile>\n{profile}\n</profile>\n\n<job>\n{job_text}\n</job>\n\n"
                    "この案件への応募文の下書きを書いてください。",
                }
            ],
        )
    except anthropic.AuthenticationError:
        return "（下書きの生成に失敗: APIキーが正しくありません）"
    except anthropic.RateLimitError:
        return "（下書きの生成に失敗: APIの利用制限に達しました。しばらくすると回復します）"
    except anthropic.APIStatusError as e:
        return f"（下書きの生成に失敗: APIエラー {e.status_code}）"
    except anthropic.APIConnectionError:
        return "（下書きの生成に失敗: APIに接続できませんでした）"

    if response.stop_reason == "refusal":
        return "（この案件は下書きを生成できませんでした）"
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text or "（下書きが空でした）"
