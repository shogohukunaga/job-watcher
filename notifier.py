"""Gmail（SMTP + アプリパスワード）でメールを送る"""
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from sources.common import Job


def send(address: str, app_password: str, to: str, subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("案件ウォッチャー", address))
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(address, app_password.replace(" ", ""))
        smtp.send_message(msg)


def build_jobs_mail(jobs: list[Job], drafts: dict[str, str]) -> tuple[str, str]:
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.site_label] = counts.get(job.site_label, 0) + 1
    breakdown = "・".join(f"{k}{v}" for k, v in counts.items())
    subject = f"【新着案件】{len(jobs)}件（{breakdown}）｜{jobs[0].title[:30]}"

    parts = []
    for i, job in enumerate(jobs, 1):
        lines = [
            f"■ {i}. [{job.site_label}] {job.title}",
            job.url,
        ]
        if job.reward:
            lines.append(f"報酬: {job.reward}")
        if job.deadline:
            lines.append(job.deadline)
        if job.category:
            lines.append(f"区分: {job.category[:80]}")
        if desc := (job.description or job.summary).strip():
            excerpt = desc if len(desc) <= 400 else desc[:400] + "…"
            lines += ["", "--- 募集内容（抜粋） ---", excerpt]
        draft = drafts.get(f"{job.site}:{job.id}")
        if draft:
            lines += ["", "--- 提案文の下書き（内容を確認・修正してから送ってください） ---", draft]
        parts.append("\n".join(lines))

    body = ("\n\n" + "=" * 40 + "\n\n").join(parts)
    return subject, body
