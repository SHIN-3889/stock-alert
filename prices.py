# -*- coding: utf-8 -*-
"""시세 수집 — 전 종목 yfinance 통일.
한국 종목은 코드 뒤에 .KS(KOSPI)/.KQ(KOSDAQ)를 붙여 조회합니다.
약 15분 지연 시세이며, 해외 서버(GitHub Actions)에서도 안정적으로 동작합니다.
"""

import yfinance as yf


def _yf_price(symbol: str, currency: str) -> dict:
    """yfinance 로 현재가 + 전일 종가 조회. 실패 시 history 로 폴백."""
    t = yf.Ticker(symbol)
    try:
        fi = t.fast_info
        price = float(fi.last_price)
        prev = float(fi.previous_close)
    except Exception:
        hist = t.history(period="5d")
        if hist.empty:
            raise RuntimeError(f"{symbol} 시세 조회 실패")
        price = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
    return {"price": price, "prev_close": prev, "currency": currency}


def get_us_price(ticker: str) -> dict:
    """미국 주식."""
    return _yf_price(ticker, "USD")


def get_kr_price(code: str) -> dict:
    """국내 종목/ETF — 코드 뒤에 .KS 붙여 yfinance 로 조회."""
    return _yf_price(f"{code}.KS", "KRW")


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
