# -*- coding: utf-8 -*-
"""시세 수집 — 전 종목 yfinance 통일.
한국 종목은 코드 뒤에 .KS(KOSPI)/.KQ(KOSDAQ)를 붙여 조회합니다.
약 15분 지연 시세이며, 해외 서버(GitHub Actions)에서도 안정적으로 동작합니다.
미국 주식은 시간외 거래(프리마켓/애프터마켓) 가격도 반영합니다.
"""

import yfinance as yf
from datetime import datetime, timezone, timedelta

# ── 미국 동부시간(ET) 기준 정규장 시간 ────────────────────────────
# ET = UTC-4(서머타임) or UTC-5(겨울)
# yfinance는 서머타임을 자동 처리하므로 여기선 UTC 기준으로 간단히 판별
def _us_session_label() -> str:
    """현재 시각 기준 미국 주식 세션 레이블 반환.
    'pre'  : 프리마켓  (ET 04:00~09:30)
    'open' : 정규장    (ET 09:30~16:00)
    'after': 애프터마켓 (ET 16:00~20:00)
    'closed': 장 마감
    """
    # 서머타임 여부에 따라 UTC-4 또는 UTC-5 이지만
    # 단순화를 위해 UTC-4(EDT, 3월~11월)와 UTC-5(EST) 기준으로 판별
    now_utc = datetime.now(timezone.utc)
    month = now_utc.month
    # 서머타임 대략 3월~11월
    offset = 4 if 3 <= month <= 11 else 5
    et_hour = (now_utc.hour - offset) % 24
    et_min  = now_utc.minute
    et_time = et_hour * 60 + et_min  # 분 단위

    pre_start  = 4  * 60        # 04:00
    open_start = 9  * 60 + 30   # 09:30
    open_end   = 16 * 60        # 16:00
    after_end  = 20 * 60        # 20:00

    # 주말 체크 (ET 기준 요일)
    # UTC 날짜 → ET 날짜 (단순화)
    et_weekday = (now_utc - timedelta(hours=offset)).weekday()  # 0=월 ~ 6=일
    if et_weekday >= 5:  # 토·일
        return 'closed'

    if pre_start <= et_time < open_start:
        return 'pre'
    elif open_start <= et_time < open_end:
        return 'open'
    elif open_end <= et_time < after_end:
        return 'after'
    else:
        return 'closed'


def _yf_price(symbol: str, currency: str, extended_hours: bool = False) -> dict:
    """yfinance 로 현재가 + 전일 종가 조회.
    extended_hours=True 이면 시간외 가격 포함.
    """
    t = yf.Ticker(symbol)
    session = None

    if extended_hours:
        session = _us_session_label()

    try:
        fi = t.fast_info
        if extended_hours and session in ('pre', 'after'):
            # 시간외: history 1분봉으로 가장 최근 가격 조회
            try:
                hist = t.history(period="1d", interval="1m", prepost=True)
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                else:
                    price = float(fi.last_price)
            except Exception:
                price = float(fi.last_price)
        else:
            price = float(fi.last_price)
        prev = float(fi.previous_close)
    except Exception:
        hist = t.history(period="5d")
        if hist.empty:
            raise RuntimeError(f"{symbol} 시세 조회 실패")
        price = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
        session = None

    return {
        "price":      price,
        "prev_close": prev,
        "currency":   currency,
        "session":    session,   # 미국: 'pre'/'open'/'after'/'closed', 한국: None
    }


def get_us_price(ticker: str) -> dict:
    """미국 주식 — 시간외 거래 포함."""
    return _yf_price(ticker, "USD", extended_hours=True)


def _kr_session_label() -> str:
    """현재 시각 기준 한국 주식 세션 레이블 반환.
    KST 기준: 정규장 09:00~15:30, 그 외 closed
    """
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    weekday = now_kst.weekday()  # 0=월 ~ 6=일
    if weekday >= 5:  # 토·일
        return 'closed'
    kst_time = now_kst.hour * 60 + now_kst.minute
    open_start = 9 * 60       # 09:00
    open_end   = 15 * 60 + 30 # 15:30
    if open_start <= kst_time < open_end:
        return 'open'
    return 'closed'


def get_kr_price(code: str) -> dict:
    """국내 종목/ETF — 코드 뒤에 .KS 붙여 yfinance 로 조회."""
    result = _yf_price(f"{code}.KS", "KRW", extended_hours=False)
    result["session"] = _kr_session_label()
    return result


def get_usdkrw() -> float:
    """원/달러 환율. 실패 시 None."""
    try:
        return float(yf.Ticker("KRW=X").fast_info.last_price)
    except Exception:
        return None


def get_price(code: str, market: str) -> dict:
    """market 값에 따라 적절한 소스로 시세 조회."""
    if market == "US":
        return get_us_price(code)
    return get_kr_price(code)
