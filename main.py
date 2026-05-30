# -*- coding: utf-8 -*-
"""메인 — 시세·자산·뉴스 수집 → 리포트 조립 → Gmail 전송 (1회 실행)."""

from datetime import datetime

import portfolio
import news as news_mod
import message_builder
import mailer


def run_once(send_mail: bool = True):
    print(f"\n===== 실행 시작 {datetime.now():%Y-%m-%d %H:%M:%S} =====")

    print("1) 시세/자산 수집 중...")
    pf = portfolio.build_portfolio()

    print("2) 뉴스 수집/번역 중...")
    nw = news_mod.collect_news()

    print("3) 리포트 조립 중...")
    report = message_builder.build_report(pf, nw)
    print("\n" + "-" * 50)
    print(report)
    print("-" * 50 + "\n")

    if send_mail:
        print("4) 메일 전송 중...")
        try:
            subject = f"📊 주식 리포트 {datetime.now():%m/%d %H:%M}"
            mailer.send_email(subject, report)
        except Exception as e:
            print(f"  메일 전송 오류: {e}")

    print("===== 실행 완료 =====")
    return report


if __name__ == "__main__":
    # 테스트 시에는 run_once(send_mail=False) 로 콘솔 출력만 확인 가능
    run_once(send_mail=True)
