# -*- coding: utf-8 -*-
"""포트폴리오 + 뉴스를 메일용 텍스트 리포트로 조립. (평가손익 강조 + 직전 발송 대비 변동)"""

import json
import os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
LAST_MAIL_PATH = os.path.join(os.path.dirname(__file__), 'last_mail.json')


def _won(n: float) -> str:
    return f"{n:+,.0f}원"


def _mark(n: float) -> str:
    """이익이면 ▲, 손실이면 ▼, 변동 없으면 -."""
    if n > 0:
        return "▲"
    if n < 0:
        return "▼"
    return "-"


def _load_last_mail() -> dict:
    """직전 메일 발송 시점의 시세 스냅샷을 읽음."""
    try:
        with open(LAST_MAIL_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_last_mail(portfolio: dict):
    """이번 메일 발송 시점의 시세 스냅샷을 저장 (다음 발송 때 비교용)."""
    snapshot = {
        "sent_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "total_value_krw": portfolio["summary"]["total_value_krw"],
        "prices": {},
    }
    for row in portfolio["rows"]:
        if "error" not in row:
            snapshot["prices"][row["name"]] = row["price"]
    for w in portfolio.get("watchlist", []):
        if "error" not in w:
            snapshot["prices"][w["name"]] = w["price"]
    try:
        with open(LAST_MAIL_PATH, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"  last_mail.json 저장 오류: {e}")


def build_report(portfolio: dict, news: dict) -> str:
    now = datetime.now(KST).strftime("%m/%d %H:%M")
    s = portfolio["summary"]
    lines = [f"📊 주식 리포트 ({now})", ""]

    # ── 직전 발송 대비 변동 불러오기 ──────────────────────────
    last = _load_last_mail()
    last_total = last.get("total_value_krw")
    last_prices = last.get("prices", {})
    last_sent = last.get("sent_at", "")

    # ── 평가손익 (최상단 강조) ────────────────────────────────
    pl = s["total_pl_krw"]
    lines.append("══════════════════════")
    lines.append("💰 내 평가손익 (누적)")
    lines.append(f"   {_mark(pl)} {_won(pl)}")
    lines.append(f"   ({s['total_pl_pct']:+.2f}%)")
    lines.append("══════════════════════")
    lines.append("")

    # ── 자산 요약 ─────────────────────────────────────────────
    lines.append("[ 내 자산 요약 ]")
    lines.append(f"· 총 평가금액: {s['total_value_krw']:,.0f}원")
    lines.append(f"· 전일 대비: {_mark(s['day_change_krw'])} {_won(s['day_change_krw'])} "
                 f"({s['day_change_pct']:+.2f}%)")

    # 직전 메일 대비 자산 변동
    if last_total is not None:
        diff = s["total_value_krw"] - last_total
        diff_pct = (diff / last_total * 100) if last_total else 0
        lines.append(f"· 직전 메일 대비: {_mark(diff)} {_won(diff)} ({diff_pct:+.2f}%)")
        lines.append(f"  (직전 발송: {last_sent})")

    if s.get("usdkrw"):
        lines.append(f"· 적용 환율: {s['usdkrw']:,.1f}원/$")

    # ── 종목별 시세 / 손익 ────────────────────────────────────
    lines.append("")
    lines.append("[ 종목별 현황 ]")
    for row in portfolio["rows"]:
        if "error" in row:
            lines.append(f"· {row['name']}: 조회 실패")
            continue
        unit = "$" if row["currency"] == "USD" else "원"
        price = f"{row['price']:,.2f}{unit}" if row["currency"] == "USD" \
                else f"{row['price']:,.0f}{unit}"

        # 직전 메일 대비 종목 가격 변동
        last_p = last_prices.get(row["name"])
        if last_p:
            p_diff_pct = (row["price"] - last_p) / last_p * 100 if last_p else 0
            change_str = f" / 직전比 {_mark(p_diff_pct)} {p_diff_pct:+.2f}%"
        else:
            change_str = ""

        lines.append(
            f"\n· {row['name']}\n"
            f"  현재가 {price} (일간 {row['day_change_pct']:+.2f}%{change_str})\n"
            f"  ▶ 평가손익 {_mark(row['pl_krw'])} {_won(row['pl_krw'])} "
            f"({row['pl_pct']:+.2f}%)"
        )

    # ── 관심 종목 시세 (있을 때만) ────────────────────────────
    watchlist = portfolio.get("watchlist", [])
    if watchlist:
        lines.append("")
        lines.append("[ 관심 종목 시세 ]")
        for w in watchlist:
            if "error" in w:
                lines.append(f"· {w['name']}: 조회 실패")
                continue
            unit = "$" if w["currency"] == "USD" else "원"
            price = (f"{w['price']:,.2f}{unit}" if w["currency"] == "USD"
                     else f"{w['price']:,.0f}{unit}")
            # 직전 메일 대비 변동
            last_p = last_prices.get(w["name"])
            if last_p:
                p_diff_pct = (w["price"] - last_p) / last_p * 100 if last_p else 0
                change_str = f" / 직전比 {_mark(p_diff_pct)} {p_diff_pct:+.2f}%"
            else:
                change_str = ""
            lines.append(
                f"\n· {w['name']}\n"
                f"  현재가 {price} (일간 {w['day_change_pct']:+.2f}%{change_str})"
            )

    # ── 뉴스 (있을 때만) ──────────────────────────────────────
    if news:
        lines.append("")
        lines.append("[ 인기 뉴스 ]")
        for code, n in news.items():
            lines.append(f"\n■ {n['name']}")
            for a in n.get("domestic", []):
                lines.append(f"· (국내) {a['title']}")
                if a.get("link"):
                    lines.append(f"  {a['link']}")
            for a in n.get("overseas", []):
                lines.append(f"· (해외) {a['title']}")
                if a.get("link"):
                    lines.append(f"  {a['link']}")

    # ── 이번 발송 스냅샷 저장 (다음 메일 비교용) ──────────────
    _save_last_mail(portfolio)

    return "\n".join(lines)
