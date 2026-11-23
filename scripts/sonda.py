import re, urllib.request, html
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def get(url):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"}), timeout=30)
    return r.status, r.read().decode("utf-8", "replace")
for t, path in [("CPFE3", "acoes/cpfe3/"), ("MXRF11", "fiis/mxrf11/")]:
    try:
        s, txt = get("https://investidor10.com.br/" + path)
        print(t, s, len(txt))
        for m in re.finditer(r"<table[^>]*>.*?</table>", txt, re.S):
            tb = m.group(0)
            if "Data Com" in tb or "data com" in tb.lower():
                rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)
                print(" TABELA linhas", len(rows), re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "|", tb)))[:1500])
        for k in ["dividends", "api/", "proventos", "chart-dividends"]:
            for mm in list(re.finditer(k, txt))[:3]:
                print(" KW", k, re.sub(r"\s+", " ", txt[max(0, mm.start()-150):mm.start()+200]))
    except Exception as e:
        print(t, "ERRO", e)
