"""新着案件ウォッチャー

クラウドワークス／ママワークスをチェックし、キーワードに合う新着案件を
提案文の下書き付きで Gmail に通知する。

  python watcher.py            通常実行（新着を通知して state/seen.json を更新）
  python watcher.py --dry-run  取得と絞り込みの結果を表示するだけ（メール・下書き・保存なし）
  python watcher.py --test 2   既読に関係なく最新の該当案件2件でテストメールを送る（保存なし）
"""
import argparse
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

import yaml

from sources import crowdworks, mamaworks
from sources.common import Job, load_description, matches

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state" / "seen.json"
MAX_SEEN = 3000  # サイトごとに覚えておく案件IDの上限
FAIL_ALERT_AT = 3  # 取得が何回続けて失敗したらエラーメールを送るか


def load_dotenv() -> None:
    """ローカル実行用: .env の KEY=VALUE を環境変数に読み込む（GitHub では Secrets を使う）"""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def load_profile() -> str:
    if text := os.environ.get("PROFILE_TEXT", "").strip():
        return text
    local = ROOT / "profile.md"
    return local.read_text(encoding="utf-8") if local.exists() else ""


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"seen": {}, "fail_count": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    # 書き込み途中で停止しても、元の既読リストを壊さない。
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=STATE_FILE.parent, suffix=".tmp", delete=False
        ) as f:
            temp = Path(f.name)
            f.write(json.dumps(state, ensure_ascii=False, indent=1) + "\n")
        temp.replace(STATE_FILE)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def collect(config: dict) -> tuple[dict[str, list[Job]], dict[str, str]]:
    """サイトごとに案件を集める。失敗したサイトはエラー内容を返す"""
    sites = config["sites"]
    fetchers = {
        "crowdworks": lambda: crowdworks.fetch_all(config["keywords"]),
        "mamaworks": lambda: mamaworks.fetch_all(sites["mamaworks"]["pages"]),
    }
    results, errors = {}, {}
    for name, fetch_fn in fetchers.items():
        if not sites.get(name, {}).get("enabled", True):
            continue
        try:
            jobs = fetch_fn()
            results[name] = [j for j in jobs if matches(j, config["keywords"], config["exclude"])]
            print(f"{name}: {len(jobs)}件取得 → キーワード該当 {len(results[name])}件")
        except Exception as e:  # noqa: BLE001 - 片方のサイトが落ちても、もう片方は続ける
            errors[name] = f"{type(e).__name__}: {e}"
            print(f"{name}: 取得失敗 {errors[name]}", file=sys.stderr)
            traceback.print_exc()
    return results, errors


def load_template() -> str:
    if text := os.environ.get("PROPOSAL_TEMPLATE", "").strip():
        return text
    for name in ("proposal_template.txt", "proposal_template.example.txt"):
        if (ROOT / name).exists():
            return (ROOT / name).read_text(encoding="utf-8").strip()
    return ""


def fill_template(template: str, job: Job) -> str:
    return (
        template.replace("{title}", job.title)
        .replace("{site}", job.site_label)
        .replace("{reward}", job.reward or "記載なし")
    )


def make_drafts(jobs: list[Job], config: dict) -> dict[str, str]:
    for job in jobs:
        load_description(job)
    mode = config.get("draft", "template")
    if mode == "template":
        # 無料: テンプレートに案件名を差し込むだけ（【】の部分は自分で埋める）
        template = load_template()
        return {f"{j.site}:{j.id}": fill_template(template, j) for j in jobs} if template else {}
    if mode != "ai":
        return {}
    # 有料: Claude API で案件ごとに下書きを作る
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY が無いので下書きは作りません")
        return {}
    import anthropic

    from drafter import make_draft

    client = anthropic.Anthropic()
    profile = load_profile() or "（プロフィール未設定）"
    drafts = {}
    for job in jobs:
        print(f"  下書き作成中: {job.title[:40]}")
        drafts[f"{job.site}:{job.id}"] = make_draft(client, job, profile)
    return drafts


def mail(subject: str, body: str) -> None:
    from notifier import send

    address = os.environ["GMAIL_ADDRESS"]
    send(address, os.environ["GMAIL_APP_PASSWORD"], os.environ.get("MAIL_TO") or address, subject, body)
    print(f"メール送信: {subject}")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="表示のみ（メール・下書き・保存なし）")
    mode.add_argument("--test", type=int, metavar="N", help="最新の該当案件N件でテストメールを送る（保存なし）")
    args = parser.parse_args()
    if args.test is not None and args.test < 1:
        parser.error("--test は1以上の件数を指定してください")

    load_dotenv()
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    state = load_state()
    results, errors = collect(config)

    if args.dry_run:
        for name, jobs in results.items():
            seen = set(state["seen"].get(name, []))
            for j in jobs:
                mark = "   " if j.id in seen else "NEW"
                print(f"[{mark}] {name} {j.id} {j.title[:50]} | {j.reward}")
        return 1 if errors else 0

    if args.test:
        jobs = [j for name in results for j in results[name]][: args.test]
        if not jobs:
            print("該当案件がありませんでした")
            return 0
        from notifier import build_jobs_mail

        subject, body = build_jobs_mail(jobs, make_drafts(jobs, config))
        mail("【テスト】" + subject, body)
        return 0

    # 通常実行: 新着を判定する
    new_jobs: list[Job] = []
    for name, jobs in results.items():
        first_run = name not in state["seen"]
        seen = state["seen"].get(name, [])
        seen_set = set(seen)
        fresh = [j for j in jobs if j.id not in seen_set]
        if first_run:
            # 初回はいま出ている案件を既読にするだけ（大量のメールを防ぐ）
            print(f"{name}: 初回実行のため {len(fresh)}件を既読として登録（通知なし）")
        else:
            new_jobs += fresh
        state["seen"][name] = (seen + [j.id for j in fresh])[-MAX_SEEN:]

    if new_jobs:
        from notifier import build_jobs_mail

        print(f"新着 {len(new_jobs)}件")
        subject, body = build_jobs_mail(new_jobs, make_drafts(new_jobs, config))
        mail(subject, body)
    else:
        print("新着なし")

    # 取得エラーが続いたときだけ知らせる
    for name in config["sites"]:
        if name in errors:
            count = state["fail_count"].get(name, 0) + 1
            state["fail_count"][name] = count
            if count == FAIL_ALERT_AT:
                mail(
                    f"【案件ウォッチャー】{name} の取得が{count}回続けて失敗しています",
                    f"エラー内容:\n{errors[name]}\n\nサイトの構造が変わった可能性があります。"
                    "GitHub の Actions のログを確認してください。",
                )
        else:
            state["fail_count"][name] = 0

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
