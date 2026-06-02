# -*- coding: utf-8 -*-
"""
DART API를 이용한 종목별 재무 분석
- 본업 가치: 사업부문별 EBITDA × EV/EBITDA 배수
- 자회사 가치: 상장사(시가), 비상장사(장부가)
- 순부채: 총차입금 - 현금성자산
결과를 sotp_data.json에 저장
"""

import os
import json
import time
import requests
import yfinance as yf
from datetime import datetime, timezone, timedelta

DART_KEY = os.environ.get("DART_API_KEY", "")
DART_BASE = "https://opendart.fss.or.kr/api"
KST = timezone(timedelta(hours=9))
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "sotp_data.json")
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "settings.json")

# ── 설정에서 한국 종목 가져오기 ─────────────────────────────────────
def load_kr_holdings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
        holdings = settings.get("holdings", {})
        watchlist = settings.get("watchlist", {})
        kr = {}
        for code, info in {**holdings, **watchlist}.items():
            if info.get("market") == "KR":
                kr[code] = info
        return kr
    except Exception as e:
        print(f"설정 로드 실패: {e}")
        return {}

# ── DART: 종목코드로 corp_code 조회 ─────────────────────────────────
def get_corp_code(stock_code):
    """종목코드(6자리)로 DART corp_code 조회"""
    try:
        url = f"{DART_BASE}/company.json"
        params = {"crtfc_key": DART_KEY, "stock_code": stock_code}
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("status") == "000":
            return data.get("corp_code")
    except Exception as e:
        print(f"  corp_code 조회 실패 ({stock_code}): {e}")
    return None

# ── DART: 최신 사업연도 조회 ────────────────────────────────────────
def get_latest_year(corp_code):
    """최근 완료된 사업연도 반환"""
    now = datetime.now(KST)
    # 4월 이전이면 전전년도, 4월 이후면 전년도 (사업보고서 제출 기준)
    if now.month < 4:
        return str(now.year - 2)
    return str(now.year - 1)

# ── DART: 재무제표 단일 항목 조회 ────────────────────────────────────
def get_financial_data(corp_code, bsns_year, fs_div="CFS"):
    """연결재무제표(CFS) 또는 개별재무제표(OFS) 조회"""
    try:
        url = f"{DART_BASE}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": DART_KEY,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": "11011",  # 사업보고서
            "fs_div": fs_div,
        }
        res = requests.get(url, params=params, timeout=15)
        data = res.json()
        if data.get("status") == "000":
            return data.get("list", [])
    except Exception as e:
        print(f"  재무데이터 조회 실패: {e}")
    return []

# ── 특정 계정 금액 추출 ──────────────────────────────────────────────
def extract_amount(fin_list, account_ids):
    """account_id 리스트 중 하나라도 매칭되면 금액 반환 (원 단위)"""
    for item in fin_list:
        acct_id = item.get("account_id", "")
        acct_nm = item.get("account_nm", "")
        for aid in account_ids:
            if aid in acct_id or aid in acct_nm:
                amt_str = item.get("thstrm_amount", "0") or "0"
                try:
                    return int(amt_str.replace(",", "").replace("-", "").strip() or "0")
                except:
                    pass
    return 0

# ── 순부채 계산 ──────────────────────────────────────────────────────
def calc_net_debt(fin_list):
    """
    순부채 = 총차입금 - 총현금성자산
    총차입금 = 단기차입금 + 유동성장기부채 + 장기차입금 + 사채
    총현금성자산 = 현금및현금성자산 + 단기금융상품
    """
    short_borrow = extract_amount(fin_list, ["ShortTermBorrowings", "단기차입금"])
    current_ltd   = extract_amount(fin_list, ["CurrentPortionOfLongTermBorrowings", "유동성장기부채", "유동성장기차입금"])
    long_borrow   = extract_amount(fin_list, ["LongTermBorrowings", "장기차입금"])
    bonds         = extract_amount(fin_list, ["BondsIssued", "사채"])
    cash          = extract_amount(fin_list, ["CashAndCashEquivalents", "현금및현금성자산"])
    short_fin     = extract_amount(fin_list, ["ShortTermFinancialInstruments", "단기금융상품"])

    total_debt = short_borrow + current_ltd + long_borrow + bonds
    total_cash = cash + short_fin
    net_debt   = total_debt - total_cash

    print(f"    단기차입금: {short_borrow:,}원")
    print(f"    유동성장기부채: {current_ltd:,}원")
    print(f"    장기차입금: {long_borrow:,}원")
    print(f"    사채: {bonds:,}원")
    print(f"    총차입금: {total_debt:,}원")
    print(f"    현금및현금성자산: {cash:,}원")
    print(f"    단기금융상품: {short_fin:,}원")
    print(f"    총현금성자산: {total_cash:,}원")
    print(f"    ▶ 순부채: {net_debt:,}원")

    return {
        "total_debt": total_debt,
        "total_cash": total_cash,
        "net_debt": net_debt,
        "detail": {
            "short_borrowings": short_borrow,
            "current_ltd": current_ltd,
            "long_borrowings": long_borrow,
            "bonds": bonds,
            "cash": cash,
            "short_financial": short_fin,
        }
    }

