# -*- coding: utf-8 -*-
"""
DART API를 이용한 종목별 재무 분석
- corp_code: 전체 기업목록 ZIP 다운로드 후 종목코드로 매핑
- 순부채: 총차입금 - 현금성자산 (DART 정의)
- 영업이익, 발행주식수, 자회사 정보
결과를 sotp_data.json에 저장
"""

import os
import io
import json
import time
import zipfile
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

DART_KEY   = os.environ.get("DART_API_KEY", "")
DART_BASE  = "https://opendart.fss.or.kr/api"
KST        = timezone(timedelta(hours=9))
OUTPUT     = os.path.join(os.path.dirname(__file__), "sotp_data.json")
SETTINGS   = os.path.join(os.path.dirname(__file__), "settings.json")


# ── 설정에서 한국 종목 가져오기 ─────────────────────────────────────
def load_kr_holdings():
    try:
        with open(SETTINGS, "r", encoding="utf-8") as f:
            s = json.load(f)
        result = {}
        for code, info in {**s.get("holdings", {}), **s.get("watchlist", {})}.items():
            if info.get("market") == "KR":
                # ETF 제외 (종목코드 6자리 숫자 중 앞 3자리가 4xx이면 ETF)
                if code.startswith(('4', '2')):
                    print(f"  ETF/리츠 제외: {info['name']} ({code})")
                    continue
                result[code] = info
        return result
    except Exception as e:
        print(f"설정 로드 실패: {e}")
        return {}


# ── DART 전체 기업목록 다운로드 → stock_code → corp_code 매핑 ───────
def build_corp_map():
    print("DART 기업목록 다운로드 중...")
    try:
        url = f"{DART_BASE}/corpCode.xml"
        res = requests.get(url, params={"crtfc_key": DART_KEY}, timeout=30)
        z = zipfile.ZipFile(io.BytesIO(res.content))
        xml_data = z.read("CORPCODE.xml")
        root = ET.fromstring(xml_data)
        corp_map = {}
        for item in root.findall("list"):
            stock_code = item.findtext("stock_code", "").strip()
            corp_code  = item.findtext("corp_code", "").strip()
            if stock_code:
                corp_map[stock_code] = corp_code
        print(f"  기업 수: {len(corp_map):,}개")
        return corp_map
    except Exception as e:
        print(f"기업목록 다운로드 실패: {e}")
        return {}


# ── 재무제표 조회 ────────────────────────────────────────────────────
def get_financial_data(corp_code, bsns_year, fs_div="CFS", reprt_code="11011"):
    try:
        url = f"{DART_BASE}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": DART_KEY,
            "corp_code":  corp_code,
            "bsns_year":  bsns_year,
            "reprt_code": "11011",
            "fs_div":     fs_div,
        }
        res  = requests.get(url, params=params, timeout=20)
        data = res.json()
        if data.get("status") == "000":
            return data.get("list", [])
        print(f"  재무데이터 status: {data.get('status')} / {data.get('message')}")
    except Exception as e:
        print(f"  재무데이터 조회 실패: {e}")
    return []


# ── 계정과목 금액 추출 ───────────────────────────────────────────────
def extract_amount(fin_list, keywords):
    for item in fin_list:
        acct_id = item.get("account_id", "") or ""
        acct_nm = item.get("account_nm", "") or ""
        for kw in keywords:
            if kw in acct_id or kw in acct_nm:
                raw = (item.get("thstrm_amount") or "0").replace(",", "").replace(" ", "")
                try:
                    val = int(raw.lstrip("-"))
                    return val
                except:
                    pass
    return 0


# ── 순부채 계산 ──────────────────────────────────────────────────────
def calc_net_debt(fin_list):
    short_borrow = extract_amount(fin_list, ["ShortTermBorrowings",  "단기차입금"])
    current_ltd  = extract_amount(fin_list, ["CurrentPortionOfLongTermBorrowings", "유동성장기부채", "유동성장기차입금"])
    long_borrow  = extract_amount(fin_list, ["LongTermBorrowings",   "장기차입금"])
    bonds        = extract_amount(fin_list, ["BondsIssued",          "사채"])
    cash         = extract_amount(fin_list, ["CashAndCashEquivalents","현금및현금성자산"])
    short_fin    = extract_amount(fin_list, ["ShortTermFinancialInstruments", "단기금융상품"])

    total_debt = short_borrow + current_ltd + long_borrow + bonds
    total_cash = cash + short_fin
    net_debt   = total_debt - total_cash

    print(f"    단기차입금:      {short_borrow:>20,}원")
    print(f"    유동성장기부채:  {current_ltd:>20,}원")
    print(f"    장기차입금:      {long_borrow:>20,}원")
    print(f"    사채:            {bonds:>20,}원")
    print(f"    총차입금:        {total_debt:>20,}원")
    print(f"    현금및현금성자산:{cash:>20,}원")
    print(f"    단기금융상품:    {short_fin:>20,}원")
    print(f"    총현금성자산:    {total_cash:>20,}원")
    print(f"    ▶ 순부채:        {net_debt:>20,}원")

    return {
        "net_debt":    net_debt,
        "total_debt":  total_debt,
        "total_cash":  total_cash,
        "detail": {
            "short_borrowings":  short_borrow,
            "current_ltd":       current_ltd,
            "long_borrowings":   long_borrow,
            "bonds":             bonds,
            "cash":              cash,
            "short_financial":   short_fin,
        }
    }


