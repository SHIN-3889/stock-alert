# -*- coding: utf-8 -*-
"""메인 — 실행 시각에 따라 다르게 작동.

06:00 (KST) → 시세 + 뉴스 + 번역 + 메일 + latest.json 저장
15:30, 20:00 (KST) → 시세 + 메일 + latest.json 저장 (뉴스 생략)
"""

import json
import os
from datetime import datetime, timezone, timedelta

import portfolio
import message_builder
import mailer

# 뉴스는 06시 실행에서만 수집
KST = timezone(timedelta(hours=9))


def is_morning_run() -> bool:
    """현재 시각이 06시 실행인지 판단 (KST 05:30~07:00 사이면 아침 실행으로 간주)."""
    now_h = datetime.now(KST).hour
    return 5 <= now_h <= 7


def save_latest(portfolio_data: dict, news_data: list):
    """최신 시세/자산 결과를 latest.json 으로 저장."""
    latest_path = os.path.join(os.path.dirname(__file__), 'latest.json')

    # 기존 뉴스 유지 (뉴스 수집 안 하는 경우)
    if news_data is None:
        try:
            with open(latest_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            news_data = existing.get("news", [])
        except (FileNotFoundError, json.JSONDecodeError):
            news_data = []

    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "updated_at": now_kst,
        "portfolio":  portfolio_data,
        "news":       news_data,
    }
    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  latest.json 저장 완료 ({now_kst})")


def run_once():
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    morning = is_morning_run()

    print(f"\n===== 실행 시작 {now_str} ({'아침 - 뉴스 포함' if morning else '일반 - 시세만'}) =====")

    # 1) 시세/자산 수집 (항상)
    print("1) 시세/자산 수집 중...")
    pf = portfolio.build_portfolio()

    # 2) 뉴스 수집 (아침 실행만)
    nw = None
    if morning:
        print("2) 뉴스 수집/번역 중...")
        import news as news_mod
        nw = news_mod.collect_news()
    else:
        print("2) 뉴스 수집 생략 (시세 전용 실행)")

    # 3) 리포트 조립
    print("3) 리포트 조립 중...")
    report = message_builder.build_report(pf, nw if nw else [])

    # 4) latest.json 저장
    print("4) latest.json 저장 중...")
    try:
        save_latest(pf, nw)
    except Exception as e:
        print(f"  latest.json 저장 오류: {e}")

    # 5) 메일 발송
    print("5) 메일 발송 중...")
    try:
        subject = f"📊 주식 리포트 {datetime.now(KST).strftime('%m/%d %H:%M')}"
        mailer.send_email(subject, report)
    except Exception as e:
        print(f"  메일 발송 오류: {e}")

    print("===== 실행 완료 =====")
    return report


if __name__ == "__main__":
    run_once()
