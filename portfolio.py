# -*- coding: utf-8 -*-
"""보유 종목별 평가금액, 전일 대비 변동, 매입가 대비 손익 계산.
관심 종목(watchlist)은 시세만 가져오고 자산 계산에는 포함하지 않음.
미국 주식 시간외 거래 세션 정보도 함께 저장.
"""

import config
import prices


def build_portfolio() -> dict:
    """전 종목 시세 조회 후 자산 현황 계산."""
    usdkrw = prices.get_usdkrw()
    rows = []

    total_value_krw = 0.0
    total_prev_krw  = 0.0
    total_cost_krw  = 0.0

    for code, h in config.HOLDINGS.items():
        if h["shares"] <= 0:
            continue
        try:
            p = prices.get_price(code, h["market"])
        except Exception as e:
            rows.append({"name": h["name"], "error": str(e)})
            continue

        cur    = p["price"]
        prev   = p["prev_close"]
        shares = h["shares"]
        avg    = h["avg_price"]
        fx     = usdkrw if (h["market"] == "US" and usdkrw) else 1.0

        value_krw = cur * shares * fx
        prev_krw  = prev * shares * fx
        cost_krw  = avg * shares * fx

        total_value_krw += value_krw
        total_prev_krw  += prev_krw
        total_cost_krw  += cost_krw

        rows.append({
            "name":           h["name"],
            "currency":       p["currency"],
            "price":          cur,
            "day_change_pct": (cur - prev) / prev * 100 if prev else 0,
            "shares":         shares,
            "value_krw":      value_krw,
            "pl_krw":         value_krw - cost_krw,
            "pl_pct":         (cur - avg) / avg * 100 if avg else 0,
            "session":        p.get("session"),  # 미국: 'pre'/'open'/'after'/'closed'
        })

    summary = {
        "total_value_krw":  total_value_krw,
        "day_change_krw":   total_value_krw - total_prev_krw,
        "day_change_pct":   (total_value_krw - total_prev_krw) / total_prev_krw * 100
                            if total_prev_krw else 0,
        "total_pl_krw":     total_value_krw - total_cost_krw,
        "total_pl_pct":     (total_value_krw - total_cost_krw) / total_cost_krw * 100
                            if total_cost_krw else 0,
        "usdkrw":           usdkrw,
    }

    # ── 관심 종목 시세 (자산 계산 미포함) ──────────────────
    watchlist_rows = []
    watchlist = getattr(config, "WATCHLIST", {})
    for code, w in watchlist.items():
        try:
            p = prices.get_price(code, w["market"])
            watchlist_rows.append({
                "code":           code,
                "name":           w["name"],
                "market":         w["market"],
                "currency":       p["currency"],
                "price":          p["price"],
                "day_change_pct": (p["price"] - p["prev_close"]) / p["prev_close"] * 100
                                  if p["prev_close"] else 0,
                "session":        p.get("session"),
            })
        except Exception as e:
            watchlist_rows.append({
                "code":  code,
                "name":  w["name"],
                "error": str(e),
            })

    return {
        "rows":      rows,
        "summary":   summary,
        "watchlist": watchlist_rows,
    }
