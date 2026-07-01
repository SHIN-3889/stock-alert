# -*- coding: utf-8 -*-
"""시세 수집 — 전 종목 yfinance 통일.
한국 종목은 코드 뒤에 .KS(KOSPI)/.KQ(KOSDAQ)를 붙여 조회합니다.
약 15분 지연 시세이며, 해외 서버(GitHub Actions)에서도 안정적으로 동작합니다.
미국 주식은 시간외 거래(프리마켓/애프터마켓) 가격도 반영합니다.
"""

import yfinance as yf
import requests
from datetime import datetime, timezone, timedelta

# ── 미국 동부시간(ET) 기준 정규장 시간 ────────────────────────────
# ET = UTC-4(서머타임) or UTC-5(겨울)
# yfinance는 서머타임을 자동 처리하므로 여기선 UTC 기준으로 간단히 판별
def _us_session_label() -> str:
    """현재 시각 기준 미국 주식 세션 레이블 반환.
    'pre'          : 프리마켓       (ET 04:00~09:30)
    'open'         : 정규장         (ET 09:30~16:00)
    'after'        : 애프터마켓     (ET 16:00~20:00)
    'market_closed': 장 마감        (ET 20:00~04:00, 주중)
    'closed'       : 휴장           (토·일)
    """
    now_utc = datetime.now(timezone.utc)
    month = now_utc.month
    offset = 4 if 3 <= month <= 11 else 5
    et_hour = (now_utc.hour - offset) % 24
    et_min  = now_utc.minute
    et_time = et_hour * 60 + et_min

    pre_start  = 4  * 60        # 04:00
    open_start = 9  * 60 + 30   # 09:30
    open_end   = 16 * 60        # 16:00
    after_end  = 20 * 60        # 20:00

    et_weekday = (now_utc - timedelta(hours=offset)).weekday()
    if et_weekday >= 5:              # 토·일 → 휴장
        return 'closed'

    if et_time < pre_start:          # 00:00~04:00 → 장 마감
        return 'market_closed'
    elif et_time < open_start:       # 04:00~09:30 → 프리마켓
        return 'pre'
    elif et_time < open_end:         # 09:30~16:00 → 정규장
        return 'open'
    elif et_time < after_end:        # 16:00~20:00 → 애프터마켓
        return 'after'
    else:                            # 20:00~24:00 → 장 마감
        return 'market_closed'


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
    'open'         : 정규장             (KST 09:00~15:30)
    'nxt'          : 장 마감(NXT 오픈)  (KST 15:30~20:00)
    'market_closed': 장 마감            (KST 20:00~09:00, 주중)
    'closed'       : 휴장               (토·일)
    """
    now_kst = datetime.now(timezone(timedelta(hours=9)))
    weekday = now_kst.weekday()
    if weekday >= 5:  # 토·일 → 휴장
        return 'closed'
    kst_time = now_kst.hour * 60 + now_kst.minute
    open_start = 9  * 60        # 09:00
    open_end   = 15 * 60 + 30   # 15:30
    nxt_end    = 20 * 60        # 20:00
    if open_start <= kst_time < open_end:   # 09:00~15:30 → 정규장
        return 'open'
    elif open_end <= kst_time < nxt_end:    # 15:30~20:00 → 장 마감(NXT 오픈)
        return 'nxt'
    else:                                   # 20:00~ 또는 ~09:00 → 장 마감
        return 'market_closed'


def _get_kr_price_naver(code: str) -> dict:
    """네이버 증권 통합시세(KRX+NXT) 조회.
    정규장엔 KRX 실시간, 애프터마켓(15:30~20:00)엔 NXT 가격을 통합시세로 사용.
    실패 시 None 반환(→ yfinance 폴백).
    """
    try:
        url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        datas = data.get("datas", [])
        if not datas:
            return None
        d = datas[0]
        krx_price = float((d.get("closePriceRaw") or "0").replace(",", "") or 0)
        if krx_price <= 0:
            return None
        prev_close = krx_price - float((d.get("compareToPreviousClosePriceRaw") or "0").replace(",", "") or 0)

        # NXT 애프터/프리마켓 정보
        over = d.get("overMarketPriceInfo") or {}
        over_price_str = (over.get("overPrice") or "").replace(",", "")
        over_session = over.get("tradingSessionType")

        # 통합시세: NXT 시간외 가격이 있으면 최신 거래가로 사용
        price = krx_price
        session = _kr_session_label()  # 기본은 시각 기반
        if over_price_str:
            try:
                over_price = float(over_price_str)
                if over_price > 0:
                    price = over_price
                    if over_session == "PRE_MARKET":
                        session = "pre"
                    elif over_session == "AFTER_MARKET":
                        session = "nxt"
            except ValueError:
                pass

        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0
        return {
            "price":      round(price, 2),
            "prev_close": round(prev_close, 2),
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency":   "KRW",
            "session":    session,
            "source":     "naver_integrated",
        }
    except Exception:
        return None


def get_kr_price(code: str) -> dict:
    """국내 종목/ETF — 네이버 통합시세(KRX+NXT) 우선, 실패 시 yfinance(.KS) 폴백."""
    # 1) 네이버 통합시세 시도 (KRX+NXT, 애프터마켓 반영)
    naver = _get_kr_price_naver(code)
    if naver:
        return naver
    # 2) 폴백: yfinance (KRX만)
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
