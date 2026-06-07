# -*- coding: utf-8 -*-
"""2026년 1분기보고서 조회 가능 여부 + 부문정보 유무 테스트"""
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
print(f"삼성SDI corp_code: {corp_code}")

# 1) 2026년 1분기 재무제표 조회 시도
print("\n=== 2026년 1분기 재무제표(11013) 조회 ===")
url = f"{DART_BASE}/fnlttSinglAcntAll.json"
for reprt, name in [("11013","1분기"),("11012","반기"),("11014","3분기")]:
    params = {"crtfc_key":DART_KEY,"corp_code":corp_code,"bsns_year":"2026","reprt_code":reprt,"fs_div":"CFS"}
    res = requests.get(url, params=params, timeout=15)
    data = res.json()
    print(f"  2026 {name}({reprt}): status={data.get('status')} / {data.get('message','')[:30]}")

# 2) 최근 공시 목록 확인 (어떤 보고서들이 올라와 있나)
print("\n=== 최근 정기공시 목록 ===")
url2 = f"{DART_BASE}/list.json"
params2 = {"crtfc_key":DART_KEY,"corp_code":corp_code,"bgn_de":"20260101","end_de":"20260630","pblntf_ty":"A","page_count":20}
res2 = requests.get(url2, params=params2, timeout=15)
data2 = res2.json()
if data2.get("status")=="000":
    for r in data2.get("list",[]):
        print(f"  {r['report_nm']} ({r['rcept_dt']}) rcept_no={r['rcept_no']}")
else:
    print(f"  status={data2.get('status')}")
