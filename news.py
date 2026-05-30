# -*- coding: utf-8 -*-
"""뉴스 수집 — 국내(네이버 뉴스 API) + 해외(NewsAPI.org), 해외분 자동 번역.

* '가장 많이 바이럴된' 기사는 무료 API로 정밀 측정이 어렵습니다.
  - 해외: NewsAPI 의 sortBy=popularity (인기순) 으로 근사
  - 국내: 네이버는 인기순 정렬이 없어 관련도순(sim) 상위로 근사
"""

import html
import re
import requests

import config

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None


def _clean(text: str) -> str:
    """네이버 응답의 HTML 태그/엔티티 제거."""
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def fetch_naver_news(query: str, count: int) -> list:
    """국내 뉴스 (관련도순)."""
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": count, "sort": "sim"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
        return [{"title": _clean(i["title"]), "link": i["originallink"] or i["link"]}
                for i in items[:count]]
    except Exception as e:
        return [{"title": f"(국내 뉴스 조회 실패: {e})", "link": ""}]


def fetch_overseas_news(query: str, count: int) -> list:
    """해외 뉴스 (인기순) + 한글 번역."""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "popularity",
        "language": "en",
        "pageSize": count,
        "apiKey": config.NEWSAPI_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        arts = r.json().get("articles", [])
    except Exception as e:
        return [{"title": f"(해외 뉴스 조회 실패: {e})", "link": ""}]

    out = []
    for a in arts[:count]:
        title = a.get("title", "")
        ko = title
        if config.TRANSLATE_OVERSEAS and GoogleTranslator and title:
            try:
                ko = GoogleTranslator(source="auto", target="ko").translate(title)
            except Exception:
                ko = title  # 번역 실패 시 원문 유지
        out.append({"title": ko, "title_orig": title, "link": a.get("url", "")})
    return out


def collect_news() -> dict:
    """전 종목 뉴스 수집."""
    result = {}
    for code, h in config.HOLDINGS.items():
        entry = {"name": h["name"], "domestic": [], "overseas": []}
        if h.get("kr_query"):
            entry["domestic"] = fetch_naver_news(h["kr_query"], config.NEWS_PER_STOCK)
        if h.get("en_query"):
            entry["overseas"] = fetch_overseas_news(h["en_query"], config.NEWS_PER_STOCK)
        result[code] = entry
    return result
