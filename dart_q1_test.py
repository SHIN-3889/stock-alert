# -*- coding: utf-8 -*-
"""2026년 1분기보고서 상세 테스트
1. 재무제표 계정과목 확인 (영업이익 잡히는지)
2. 공시 원문에 부문 정보 있는지
"""
import os, io, re, zipfile, requests
import xml.etree.ElementTree as ET

DART_KEY  = os.environ.get("DART_API_KEY", "")
DART_BASE = "https://opendart.fss.or.kr/api"

def build_corp_map():
    url = f"{DART_BASE}/corpCode.xml"
    res = requests.get(url, params={"crtfc_key": DART_KEY}, timeout=30)
    z = zipfile.ZipFile(io.BytesIO(res.content))
    root = ET.fromstring(z.read("CORPCODE.xml"))
    m = {}
    for item in root.findall("list"):
        sc = item.findtext("stock_code", "").strip()
        cc = item.findtext("corp_code", "").strip()
        if sc: m[sc] = cc
    return m

corp_code = build_corp_map().get("006400")

# 1) 2026년 1분기 재무제표 계정과목 확인
print("=== 2026년 1분기 재무제표 주요 계정 ===")
url = f"{DART_BASE}/fnlttSinglAcntAll.json"
params = {"crtfc_key":DART_KEY,"corp_code":corp_code,"bsns_year":"2026","reprt_code":"11013","fs_div":"CFS"}
res = requests.get(url, params=params, timeout=15)
data = res.json()
if data.get("status") == "000":
    items = data.get("list", [])
    print(f"  총 항목수: {len(items)}")
    # 영업이익, 매출액, 감가상각 관련 항목만 출력
    keywords = ["영업", "매출", "감가", "OperatingIncome", "Revenue"]
    for item in items:
        nm = item.get("account_nm","")
        aid = item.get("account_id","")
        amt = item.get("thstrm_amount","")
        if any(kw in nm or kw in aid for kw in keywords):
            print(f"  [{aid}] {nm}: {amt}")
else:
    print(f"  실패: {data.get('message')}")

# 2) 분기보고서 원문에 부문 정보 있는지
print("\n=== 분기보고서 원문 부문 정보 확인 ===")
rcept_no = "20260515002408"
url2 = f"{DART_BASE}/document.xml"
res2 = requests.get(url2, params={"crtfc_key":DART_KEY,"rcept_no":rcept_no}, timeout=60)
try:
    z = zipfile.ZipFile(io.BytesIO(res2.content))
    names = z.namelist()
    biggest = max(names, key=lambda n: z.getinfo(n).file_size)
    raw = z.read(biggest)
    doc = raw.decode("utf-8", errors="ignore")
    print(f"  문서 길이: {len(doc):,}자")
    
    anchors = ["연결기준 사업부문별 재무정보", "부문별 주요 재무정보", "사업부문별 재무정보", "부문별 재무정보"]
    for anchor in anchors:
        pos = doc.find(anchor)
        if pos != -1:
            chunk = doc[pos:pos+3000]
            clean = re.sub(r'<[^>]+>', ' | ', chunk)
            clean = re.sub(r'\s+', ' ', clean).strip()
            print(f"\n  발견: [{anchor}]")
            print(f"  {clean[:1000]}")
            break
    else:
        print("  부문별 재무정보 표 없음 (분기보고서 생략)")
        # 어떤 섹션이 있는지 확인
        for kw in ["부문", "사업부"]:
            idx = doc.find(kw)
            if idx != -1:
                snippet = re.sub(r'<[^>]+>', ' ', doc[idx:idx+200])
                snippet = re.sub(r'\s+', ' ', snippet).strip()
                print(f"  [{kw}] {snippet[:150]}")
except Exception as e:
    print(f"  오류: {e}")
