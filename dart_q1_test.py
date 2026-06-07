# -*- coding: utf-8 -*-
"""SK하이닉스/삼성전자 분기보고서에서 부문 키워드 찾기"""
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

def find_latest_rcept(corp_code):
    url = f"{DART_BASE}/list.json"
    params = {"crtfc_key":DART_KEY,"corp_code":corp_code,
              "bgn_de":"20260101","end_de":"20260630","pblntf_ty":"A","page_count":10}
    res = requests.get(url, params=params, timeout=15)
    data = res.json()
    for keyword in ["분기보고서", "반기보고서", "사업보고서"]:
        for r in data.get("list", []):
            if keyword in r.get("report_nm", ""):
                return r["rcept_no"], r["report_nm"]
    return None, None

def get_doc(rcept_no):
    res = requests.get(f"{DART_BASE}/document.xml",
                       params={"crtfc_key":DART_KEY,"rcept_no":rcept_no}, timeout=60)
    z = zipfile.ZipFile(io.BytesIO(res.content))
    biggest = max(z.namelist(), key=lambda n: z.getinfo(n).file_size)
    raw = z.read(biggest)
    for enc in ["utf-8","euc-kr","cp949"]:
        try: return raw.decode(enc)
        except: pass
    return raw.decode("utf-8", errors="ignore")

corp_map = build_corp_map()

for stock, name in [("000660","SK하이닉스"), ("005930","삼성전자"), ("012330","현대모비스")]:
    print(f"\n=== {name} ===")
    corp_code = corp_map.get(stock)
    rcept_no, rpt_nm = find_latest_rcept(corp_code)
    print(f"  보고서: {rpt_nm} / {rcept_no}")
    doc = get_doc(rcept_no)
    
    # 부문 관련 키워드 모두 검색
    keywords = ["부문별 재무정보", "사업부문별", "영업부문", "세그먼트",
                "Segment", "부문 정보", "부문별 정보", "영업 부문"]
    for kw in keywords:
        pos = doc.find(kw)
        if pos != -1:
            chunk = doc[pos:pos+500]
            clean = re.sub(r'<[^>]+>', ' | ', chunk)
            clean = re.sub(r'\s+', ' ', clean).strip()
            print(f"  발견 [{kw}]: {clean[:200]}")
            break
    else:
        print("  ⚠️ 부문 관련 키워드 없음")
