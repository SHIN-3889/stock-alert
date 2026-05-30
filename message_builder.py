# -*- coding: utf-8 -*-
"""포트폴리오 + 뉴스를 메일용 텍스트 리포트로 조립. (평가손익 강조)"""

from datetime import datetime


def _won(n: float) -> str:
    return f"{n:+,.0f}원"


def _mark(n: float) -> str:
    """이익이면 ▲, 손실이면 ▼, 변동 없으면 -."""
    if n > 0:
        return "▲"
    if n < 0:
        return "▼"
    return "-"


def build_report(portfolio: dict, news: dict) -> str:
    now = datetime.now().strftime("%m/%d %H:%M")
    s = portfolio["summary"]
    lines = [f"📊 주식 리포트 ({now})", ""]

    # ── 평가손익 (최상단 강조) ────────────────────
    pl = s["total_pl_krw"]
    lines.append("══════════════════════")
    lines.append("💰 내 평가손익 (누적)")
    lines.append(f"   {_mark(pl)} {_won(pl)}")
    lines.append(f"   ({s['total_pl_pct']:+.2f}%)")
    lines.append("══════════════════════")
    lines.append("")

    # ── 자산 요약 ────────────────────────────────
    lines.append("[ 내 자산 요약 ]")
    lines.append(f"· 총 평가금액: {s['total_value_krw']:,.0f}원")
    lines.append(f"· 전일 대비: {_mark(s['day_change_krw'])} {_won(s['day_change_krw'])} "
                 f"({s['day_change_pct']:+.2f}%)")
    if s.get("usdkrw"):
        lines.append(f"· 적용 환율: {s['usdkrw']:,.1f}원/$")

    # ── 종목별 시세 / 손익 ───────────────────────
    lines.append("")
    lines.append("[ 종목별 현황 ]")
    for row in portfolio["rows"]:
        if "error" in row:
            lines.append(f"· {row['name']}: 조회 실패")
            continue
        unit = "$" if row["currency"] == "USD" else "원"
        price = f"{row['price']:,.2f}{unit}" if row["currency"] == "USD" \
                else f"{row['price']:,.0f}{unit}"
        lines.append(
            f"\n· {row['name']}\n"
            f"  현재가 {price} (일간 {row['day_change_pct']:+.2f}%)\n"
            f"  ▶ 평가손익 {_mark(row['pl_krw'])} {_won(row['pl_krw'])} "
            f"({row['pl_pct']:+.2f}%)"
        )

    # ── 뉴스 ────────────────────────────────────
    lines.append("")
    lines.append("[ 인기 뉴스 ]")
    for code, n in news.items():
        lines.append(f"\n■ {n['name']}")
        for a in n["domestic"]:
            lines.append(f"· (국내) {a['title']}")
            if a["link"]:
                lines.append(f"  {a['link']}")
        for a in n["overseas"]:
            lines.append(f"· (해외) {a['title']}")
            if a["link"]:
                lines.append(f"  {a['link']}")

    return "\n".join(lines)