# ── 영업이익 ─────────────────────────────────────────────────────────
def get_operating_income(fin_list):
    return extract_amount(fin_list, ["OperatingIncomeLoss", "영업이익"])


# ── 발행주식수 ───────────────────────────────────────────────────────
def get_shares_outstanding(corp_code, bsns_year, reprt_code="11011"):
    """주식총수 현황에서 발행주식수 조회"""
    try:
        # 방법1: 주식총수 현황 API
        url = f"{DART_BASE}/stockTotqySttus.json"
        params = {
            "crtfc_key":  DART_KEY,
            "corp_code":  corp_code,
            "bsns_year":  bsns_year,
            "reprt_code": reprt_code,
        }
        res  = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("status") == "000":
            for item in data.get("list", []):
                se = item.get("se", "")
                if "보통주" in se and "합계" not in se:
                    val = item.get("distb_stock_co", "0") or "0"
                    val = val.replace(",", "").strip()
                    if val and val != "-":
                        shares = int(val)
                        if shares > 0:
                            print(f"  발행주식수(보통주): {shares:,}주")
                            return shares
    except Exception as e:
        print(f"  발행주식수 조회 실패: {e}")

    # 방법2: 재무제표에서 추출
    try:
        url = f"{DART_BASE}/fnlttCmpnyIndx.json"
        params = {
            "crtfc_key":  DART_KEY,
            "corp_code":  corp_code,
            "bsns_year":  bsns_year,
            "reprt_code": "11011",
        }
        res  = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("status") == "000":
            for item in data.get("list", []):
                if "주식수" in item.get("idx_nm", ""):
                    val = item.get("idx_val", "0").replace(",", "")
                    if val and val.isdigit():
                        return int(val)
    except Exception as e:
        print(f"  발행주식수 방법2 실패: {e}")
    return 0


# ── 자회사 정보 ──────────────────────────────────────────────────────
def get_subsidiaries(corp_code, bsns_year, reprt_code="11011"):
    """특수관계인 출자현황으로 자회사 정보 조회"""
    results = []

    # 방법1: 최대주주 현황 (투자자산 포함)
    endpoints = [
        ("invstgNtcsCmn.json", "투자현황"),     # 타법인 출자현황
        ("otrCprInvstmntSttus.json", "타법인출자"),  # 타법인 출자현황
    ]

    for endpoint, desc in endpoints:
        try:
            url = f"{DART_BASE}/{endpoint}"
            params = {
                "crtfc_key":  DART_KEY,
                "corp_code":  corp_code,
                "bsns_year":  bsns_year,
                "reprt_code": reprt_code,
            }
            res  = requests.get(url, params=params, timeout=10)
            data = res.json()
            print(f"  {desc} status: {data.get('status')} / 건수: {len(data.get('list',[]))}")
            if data.get("status") == "000" and data.get("list"):
                items = data.get("list", [])
                if items and any(item.get("inv_prm") or item.get("corp_nm") for item in items):
                    results = items
                    break
        except Exception as e:
            print(f"  {desc} API 실패: {e}")

    # 방법2: fnlttSinglAcntAll에서 관계기업투자 금액 직접 추출
    if not results:
        print("  자회사 정보 직접 조회 실패 - 재무제표 주석에서 추정")

    return results


# ── 최신 보고서 정보 자동 선택 ──────────────────────────────────────
def get_latest_report():
    """현재 시점 기준 가장 최신 보고서 코드와 사업연도 반환.
    월별 기준:
    - 1~3월: 전년도 3분기보고서 (11014)
    - 4월:   전년도 사업보고서 (11011) - 아직 1분기 미공시
    - 5~7월: 당해연도 1분기보고서 (11013)
    - 8~10월: 당해연도 반기보고서 (11012)
    - 11~12월: 당해연도 3분기보고서 (11014)
    """
    now = datetime.now(KST)
    m, y = now.month, now.year
    if m <= 3:
        return str(y - 1), "11014"   # 전년도 3분기
    elif m == 4:
        return str(y - 1), "11011"   # 전년도 사업보고서
    elif m <= 7:
        return str(y), "11013"       # 당해 1분기
    elif m <= 10:
        return str(y), "11012"       # 당해 반기
    else:
        return str(y), "11014"       # 당해 3분기

REPRT_NAMES = {
    "11011": "사업보고서(연간)",
    "11012": "반기보고서",
    "11013": "1분기보고서",
    "11014": "3분기보고서",
}


