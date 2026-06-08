# -*- coding: utf-8 -*-
"""삼성전자 부문 정보가 어떻게 추출되는지 확인"""
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

def find_report(corp_code, year):
    url = f"{DART_BASE}/list.json"
    params = {"crtfc_key":DART_KEY,"corp_code":corp_code,"bgn_de":f"{year}0101","end_de":f"{int(year)+1}0630","pblntf_ty":"A","page_count":100}
    data = requests.get(url, params=params, timeout=15).json()
    for kw in ["사업보고서","반기보고서","분기보고서"]:
        for r in data.get("list",[]):
            if kw in r.get("report_nm",""):
                return r["rcept_no"], r["report_nm"]
    return None, None

def get_doc(rcept_no):
    res = requests.get(f"{DART_BASE}/document.xml", params={"crtfc_key":DART_KEY,"rcept_no":rcept_no}, timeout=60)
    z = zipfile.ZipFile(io.BytesIO(res.content))
    biggest = max(z.namelist(), key=lambda n: z.getinfo(n).file_size)
    raw = z.read(biggest)
    for enc in ["utf-8","euc-kr","cp949"]:
        try: return raw.decode(enc)
        except: pass
    return raw.decode("utf-8", errors="ignore")

corp_code = build_corp_map().get("005930")
rcept_no, rpt = find_report(corp_code, "2025")
print(f"삼성전자 보고서: {rpt} / {rcept_no}")
doc = get_doc(rcept_no)
print(f"문서 길이: {len(doc):,}")

# 단일부문 마커 체크
markers = ["지배적 단일 사업부문", "단일 사업부문으로", "부문별 기재를 생략", "단일 영업부문"]
for mk in markers:
    if mk in doc:
        print(f"⚠️ 단일부문 마커 발견: {mk}")

# 부문 표 앵커 체크
anchors = ["연결기준 사업부문별 재무정보","부문별 주요 재무정보","사업부문별 재무정보","사업부문별 요약 재무","부문별 재무정보","영업부문별 정보"]
for a in anchors:
    pos = doc.find(a)
    if pos != -1:
        chunk = doc[pos:pos+3000]
        clean = re.sub(r"<[^>]+>", " | ", chunk)
        clean = re.sub(r"\s+", " ", clean).strip()
        digits = re.findall(r"[\d,]{4,}", clean)
        has_profit = "영업" in clean and ("이익" in clean or "손익" in clean or "손실" in clean)
        print(f"\n앵커 [{a}] 발견 (위치 {pos})")
        print(f"  영업이익단어: {has_profit}, 숫자그룹: {len(digits)}개")
        print(f"  내용: {clean[:600]}")
        break
