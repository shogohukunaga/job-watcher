"""クラウドワークス: 検索結果ページに埋め込まれたJSON（#vue-container の data 属性）を読む"""
import json
from urllib.parse import quote

from bs4 import BeautifulSoup

from .common import Job, fetch

BASE = "https://crowdworks.jp"
SEARCH_URL = BASE + "/public/jobs/search?search%5Bkeywords%5D={kw}&order=new"


def _yen(v) -> str:
    return f"{int(v):,}円" if v else ""


def _range(lo, hi) -> str:
    lo, hi = _yen(lo), _yen(hi)
    if lo and hi:
        return lo if lo == hi else f"{lo}〜{hi}"
    if lo:
        return f"{lo}〜"
    if hi:
        return f"〜{hi}"
    return "相談"


def _format_payment(payment: dict) -> str:
    if p := payment.get("hourly_payment"):
        return "時間単価 " + _range(p.get("min_hourly_wage"), p.get("max_hourly_wage"))
    if p := payment.get("fixed_price_payment"):
        return "固定報酬 " + _range(p.get("min_budget"), p.get("max_budget"))
    if p := payment.get("fixed_price_writing_payment"):
        return f"記事単価 {_yen(p.get('article_price'))}"
    if p := payment.get("task_payment"):
        return f"タスク単価 {_yen(p.get('task_price') or p.get('price'))}"
    return ""


def search(keyword: str) -> list[Job]:
    page = fetch(SEARCH_URL.format(kw=quote(keyword)))
    el = BeautifulSoup(page, "html.parser").select_one("#vue-container")
    if el is None or not el.get("data"):
        raise RuntimeError("クラウドワークスの検索結果を読み取れませんでした（ページ構造が変わった可能性）")
    data = json.loads(el["data"])
    jobs = []
    for item in data["searchResult"]["job_offers"]:
        offer = item["job_offer"]
        jobs.append(
            Job(
                site="crowdworks",
                id=str(offer["id"]),
                title=offer["title"],
                url=f"{BASE}/public/jobs/{offer['id']}",
                summary=offer.get("description_digest") or "",
                reward=_format_payment(item.get("payment") or {}),
                deadline=f"応募期限 {offer['expired_on']}" if offer.get("expired_on") else "",
            )
        )
    return jobs


def fetch_all(keywords: list[str]) -> list[Job]:
    """キーワードごとに新着順の1ページ目を取得し、重複を除いて返す"""
    found: dict[str, Job] = {}
    for kw in keywords:
        for job in search(kw):
            found.setdefault(job.id, job)
    return list(found.values())