# ── 종목 분석 ────────────────────────────────────────────────────────
def analyze_stock(stock_code, name, corp_code):
    print(f"\n{'='*50}")
    print(f"분석 중: {name} ({stock_code}) / corp_code: {corp_code}")

    bsns_year, reprt_code = get_latest_report()
    reprt_name = REPRT_NAMES.get(reprt_code, reprt_code)
    print(f"  기준: {bsns_year}년 {reprt_name} ({reprt_code})")

    # 연결재무제표 우선, 없으면 개별
    fin_list = get_financial_data(corp_code, bsns_year, "CFS", reprt_code)
    if not fin_list:
        print("  연결재무제표 없음 → 개별재무제표 시도")
        fin_list = get_financial_data(corp_code, bsns_year, "OFS", reprt_code)
    if not fin_list:
        # 폴백: 직전 보고서 시도 (사업보고서)
        print("  최신 보고서 없음 → 직전 사업보고서 시도")
        prev_year = str(int(bsns_year) - 1) if reprt_code != "11011" else bsns_year
        fin_list = get_financial_data(corp_code, prev_year, "CFS", "11011")
        if fin_list:
            bsns_year = prev_year
            reprt_code = "11011"
            reprt_name = "사업보고서(연간)"
            print(f"  → 전년도 사업보고서 사용: {bsns_year}")
    if not fin_list:
        return {"error": "재무데이터 없음"}

    print(f"  재무항목 수: {len(fin_list)}개")

    # 순부채
    print("  [순부채 계산]")
    net_debt_data = calc_net_debt(fin_list)

    # 영업이익
    op_income = get_operating_income(fin_list)
    print(f"  영업이익: {op_income:,}원")

    # 발행주식수
    shares = get_shares_outstanding(corp_code, bsns_year, reprt_code)
    print(f"  발행주식수: {shares:,}주")

    # 자회사
    subs = get_subsidiaries(corp_code, bsns_year, reprt_code)
    sub_list = []
    for sub in subs[:20]:
        name  = sub.get("inv_prm", "").strip()
        ratio = sub.get("trmend_blce_qota_rt", "").strip()  # 기말 지분율
        qty   = sub.get("trmend_blce_qy", "0").replace(",", "").strip()  # 기말 보유주식수
        book  = sub.get("trmend_blce_acntbk_amount", "0").replace(",", "").strip()  # 기말 장부가액
        purps = sub.get("invstmnt_purps", "")  # 투자목적

        if not name:
            continue

        # 경영참여 목적인 것만 포함 (단순투자 제외)
        if purps and "단순투자" in purps:
            continue

        try:
            ratio_f = float(ratio) if ratio and ratio != "-" else 0.0
            qty_i   = int(qty) if qty and qty.isdigit() else 0
            book_i  = int(book) if book and book.lstrip("-").isdigit() else 0
        except:
            ratio_f, qty_i, book_i = 0.0, 0, 0

        sub_list.append({
            "name":            name,
            "ownership_ratio": ratio_f,
            "shares_held":     qty_i,
            "book_value":      book_i,
            "investment_purpose": purps,
        })
        print(f"    자회사: {name} ({ratio_f}%) 보유주식: {qty_i:,}주 장부가: {book_i:,}원")

    # 잉여현금 계산
    print("  [잉여현금 계산]")
    revenue = get_revenue(fin_list)
    total_cash = net_debt_data["total_cash"]
    excess_cash_data = calc_excess_cash(total_cash, revenue, stock_code)

    return {
        "stock_code":        stock_code,
        "name":              name,
        "bsns_year":         bsns_year,
        "reprt_name":        reprt_name,
        "operating_income":  op_income,
        "revenue":           revenue,
        "shares_outstanding": shares,
        "net_debt":          net_debt_data,
        "excess_cash":       excess_cash_data,
        "subsidiaries":      sub_list,
        "updated_at":        datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── 메인 ─────────────────────────────────────────────────────────────
def main():
    if not DART_KEY:
        print("DART_API_KEY 없음")
        return

    kr_holdings = load_kr_holdings()
    if not kr_holdings:
        print("한국 종목 없음")
        return

    # 전체 기업목록으로 corp_code 매핑
    corp_map = build_corp_map()
    if not corp_map:
        print("기업목록 로드 실패")
        return

    results = {}
    for stock_code, info in kr_holdings.items():
        corp_code = corp_map.get(stock_code)
        if not corp_code:
            print(f"  {stock_code} ({info['name']}): corp_code 없음")
            results[stock_code] = {"error": f"corp_code 없음: {stock_code}"}
            continue
        try:
            results[stock_code] = analyze_stock(stock_code, info["name"], corp_code)
            time.sleep(1)
        except Exception as e:
            results[stock_code] = {"error": str(e)}
            print(f"  {stock_code} 분석 실패: {e}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✓ sotp_data.json 저장 완료")


if __name__ == "__main__":
    main()
