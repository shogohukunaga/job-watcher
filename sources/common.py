import html
import json
import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
REQUEST_INTERVAL = 1.5  # サイトに負荷をかけないよう、リクエストの間隔をあける（秒）

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"})
_last_request = 0.0


def fetch(url: str) -> str:
    global _last_request
    wait = REQUEST_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        res = _session.get(url, timeout=30)
    finally:
        _last_request = time.monotonic()
    res.raise_for_status()
    if "charset" not in res.headers.get("Content-Type", "").lower():
        res.encoding = "utf-8"
    return res.text


@dataclass
class Job:
    site: str  # "crowdworks" / "mamaworks"
    id: str
    title: str
    url: str
    summary: str = ""  # 一覧で取れる概要（キーワード判定に使う）
    reward: str = ""
    deadline: str = ""
    category: str = ""  # 職種など（除外判定に使う）
    description: str = ""  # 下書き用の全文（新着だけ取得する）
    extra: dict = field(default_factory=dict)

    @property
    def site_label(self) -> str:
        return {"crowdworks": "クラウドワークス", "mamaworks": "ママワークス"}.get(self.site, self.site)


def _html_to_text(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def load_description(job: Job) -> None:
    """詳細ページから仕事内容の全文を取る。候補の中で一番長いものを使い、失敗したら概要のまま"""
    candidates = [job.summary]
    try:
        soup = BeautifulSoup(fetch(job.url), "html.parser")
        # 構造化データ(JSON-LD の JobPosting)。クラウドワークスは &lt;br&gt; の形で二重にエスケープされている。
        # ママワークスは途中で省略されている
        for sc in soup.select('script[type="application/ld+json"]'):
            data = json.loads(sc.string or "{}")
            if isinstance(data, dict) and data.get("@type") == "JobPosting" and data.get("description"):
                candidates.append(_html_to_text(html.unescape(data["description"])))
        # ママワークスの募集要項の表
        if body := soup.select_one("section.p-recruit-show__contents"):
            candidates.append(re.sub(r"\n\s*\n+", "\n\n", body.get_text("\n", strip=True)))
    except Exception as e:  # noqa: BLE001 - 詳細が取れなくても通知は続ける
        print(f"  詳細の取得に失敗 {job.url}: {e}")
    job.description = max(candidates, key=len)


def matches(job: Job, keywords: list[str], exclude: list[str]) -> bool:
    head = f"{job.title}\n{job.category}".lower()
    if any(w.lower() in head for w in exclude):
        return False
    text = f"{job.title}\n{job.category}\n{job.summary}".lower()
    return any(w.lower() in text for w in keywords)
