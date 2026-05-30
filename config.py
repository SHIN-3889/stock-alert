# -*- coding: utf-8 -*-
"""
=====================================================================
 설정 파일
 - API 키는 GitHub Secrets(환경 변수)에서 자동으로 읽어옵니다.
 - 보유 종목/시각은 settings.json 파일에서 읽어옵니다.
   (settings.json 은 휴대폰 화면에서 수정 가능)
 - settings.json 이 없으면 아래 기본값을 사용합니다.
=====================================================================
"""

import json
import os

# ── 환경 변수에서 API 키 읽기 (GitHub Secrets) ───────
NAVER_CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
NEWSAPI_KEY         = os.environ.get("NEWSAPI_KEY", "")
GMAIL_ADDRESS       = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")
MAIL_TO             = os.environ.get("MAIL_TO", GMAIL_ADDRESS)

# ── 기본 보유 종목 (settings.json 없을 때만 사용) ─────
_DEFAULT_HOLDINGS = {
    "GEV": {
        "name": "GE버노바", "market": "US",
        "shares": 42, "avg_price": 1044.9593,
        "kr_query": "GE버노바", "en_query": "GE Vernova",
    },
    "006400": {
        "name": "삼성SDI", "market": "KR",
        "shares": 241, "avg_price": 584874,
        "kr_query": "삼성SDI", "en_query": "Samsung SDI",
    },
    "476550": {
        "name": "TIGER 미국30년국채커버드콜액티브(H)", "market": "KR",
        "shares": 503, "avg_price": 7156,
        "kr_query": "TIGER 미국30년국채 커버드콜", "en_query": None,
    },
}
_DEFAULT_RUN_TIMES = ["06:00", "15:30", "20:00"]

# ── settings.json 에서 사용자 설정 읽기 ─────────────
_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
try:
    with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
        _settings = json.load(f)
    HOLDINGS  = _settings.get("holdings",  _DEFAULT_HOLDINGS)
    RUN_TIMES = _settings.get("run_times", _DEFAULT_RUN_TIMES)
except (FileNotFoundError, json.JSONDecodeError):
    HOLDINGS  = _DEFAULT_HOLDINGS
    RUN_TIMES = _DEFAULT_RUN_TIMES

# ── 뉴스 설정 ────────────────────────────────────
NEWS_PER_STOCK     = 3
TRANSLATE_OVERSEAS = True
