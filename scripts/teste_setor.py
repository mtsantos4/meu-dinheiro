import json, base64, urllib.request, re
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36","Accept":"*/*"}
def get(u, raw=False):
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=25) as r:
        t=r.read().decode("utf-8","replace"); return t if raw else json.loads(t)
b=lambda o: base64.b64encode(json.dumps(o,separators=(",",":")).encode()).decode()
B="https://sistemaswebb3-listados.b3.com.br/"
for nome,u in [
 ("B3 GetDetail BBAS", B+"listedCompaniesProxy/CompanyCall/GetDetail/"+b({"codeCVM":"1023","language":"pt-br"})),
 ("B3 Initial ITSA", B+"listedCompaniesProxy/CompanyCall/GetInitialCompanies/"+b({"language":"pt-br","pageNumber":1,"pageSize":5,"company":"ITSA"})),
 ("B3 FII detail MXRF", B+"fundsProxy/fundsCall/GetDetailFundSIG/"+b({"typeFund":7,"cnpj":"0","identifierFund":"MXRF"})),
 ("B3 FII list", B+"fundsProxy/fundsCall/GetListFundDownload/"+b({"language":"pt-br","typeFund":7,"pageNumber":1,"pageSize":5,"keyword":"MXRF"})),
]:
    try: d=get(u); print(nome, json.dumps(d,ensure_ascii=False)[:900])
    except Exception as e: print(nome,"ERRO",e)
for nome,u,pat in [
 ("FundsExplorer MXRF11","https://www.fundsexplorer.com.br/funds/mxrf11", r"[Ss]egmento.{0,200}"),
 ("Investidor10 MXRF11","https://investidor10.com.br/fiis/mxrf11/", r"[Ss]egmento.{0,200}"),
 ("Investidor10 BBAS3","https://investidor10.com.br/acoes/bbas3/", r"[Ss]etor.{0,200}"),
 ("Statusinvest BBAS3","https://statusinvest.com.br/acoes/bbas3", r"[Ss]etor.{0,200}"),
]:
    try:
        t=get(u,True); m=re.findall(pat,t,re.S)[:3]; print(nome,"OK", len(t), [re.sub(r"<[^>]+>"," ",x)[:160] for x in m])
    except Exception as e: print(nome,"ERRO",e)