# ── 영업이익 조회 ────────────────────────────────────────────────────
def get_operating_income(fin_list):
    """연결 영업이익"""
    return extract_amount(fin_list, ["OperatingIncomeLoss", "영업이익"])

# ── 발행주식수 조회 ──────────────────────────────────────────────────
def get_shares_outstanding(corp_code, bsns_year):
    """DART 주요 재무정보에서 발행주식수 조회"""
    try:
        url = f"{DART_BASE}/fnlttCmpnyIndx.json"
        params = {
            "crtfc_key": DART_KEY,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": "11011",
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("status") == "000":
            for item in data.get("list", []):
                if "발행주식수" in item.get("idx_nm", ""):
                    val = item.get("idx_val", "0").replace(",", "")
                    return int(val)
    except Exception as e:
        print(f"  발행주식수 조회 실패: {e}")
    return 0

# ── 자회사 정보 조회 ─────────────────────────────────────────────────
def get_subsidiaries(corp_code, bsns_year):
    """종속기업/관계기업 투자 현황"""
    try:
        url = f"{DART_BASE}/hyslrSttus.json"
        params = {
            "crtfc_key": DART_KEY,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": "11011",
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("status") == "000":
            return data.get("list", [])
    except Exception as e:
        print(f"  자회사 정보 조회 실패: {e}")
    return []

# ── 상장 자회사 시가 계산 ────────────────────────────────────────────
def calc_listed_subsidiary_value(stock_code, shares_held, discount=0.4):
    """상장 자회사: 보유주식수 × 현재주가 × (1 - 할인율)"""
    try:
        ticker = f"{stock_code}.KS"
        t = yf.Ticker(ticker)
        price = float(t.fast_info.last_price)
        value = shares_held * price * (1 - discount)
        print(f"    상장자회사 {stock_code}: {price:,.0f}원 × {shares_held:,}주 × {1-discount} = {value:,.0f}원")
        return value
    except Exception as e:
        print(f"    상장자회사 시가 조회 실패 ({stock_code}): {e}")
    return 0

# ── 메인 분석 ────────────────────────────────────────────────────────
def analyze_stock(stock_code, name):
    print(f"\n{'='*50}")
    print(f"분석 중: {name} ({stock_code})")

    corp_code = get_corp_code(stock_code)
    if not corp_code:
        return {"error": f"corp_code 조회 실패: {stock_code}"}

    print(f"  corp_code: {corp_code}")
    bsns_year = get_latest_year(corp_code)
    print(f"  기준 사업연도: {bsns_year}")

    # 재무데이터 조회
    fin_list = get_financial_data(corp_code, bsns_year, "CFS")
    if not fin_list:
        print("  연결재무제표 없음, 개별재무제표 시도")
        fin_list = get_financial_data(corp_code, bsns_year, "OFS")

    if not fin_list:
        return {"error": "재무데이터 조회 실패"}

    # 순부채 계산
    print("  [순부채 계산]")
    net_debt_data = calc_net_debt(fin_list)

    # 영업이익
    op_income = get_operating_income(fin_list)
    print(f"  영업이익: {op_income:,}원")

    # 발행주식수
    shares = get_shares_outstanding(corp_code, bsns_year)
    print(f"  발행주식수: {shares:,}주")

    # 자회사 정보
    print("  [자회사 정보]")
    subsidiaries = get_subsidiaries(corp_code, bsns_year)
    sub_list = []
    for sub in subsidiaries[:10]:  # 최대 10개
        sub_list.append({
            "name": sub.get("sub_corp_nm", ""),
            "ownership_ratio": sub.get("prnt_own_rate", ""),
            "book_value": sub.get("inv_asset_blnc", "0"),
        })
        print(f"    - {sub.get('sub_corp_nm','')} ({sub.get('prnt_own_rate','')}%)")

    return {
        "stock_code": stock_code,
        "name": name,
        "bsns_year": bsns_year,
        "operating_income": op_income,
        "shares_outstanding": shares,
        "net_debt": net_debt_data,
        "subsidiaries": sub_list,
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    if not DART_KEY:
        print("DART_API_KEY 환경변수가 없습니다.")
        return

    kr_holdings = load_kr_holdings()
    if not kr_holdings:
        print("한국 종목이 없습니다.")
        return

    print(f"분석 대상: {list(kr_holdings.keys())}")

    results = {}
    for code, info in kr_holdings.items():
        try:
            result = analyze_stock(code, info["name"])
            results[code] = result
            time.sleep(1)  # API 호출 간격
        except Exception as e:
            results[code] = {"error": str(e)}
            print(f"  {code} 분석 실패: {e}")

    # 결과 저장
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✓ 분석 완료: {OUTPUT_PATH}")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str)[:1000])


if __name__ == "__main__":
    main()
