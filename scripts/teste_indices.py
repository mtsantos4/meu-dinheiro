import json, urllib.request, urllib.parse
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36","Accept":"application/json"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=25) as r: return json.load(r)
for nome,u in [("CDI mensal 4391","https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados?formato=json&dataInicial=01/01/2024"),
               ("IPCA 433","https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2024")]:
    try: d=get(u); print(nome, len(d), d[:2], d[-2:])
    except Exception as e: print(nome,"ERRO",e)
for sym in ["^BVSP","IFIX.SA","SMAL11.SA","DIVO11.SA","IVVB11.SA","BRL=X","PETR4.SA","VOO","BTC-BRL","BTC-USD","XFIX11.SA"]:
    try:
        d=get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=5y&interval=1mo&events=div")
        r=d["chart"]["result"][0]; ts=r.get("timestamp") or []; cl=r["indicators"]["quote"][0]["close"]; adj=(r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
        print(sym, len(ts), "ultimos", list(zip(ts[-2:], cl[-2:])), "adj" if adj else "")
    except Exception as e: print(sym,"ERRO",e)
