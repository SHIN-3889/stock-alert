# -*- coding: utf-8 -*-
"""
DART 공시 원문에서 사업부문 정보를 추출하는 테스트.
삼성SDI(006400) 사업보고서 원문을 받아서 '부문' 관련 표가 어떻게 생겼는지 확인.
GitHub Actions에서 실행 (DART_API_KEY 환경변수 사용).
"""

import os
import io
import re
import zipfile
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

DART_KEY  = os.environ.get("DART_API_KEY", "")
DART_BASE = "https://opendart.fss.or.kr/api"
KST       = timezone(timedelta(hours=9))


def build_corp_map():
    """종목코드 → corp_code 매핑"""
    url = f"{DART_BASE}/corpCode.xml"
    res = requests.get(url, params={"crtfc_key": DART_KEY}, timeout=30)
    z = zipfile.ZipFile(io.BytesIO(res.content))
    root = ET.fromstring(z.read("CORPCODE.xml"))
    m = {}
    for item in root.findall("list"):
        sc = item.findtext("stock_code", "").strip()
        cc = item.findtext("corp_code", "").strip()
        if sc:
            m[sc] = cc
    return m


def find_business_report(corp_code, bsns_year):
    """사업보고서 접수번호(rcept_no) 찾기"""
    url = f"{DART_BASE}/list.json"
    params = {
        "crtfc_key": DART_KEY,
        "corp_code": corp_code,
        "bgn_de":    f"{bsns_year}0101",
        "end_de":    f"{int(bsns_year)+1}0630",
        "pblntf_ty": "A",   # 정기공시
        "page_count": 100,
    }
    res = requests.get(url, params=params, timeout=15)
    data = res.json()
    if data.get("status") != "000":
        print(f"공시검색 실패: {data.get('status')} / {data.get('message')}")
        return None
    # 사업보고서 우선, 없으면 분기/반기보고서
    reports = data.get("list", [])
    for keyword in ["사업보고서", "반기보고서", "분기보고서"]:
        for r in reports:
            if keyword in r.get("report_nm", ""):
                print(f"  발견: {r['report_nm']} (rcept_no: {r['rcept_no']})")
                return r["rcept_no"]
    return None


def download_document(rcept_no):
    """공시 원문 ZIP 다운로드 → XML 텍스트 반환"""
    url = f"{DART_BASE}/document.xml"
    res = requests.get(url, params={"crtfc_key": DART_KEY, "rcept_no": rcept_no}, timeout=60)
    try:
        z = zipfile.ZipFile(io.BytesIO(res.content))
        names = z.namelist()
        print(f"  ZIP 내부 파일: {names}")
        # 가장 큰 XML 파일 (본문)
        biggest = max(names, key=lambda n: z.getinfo(n).file_size)
        raw = z.read(biggest)
        # 인코딩 추정 (DART는 보통 EUC-KR 또는 UTF-8)
        for enc in ["utf-8", "euc-kr", "cp949"]:
            try:
                return raw.decode(enc)
            except:
                continue
        return raw.decode("utf-8", errors="ignore")
    except zipfile.BadZipFile:
        print("  ZIP 아님. 응답 일부:", res.content[:200])
        return None


def extract_segment_section(doc_text):
    """'연결기준 사업부문별 재무정보' 표 전체를 추출"""
    found = []
    # 핵심 표: 부문별 재무정보 (영업이익, 매출 등이 있는 표)
    anchors = ["연결기준 사업부문별 재무정보", "부문별 주요 재무정보", "사업부문별 재무정보"]
    for anchor in anchors:
        pos = doc_text.find(anchor)
        if pos == -1:
            continue
        # 앵커부터 다음 2500자를 가져와서 표 내용 확인
        chunk = doc_text[pos:pos+5000]
        # TABLE 태그 안의 내용을 텍스트로 정리
        clean = re.sub(r'<[^>]+>', ' | ', chunk)
        clean = re.sub(r'\s*\|\s*(\|\s*)+', ' | ', clean)  # 연속 구분자 정리
        clean = re.sub(r'\s+', ' ', clean).strip()
        found.append(f"=== [{anchor}] ===\n{clean[:4000]}")
        break  # 첫 번째 표만
    return found


def main():
    if not DART_KEY:
        print("DART_API_KEY 없음")
        return

    stock_code = "006400"  # 삼성SDI
    print(f"=== 삼성SDI({stock_code}) 사업부문 정보 추출 테스트 ===\n")

    corp_map = build_corp_map()
    corp_code = corp_map.get(stock_code)
    print(f"corp_code: {corp_code}")

    rcept_no = find_business_report(corp_code, "2025")
    if not rcept_no:
        print("사업보고서 못 찾음")
        return

    print(f"\n공시 원문 다운로드 중... (rcept_no: {rcept_no})")
    doc = download_document(rcept_no)
    if not doc:
        print("원문 다운로드 실패")
        return

    print(f"  문서 길이: {len(doc):,}자\n")

    print("=== '부문' 관련 섹션 ===")
    sections = extract_segment_section(doc)
    if not sections:
        print("부문 관련 키워드를 못 찾음")
    for s in sections:
        print(f"\n{s}")


if __name__ == "__main__":
    main()
