"""ママワークス: パラメータなしのカテゴリ一覧ページ（更新が新しい順）を読み、手元でキーワード判定する"""
import re

from bs4 import BeautifulSoup

from .common import Job, fetch

JOB_HREF = re.compile(r"/job/(\d+)$")


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def _first_line(s: str, limit: int = 60) -> str:
    line = next((x.strip() for x in s.splitlines() if x.strip()), "")
    return line if len(line) <= limit else line[:limit] + "…"


def parse_page(page: str) -> list[Job]:
    soup = BeautifulSoup(page, "html.parser")
    jobs: dict[str, Job] = {}

    # 一覧のカード（掲載期間・職種・タイトル・本文が入っている）
    for box in soup.select(".p-recruit-index__result-box"):
        a = box.find("a", href=JOB_HREF)
        if not a:
            continue
        job_id = JOB_HREF.search(a["href"]).group(1)
        reward = ""
        detail = box.select_one(".p-recruit-index__result-detail-box p")
        if detail and "報酬" in _text(detail.find("span")):
            reward = _first_line(detail.get_text("\n").split("：", 1)[-1])
        period = _text(a.select_one(".p-recruit-index__result-job-application-period"))
        jobs[job_id] = Job(
            site="mamaworks",
            id=job_id,
            title=_text(a.select_one(".p-recruit-index__result-ttl")),
            url=f"https://mamaworks.jp/job/{job_id}",
            category=_text(a.select_one(".p-recruit-index__result-job-type")),
            summary=_text(a.select_one(".p-recruit-index__result-description")),
            reward=reward,
            deadline=period,
        )

    # サイドの「新着」カード（全カテゴリ共通。一覧に無いものだけ追加）
    for a in soup.select("a.p-top-content__content-new-link"):
        m = JOB_HREF.search(a.get("href", ""))
        if not m or m.group(1) in jobs:
            continue
        job_id = m.group(1)
        jobs[job_id] = Job(
            site="mamaworks",
            id=job_id,
            title=_text(a.select_one(".p-top-content__content-new-header-catch_copy")),
            url=f"https://mamaworks.jp/job/{job_id}",
            category=_text(a.select_one(".p-top-content__content-new-body-detail")),
            summary=_text(a.select_one(".p-top-content__content-new-body")),
            reward=_first_line(_text(a.select_one(".p-top-content__content-new-body-salary"))),
        )

    return list(jobs.values())


def fetch_all(pages: list[str]) -> list[Job]:
    found: dict[str, Job] = {}
    for url in pages:
        jobs = parse_page(fetch(url))
        if not jobs:
            raise RuntimeError(f"ママワークスの一覧を読み取れませんでした（ページ構造が変わった可能性）: {url}")
        for job in jobs:
            found.setdefault(job.id, job)
    return list(found.values())
