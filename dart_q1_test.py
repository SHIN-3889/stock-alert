# -*- coding: utf-8 -*-
"""과거 3개년 영업이익/매출/영업현금흐름 수집 테스트"""
import os, io, zipfile, requests
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

def get_3yr(corp_code, year):
    """사업보고서(11011) 재무제표에서 당기/전기/전전기 추출"""
    url = f"{DART_BASE}/fnlttSinglAcntAll.json"
    params = {"crtfc_key":DART_KEY,"corp_code":corp_code,"bsns_year":year,"reprt_code":"11011","fs_div":"CFS"}
    data = requests.get(url, params=params, timeout=20).json()
    if data.get("status") != "000":
        print(f"  status: {data.get(status)}")
        return
    items = data.get("list", [])

    # 영업이익, 매출액, 영업활동현금흐름 찾기
    targets = {
        "영업이익": ["영업이익", "영업이익(손실)", "영업손익"],
        "매출액": ["매출액", "수익(매출액)", "영업수익"],
        "영업활동현금흐름": ["영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로 인한 현금흐름"],
    }
    for label, names in targets.items():
        for item in items:
            acct = (item.get("account_nm","") or "").replace(" ","")
            if any(n.replace(" ","") == acct for n in names):
                th = item.get("thstrm_amount","") or "0"
                fr = item.get("frmtrm_amount","") or "0"
                bf = item.get("bfefrmtrm_amount","") or "0"
                def conv(x):
                    try: return int(str(x).replace(",","").strip() or 0)
                    except: return 0
                th_v, fr_v, bf_v = conv(th), conv(fr), conv(bf)
                print(f"  [{label}] ({acct})")
                print(f"    당기: {th_v:,}")
                print(f"    전기: {fr_v:,}")
                print(f"    전전기: {bf_v:,}")
                break
        else:
            print(f"  [{label}] 못 찾음")

cm = build_corp_map()
for stock, name in [("005930","삼성전자"),("267260","HD현대일렉트릭"),("000660","SK하이닉스")]:
    print(f"\n=== {name} (2025 사업보고서 기준 3개년) ===")
    get_3yr(cm.get(stock), "2025")
