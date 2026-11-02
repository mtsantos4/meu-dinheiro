import re, json, urllib.request, http.cookiejar, html
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def get(url, enc=None, hdr=None):
    h = {"User-Agent": UA, "Accept": "text/html,application/json,*/*", "Accept-Language": "pt-BR,pt;q=0.9"}; h.update(hdr or {})
    with op.open(urllib.request.Request(url, headers=h), timeout=25) as r:
        b = r.read(); return r.status, b.decode(enc or "utf-8", "replace")
def tenta(nome, f):
    try: f()
    except Exception as e: print(nome, "ERRO", e)
def fundamentus(t):
    s, txt = get(f"https://www.fundamentus.com.br/detalhes.php?papel={t}", "iso-8859-1")
    pares = re.findall(r'<td class="label[^"]*">.*?<span class="txt">(.*?)</span>.*?</td>\s*<td class="data[^"]*">\s*(?:<span[^>]*>)?\s*(?:<a[^>]*>)?\s*([^<]*)', txt, re.S)
    print("FUNDAMENTUS", t, s, len(txt), [(html.unescape(a).strip(), html.unescape(b).strip()) for a, b in pares][:80])
for t in ["PETR4", "WEGE3", "MXRF11", "AAPL34", "TAEE11"]:
    tenta("fund " + t, lambda t=t: fundamentus(t))
def inv10(path):
    s, txt = get("https://investidor10.com.br/" + path)
    cards = re.findall(r'<span[^>]*>\s*([A-Z/][^<]{1,40}?)\s*</span>\s*(?:<[^>]+>\s*)*<span[^>]*>\s*([-\d.,%R$ ]+)\s*</span>', txt)
    print("INV10", path, s, len(txt), cards[:40])
    i = txt.find("P/L"); print("INV10 trecho", re.sub(r"\s+", " ", txt[i-300:i+600]) if i > 0 else "sem P/L")
for p in ["acoes/petr4/", "fiis/mxrf11/", "bdrs/aapl34/", "etfs-global/voo/"]:
    tenta("inv10 " + p, lambda p=p: inv10(p))
def yq(sym):
    try: get("https://fc.yahoo.com")
    except Exception as e: pass
    s, crumb = get("https://query1.finance.yahoo.com/v1/test/getcrumb")
    mods = "summaryDetail,defaultKeyStatistics,financialData,price,fundProfile,topHoldings,assetProfile"
    s, txt = get(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules={mods}&crumb={crumb}")
    js = json.loads(txt); r = js["quoteSummary"]["result"][0]
    print("YAHOO", sym, {k: list(v.keys())[:30] for k, v in r.items()})
    sd = r.get("summaryDetail", {}); print("  sd", {k: (v.get("fmt") if isinstance(v, dict) else v) for k, v in sd.items()})
    print("  ks", {k: (v.get("fmt") if isinstance(v, dict) else v) for k, v in r.get("defaultKeyStatistics", {}).items()})
    print("  fd", {k: (v.get("fmt") if isinstance(v, dict) else v) for k, v in r.get("financialData", {}).items()})
for s in ["VOO", "AAPL", "PETR4.SA", "MXRF11.SA"]:
    tenta("yahoo " + s, lambda s=s: yq(s))
