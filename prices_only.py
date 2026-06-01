# -*- coding: utf-8 -*-
"""시세만 빠르게 수집해서 latest.json 업데이트 (메일 발송 없음)."""

import json
import os
from datetime import datetime, timezone, timedelta

import config
import prices as prices_mod
import portfolio


def update_prices_only():
    """시세만 수집해서 latest.json 업데이트."""
    print(f"===== 시세 업데이트 시작 {datetime.now():%Y-%m-%d %H:%M:%S} =====")

    # 1) 기존 latest.json 읽기 (뉴스는 유지)
    latest_path = os.path.join(os.path.dirname(__file__), 'latest.json')
    existing = {}
    try:
        with open(latest_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        print("  기존 latest.json 로드 완료")
    except (FileNotFoundError, json.JSONDecodeError):
        print("  기존 latest.json 없음 - 새로 생성")

    # 2) 시세만 새로 수집
    print("  시세 수집 중...")
    pf = portfolio.build_portfolio()

    # 3) 업데이트 시각
    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")

    # 4) 뉴스는 기존 것 유지, 시세/자산만 업데이트
    data = {
        "updated_at": now_kst,
        "portfolio":  pf,
        "news":       existing.get("news", []),  # 뉴스는 기존 유지
    }

    with open(latest_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"  latest.json 업데이트 완료 ({now_kst})")
    print("===== 시세 업데이트 완료 =====")


if __name__ == "__main__":
    update_prices_only()
