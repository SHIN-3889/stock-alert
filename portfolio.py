# -*- coding: utf-8 -*-
"""보유 종목별 평가금액, 전일 대비 변동, 매입가 대비 손익 계산."""

import config
import prices


def build_portfolio() -> dict:
    """전 종목 시세 조회 후 자산 현황 계산."""
    usdkrw = prices.get_usdkrw()  # 미국 종목 원화 환산용
    rows = []

    total_value_krw = 0.0      # 현재 평가금액(원화 환산 합계)
    total_prev_krw = 0.0       # 전일 종가 기준 평가금액 합계
    total_cost_krw = 0.0       # 매입원가 합계

    for code, h in config.HOLDINGS.items():
        if h["shares"] <= 0:
            continue
        try:
            p = prices.get_price(code, h["market"])
        except Exception as e:
            rows.append({"name": h["name"], "error": str(e)})
            continue

        cur = p["price"]
        prev = p["prev_close"]
        shares = h["shares"]
        avg = h["avg_price"]

        # 원화 환산 계수 (USD 종목이면 환율 적용)
        fx = usdkrw if (h["market"] == "US" and usdkrw) else 1.0

        value_krw = cur * shares * fx
        prev_krw = prev * shares * fx
        cost_krw = avg * shares * fx

        total_value_krw += value_krw
        total_prev_krw += prev_krw
        total_cost_krw += cost_krw

        rows.append({
            "name": h["name"],
            "currency": p["currency"],
            "price": cur,
            "day_change_pct": (cur - prev) / prev * 100 if prev else 0,
            "shares": shares,
            "value_krw": value_krw,
            "pl_krw": value_krw - cost_krw,          # 매입가 대비 손익(원화)
            "pl_pct": (cur - avg) / avg * 100 if avg else 0,
        })

    summary = {
        "total_value_krw": total_value_krw,
        "day_change_krw": total_value_krw - total_prev_krw,        # 전일 대비 변동액
        "day_change_pct": (total_value_krw - total_prev_krw) / total_prev_krw * 100
                          if total_prev_krw else 0,
        "total_pl_krw": total_value_krw - total_cost_krw,          # 누적 손익
        "total_pl_pct": (total_value_krw - total_cost_krw) / total_cost_krw * 100
                        if total_cost_krw else 0,
        "usdkrw": usdkrw,
    }
    return {"rows": rows, "summary": summary}
