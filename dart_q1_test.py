# -*- coding: utf-8 -*-
"""삼성전자/현대모비스 부문 표 추출 검증 (새 로직)"""
import os, io, re, zipfile, requests
import xml.etree.ElementTree as ET

DART_KEY  = os.environ.get("DART_API_KEY", "")
DART_BASE = "https://opendart.fss.or.kr/api"

def build_corp_map():
    res = requests.get(f"{DART_BASE}/corpCode.xml", params={"crtfc_key": DART_KEY}, timeout=30)
    z = zipfile.ZipFile(io.BytesIO(res.content))
    root = ET.fromstring(z.read("CORPCODE.xml"))
    m = {}
    for item in root.findall("list"):
        sc = item.findtext("stock_code","").strip(); cc = item.findtext("corp_code","").strip()
        if sc: m[sc]=cc
    return m

def find_report(corp_code, year):
    data = requests.get(f"{DART_BASE}/list.json", params={"crtfc_key":DART_KEY,"corp_code":corp_code,"bgn_de":f"{year}0101","end_de":f"{int(year)+1}0630","pblntf_ty":"A","page_count":100}, timeout=15).json()
    for kw in ["사업보고서","반기보고서","분기보고서"]:
        for r in data.get("list",[]):
            if kw in r.get("report_nm",""): return r["rcept_no"]
    return None

def get_doc(rcept_no):
    res = requests.get(f"{DART_BASE}/document.xml", params={"crtfc_key":DART_KEY,"rcept_no":rcept_no}, timeout=60)
    z = zipfile.ZipFile(io.BytesIO(res.content))
    biggest = max(z.namelist(), key=lambda n: z.getinfo(n).file_size)
    raw = z.read(biggest)
    for enc in ["utf-8","euc-kr","cp949"]:
        try: return raw.decode(enc)
        except: pass
    return raw.decode("utf-8", errors="ignore")

def extract(doc_text):
    anchors = ["연결기준 사업부문별 재무정보","부문별 주요 재무정보","사업부문별 재무정보","부문별 재무정보","사업부문별 요약 재무","영업부문별 정보"]
    candidates = []
    for anchor in anchors:
        start = 0
        while True:
            pos = doc_text.find(anchor, start)
            if pos == -1: break
            chunk = doc_text[pos:pos+5000]
            clean = re.sub(r"<[^>]+>", " | ", chunk)
            clean = re.sub(r"\s*\|\s*(\|\s*)+", " | ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            has_profit = ("영업이익" in clean) or ("영업손익" in clean) or ("영업손실" in clean)
            digits = re.findall(r"[\d,]{4,}", clean)
            if has_profit and len(digits) >= 8:
                candidates.append((len(digits), clean[:1500]))
            start = pos + 1
    if candidates:
        candidates.sort(key=lambda x:x[0], reverse=True)
        return candidates[0][1]
    return "SINGLE_SEGMENT"

cm = build_corp_map()
for stock, name in [("005930","삼성전자"),("012330","현대모비스")]:
    print(f"\n=== {name} ===")
    rc = find_report(cm.get(stock), "2025")
    doc = get_doc(rc)
    result = extract(doc)
    print(result[:1200])
