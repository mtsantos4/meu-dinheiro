#!/usr/bin/env python3
"""Rotina diária do Meu Dinheiro: busca cotações, dólar e proventos e grava no Supabase.

Fontes (gratuitas, sem IA):
  - Cotações e dólar: Yahoo Finance (ações, FIIs, ETFs, BDRs, EUA e cripto)
  - Proventos B3 (data-com, pagamento, tipo): Status Invest; reserva: B3 oficial
  - Proventos EUA (ex-date, pagamento): Nasdaq; reserva: Yahoo (sem data de pagamento)

Variáveis de ambiente:
  SUPABASE_URL, SUPABASE_SERVICE_KEY  -> grava no banco
  TICKERS="PETR4:acao,MXRF11:fii,VOO:etf_ext,BTC:cripto"  -> modo teste (não lê nem grava no banco)
"""
import base64, datetime as dt, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
HOJE = dt.date.today()
JANELA_DIAS = 2200  # ~6 anos de proventos (para a rentabilidade histórica)
LOG = []
USD = [None]

def log(msg):
    LOG.append(msg); print(msg, flush=True)

def http_json(url, headers=None, data=None, method=None, timeout=25, tentativas=2):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    h.update(headers or {})
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        h.setdefault("Content-Type", "application/json")
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, data=body, headers=h, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = r.read().decode("utf-8", "replace")
                return json.loads(txt) if txt.strip() else None
        except urllib.error.HTTPError as e:
            ultimo = f"HTTP {e.code}"
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:  # noqa
            ultimo = str(e)
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(ultimo)

def safe_id(s):
    return re.sub(r"[^A-Z0-9_\-.~:@+]", "_", s.upper())

def data_br(s):
    """'31/10/2026' ou '2026-10-31T00:00:00' -> '2026-10-31'"""
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2})$", s)
    if m:
        return f"20{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"  # formato EUA mm/dd/yy
    return None

def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip().replace("$", "").replace("R", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def dentro_janela(iso):
    if not iso:
        return False
    try:
        return (HOJE - dt.date.fromisoformat(iso)).days <= JANELA_DIAS
    except ValueError:
        return False

def dia_util_anterior(d):
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d

def tipo_padrao(txt, classe):
    t = (txt or "").lower()
    if "jcp" in t or "juros" in t or "jrs" in t:
        return "jcp"
    if "rend" in t:
        return "rendimento"
    if "amort" in t:
        return "amortizacao"
    if classe == "fii":
        return "rendimento"
    return "dividendo"

# ---------------- Yahoo ----------------
def yahoo_symbol(t, classe, moeda):
    if classe == "cripto":
        return t if "-" in t else f"{t}-BRL"
    if classe in ("etf_ext", "stock_ext") or moeda == "USD":
        return t
    return t if t.endswith(".SA") else f"{t}.SA"

def yahoo_chart(sym, rng="2y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range={rng}&interval=1d&events=div"
    js = http_json(url)
    res = (js.get("chart") or {}).get("result")
    if not res:
        raise RuntimeError(str((js.get("chart") or {}).get("error") or "sem resultado"))
    return res[0]

def yahoo_preco(r):
    m = r["meta"]
    preco = float(m["regularMarketPrice"])
    closes = [c for c in (((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []) if c]
    prev = closes[-2] if len(closes) >= 2 else (m.get("chartPreviousClose") or m.get("previousClose"))
    var = round((preco / prev - 1) * 100, 2) if prev else 0.0
    return preco, var, m.get("currency")

def yahoo_dividendos(r, moeda):
    out = []
    for ev in ((r.get("events") or {}).get("dividends") or {}).values():
        ex = dt.datetime.fromtimestamp(ev["date"], dt.timezone.utc).date()
        dc = dia_util_anterior(ex).isoformat()
        if dentro_janela(dc):
            out.append({"dataCom": dc, "dataPagamento": None, "valor": round(float(ev["amount"]), 8), "tipoTxt": "", "moeda": moeda})
    return out

def dolar():
    try:
        r = yahoo_chart("BRL=X", "5d")
        return round(float(r["meta"]["regularMarketPrice"]), 4), "Yahoo"
    except Exception as e:
        log(f"  dólar Yahoo falhou: {e}")
    js = http_json("https://economia.awesomeapi.com.br/json/last/USD-BRL")
    return round(float(js["USDBRL"]["bid"]), 4), "AwesomeAPI"

# ---------------- Histórico mensal (rentabilidade) ----------------
def yahoo_mensal(sym, rng="10y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range={rng}&interval=1mo"
    js = http_json(url)
    r = ((js.get("chart") or {}).get("result") or [None])[0]
    if not r:
        raise RuntimeError("sem histórico")
    ts = r.get("timestamp") or []
    cl = (((r.get("indicators") or {}).get("quote") or [{}])[0].get("close")) or []
    out = {}
    for t, c in zip(ts, cl):
        if c is None:
            continue
        d = dt.datetime.fromtimestamp(t + 6 * 3600, dt.timezone.utc)  # margem p/ fuso
        out[f"{d.year}-{d.month:02d}"] = round(float(c), 6)
    return out, (r.get("meta") or {}).get("currency")

def bcb_mensal(serie, desde="01/01/2015"):
    js = http_json(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados?formato=json&dataInicial={desde}")
    out = {}
    for x in js or []:
        d = x.get("data", ""); v = num(x.get("valor"))
        m = re.match(r"\d{2}/(\d{2})/(\d{4})", d)
        if m and v is not None:
            out[f"{m.group(2)}-{m.group(1)}"] = v
    return out

def indices_mensais():
    idx, erros = {}, []
    for nome, serie in (("CDI", 4391), ("IPCA", 433)):
        try:
            idx[nome] = bcb_mensal(serie)
        except Exception as e:
            erros.append(f"{nome}: {e}")
    for nome, sym in (("IBOV", "^BVSP"), ("IFIX", "XFIX11.SA"), ("SMLL", "SMAL11.SA"), ("IDIV", "DIVO11.SA"), ("IVVB11", "IVVB11.SA"), ("USDBRL", "BRL=X")):
        try:
            idx[nome], _ = yahoo_mensal(sym)
        except Exception as e:
            erros.append(f"{nome}: {e}")
    return idx, erros

def historico_ativo(t, classe, moeda, usd_hist):
    if classe == "cripto":
        try:
            h, _ = yahoo_mensal(f"{t}-BRL")
            return h, "BRL"
        except Exception:
            h, _ = yahoo_mensal(f"{t}-USD")
            return {m: round(v * usd_hist.get(m, 0), 6) for m, v in h.items() if usd_hist.get(m)}, "BRL"
    h, cur = yahoo_mensal(yahoo_symbol(t, classe, moeda))
    return h, ("USD" if cur == "USD" else "BRL")

# ---------------- Setor / segmento ----------------
def http_texto(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"}), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def setor_b3(ticker):
    raiz = re.match(r"[A-Z0-9]{4}", ticker).group(0)
    base = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/"
    lst = http_json(base + "GetInitialCompanies/" + b3_b64({"language": "pt-br", "pageNumber": 1, "pageSize": 20, "company": raiz}))
    emp = next((x for x in (lst or {}).get("results", []) if x.get("issuingCompany") == raiz), None)
    if not emp:
        raise RuntimeError("empresa não encontrada na B3")
    det = http_json(base + "GetDetail/" + b3_b64({"codeCVM": emp["codeCVM"], "language": "pt-br"}))
    partes = [p.strip() for p in (det.get("industryClassification") or emp.get("segment") or "").split("/") if p.strip()]
    return {"setor": partes[0] if partes else None, "subsetor": partes[1] if len(partes) > 1 else None,
            "segmento": partes[2] if len(partes) > 2 else (emp.get("segment") or None), "nome": det.get("companyName"), "fonte": "B3"}

def setor_fii(ticker):
    t = http_texto(f"https://www.fundsexplorer.com.br/funds/{ticker.lower()}")
    seg = re.search(r'"segmento_atuacao"\s*:\s*"([^"]+)"', t)
    anb = re.search(r'"segmento_ambima"\s*:\s*"([^"]+)"', t)
    if not seg and not anb:
        raise RuntimeError("segmento não encontrado")
    return {"setor": "Fundos imobiliários", "segmento": seg.group(1) if seg else None, "segmentoAnbima": anb.group(1) if anb else None, "fonte": "Funds Explorer"}

def setores_faltando(url, key, ativos, teste):
    ja = set()
    if not teste:
        try:
            ja = {r["id"] for r in (http_json(f"{url}/rest/v1/mercado_docs?col=eq.setores&select=id", headers=sb_headers(key)) or [])}
        except Exception:
            pass
    out = []
    for a in ativos:
        if a["classe"] not in ("acao", "fii", "bdr") or safe_id(a["ticker"]) in ja:
            continue
        try:
            d = setor_fii(a["ticker"]) if a["classe"] == "fii" else setor_b3(a["ticker"])
            out.append({"col": "setores", "id": safe_id(a["ticker"]), "data": {"ticker": a["ticker"], **d}})
        except Exception as e:
            log(f"  setor {a['ticker']}: {e}")
        time.sleep(0.3)
    return out

# ---------------- Status Invest ----------------
SI_PATH = {"acao": "acao", "fii": "fii", "bdr": "bdr", "etf": "etf"}

def statusinvest(ticker, classe):
    caminhos = [SI_PATH.get(classe, "acao")] + [p for p in ("acao", "fii", "bdr", "etf") if p != SI_PATH.get(classe)]
    erro = None
    for p in caminhos:
        url = f"https://statusinvest.com.br/{p}/companytickerprovents?ticker={ticker}&chartProventsType=2"
        try:
            js = http_json(url, headers={"Referer": f"https://statusinvest.com.br/{p}/{ticker.lower()}", "X-Requested-With": "XMLHttpRequest"}, tentativas=1)
        except Exception as e:
            erro = e; continue
        lst = (js or {}).get("assetEarningsModels") or []
        if not lst:
            continue
        out = []
        for x in lst:
            dc = data_br(x.get("ed")); pg = data_br(x.get("pd"))
            if not dc or not dentro_janela(dc):
                continue
            v = num(x.get("v"))
            if not v:
                continue
            out.append({"dataCom": dc, "dataPagamento": pg, "valor": round(v, 8), "tipoTxt": x.get("et") or x.get("etd") or "", "moeda": "BRL"})
        return out
    if erro:
        raise RuntimeError(f"Status Invest: {erro}")
    return []

# ---------------- B3 oficial ----------------
def b3_b64(obj):
    return base64.b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode()

def b3_proventos(ticker, classe):
    raiz = re.match(r"[A-Z]{4}", ticker).group(0)
    if classe == "fii":
        url = "https://sistemaswebb3-listados.b3.com.br/fundsProxy/fundsCall/GetListedSupplementFunds/" + b3_b64({"cnpj": "0", "identifierFund": raiz, "typeFund": 7})
    else:
        url = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/" + b3_b64({"issuingCompany": raiz, "language": "pt-br"})
    js = http_json(url)
    if os.environ.get("DEBUG"):
        print("B3 RAW", ticker, json.dumps(js, ensure_ascii=False)[:3000])
    blocos = js if isinstance(js, list) else [js]
    lst = []
    for b in blocos:
        if isinstance(b, dict):
            lst += b.get("cashDividends") or []
    if classe in ("fii", "etf"):
        sufixo = "CTF"
    elif classe == "bdr":
        sufixo = "BDR"
    else:
        sufixo = {"3": "ACNOR", "4": "ACNPR", "5": "ACNPA", "6": "ACNPB", "11": "CDAM"}.get(ticker[4:], "")
    if sufixo and any(sufixo in (x.get("isinCode") or "") for x in lst):
        lst = [x for x in lst if sufixo in (x.get("isinCode") or "")]
    out = []
    for x in lst:
        dc = data_br(x.get("lastDatePrior") or x.get("lastDatePriorEx") or x.get("dateCom"))
        pg = data_br(x.get("paymentDate"))
        v = num(x.get("rate") or x.get("value"))
        if not dc or not v or not dentro_janela(dc):
            continue
        out.append({"dataCom": dc, "dataPagamento": pg, "valor": round(v, 8), "tipoTxt": x.get("label") or x.get("corporateAction") or "", "moeda": "BRL"})
    return out

# ---------------- Nasdaq (EUA) ----------------
def data_eua(s):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(s or ""))
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None

def nasdaq(ticker, classe):
    out, erro = [], None
    for ac in (["etf", "stocks"] if classe == "etf_ext" else ["stocks", "etf"]):
        url = f"https://api.nasdaq.com/api/quote/{ticker}/dividends?assetclass={ac}"
        try:
            js = http_json(url, headers={"Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}, tentativas=1)
        except Exception as e:
            erro = e; continue
        if os.environ.get("DEBUG"):
            print("NASDAQ RAW", ticker, ac, json.dumps(js, ensure_ascii=False)[:1500])
        rows = (((js or {}).get("data") or {}).get("dividends") or {}).get("rows") or []
        for x in rows:
            ex = data_eua(x.get("exOrEffDate"))
            if not ex:
                continue
            dc = dia_util_anterior(dt.date.fromisoformat(ex)).isoformat()
            v = num(x.get("amount"))
            if not v or not dentro_janela(dc):
                continue
            out.append({"dataCom": dc, "dataPagamento": data_eua(x.get("paymentDate")), "valor": round(v, 8), "tipoTxt": x.get("type") or "", "moeda": "USD"})
        if out:
            return out
    if erro:
        raise RuntimeError(f"Nasdaq: {erro}")
    return out

# ---------------- Supabase ----------------
def sb_headers(key):
    return {"apikey": key, "Authorization": f"Bearer {key}"}

def sb_ativos(url, key):
    rows, start = [], 0
    while True:
        h = sb_headers(key); h["Range"] = f"{start}-{start + 999}"
        lote = http_json(f"{url}/rest/v1/docs?col=eq.ativos&select=data", headers=h)
        rows += lote or []
        if not lote or len(lote) < 1000:
            break
        start += 1000
    vistos = {}
    for r in rows:
        d = r.get("data") or {}
        t = (d.get("ticker") or "").upper().strip()
        if t and t not in vistos:
            vistos[t] = {"ticker": t, "classe": d.get("classe") or "acao", "moeda": d.get("moeda") or "BRL"}
    return list(vistos.values())

def sb_upsert(url, key, linhas):
    h = sb_headers(key); h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    for i in range(0, len(linhas), 500):
        http_json(f"{url}/rest/v1/mercado_docs?on_conflict=col,id", headers=h, data=linhas[i:i + 500], method="POST")

# ---------------- principal ----------------
def processar(a, agora):
    t, classe, moeda = a["ticker"], a["classe"], a["moeda"]
    mercado, provs, fonte_prov, avisos = None, [], None, []
    try:
        try:
            r = yahoo_chart(yahoo_symbol(t, classe, moeda))
            preco, var, cur = yahoo_preco(r)
        except Exception:
            if classe != "cripto":
                raise
            r = yahoo_chart(f"{t}-USD", "5d")
            preco, var, cur = yahoo_preco(r)
            if USD[0]:
                preco, cur = preco * USD[0], "BRL"
        mercado = {"ticker": t, "preco": round(preco, 6), "moeda": "USD" if cur == "USD" else "BRL", "variacao": var, "atualizadoEm": agora, "fonte": "Yahoo Finance"}
    except Exception as e:
        r = None; avisos.append(f"cotação: {e}")
    if classe == "cripto":
        return mercado, [], None, avisos
    if classe in ("etf_ext", "stock_ext") or moeda == "USD":
        try:
            provs, fonte_prov = nasdaq(t, classe), "Nasdaq"
        except Exception as e:
            avisos.append(str(e))
        if not provs and r is not None:
            provs, fonte_prov = yahoo_dividendos(r, "USD"), "Yahoo (pagamento estimado)"
            for p in provs:  # EUA: pagamento costuma sair poucos dias após a data-ex; estimamos +7 dias corridos
                ex = dt.date.fromisoformat(p["dataCom"]) + dt.timedelta(days=1)
                while ex.weekday() >= 5:
                    ex += dt.timedelta(days=1)
                p["dataPagamento"] = (ex + dt.timedelta(days=7)).isoformat()
                p["estimado"] = True
    else:
        try:
            provs, fonte_prov = b3_proventos(t, classe), "B3"
        except Exception as e:
            avisos.append(f"B3: {e}")
        if not provs and classe != "etf":
            try:
                provs, fonte_prov = statusinvest(t, classe), "Status Invest"
            except Exception as e:
                avisos.append(str(e))
        if not provs and r is not None:
            provs, fonte_prov = yahoo_dividendos(r, "BRL"), "Yahoo (sem data de pagamento)"
    return mercado, provs, fonte_prov, avisos

def main():
    url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")
    teste = os.environ.get("TICKERS", "").strip()
    if teste:
        ativos = []
        for item in teste.split(","):
            t, _, c = item.strip().partition(":")
            c = c or "acao"
            ativos.append({"ticker": t.upper(), "classe": c, "moeda": "USD" if c in ("etf_ext", "stock_ext") else "BRL"})
        log(f"MODO TESTE com {len(ativos)} ativos (nada será gravado)")
    else:
        if not url or not key:
            sys.exit("Defina SUPABASE_URL e SUPABASE_SERVICE_KEY (ou TICKERS para testar).")
        ativos = sb_ativos(url, key)
        log(f"{len(ativos)} ativos cadastrados")

    agora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    linhas, ok, erros, n_prov = [], 0, [], 0
    try:
        usd, fonte_usd = dolar()
        USD[0] = usd
        log(f"Dólar: {usd} ({fonte_usd})")
    except Exception as e:
        usd = None; erros.append(f"dólar: {e}"); log(f"Dólar falhou: {e}")

    for a in ativos:
        mercado, provs, fonte_prov, avisos = processar(a, agora)
        if mercado:
            ok += 1
            linhas.append({"col": "mercado", "id": safe_id(a["ticker"]), "data": mercado})
        vistos, iguais = set(), set()
        for p in provs:
            chave = (p["dataCom"], p["dataPagamento"], p["valor"], p["tipoTxt"])
            if chave in iguais:  # registro repetido na fonte
                continue
            iguais.add(chave)
            tipo = tipo_padrao(p["tipoTxt"], a["classe"])
            pid = safe_id(f"{a['ticker']}_{p['dataCom']}_{tipo}")
            if pid in vistos:  # dois proventos do mesmo tipo na mesma data-com
                base = pid
                pid = safe_id(f"{base}_{p['dataPagamento'] or 'X'}")
                if pid in vistos:
                    pid = safe_id(f"{base}_{p['dataPagamento'] or 'X'}_{int(round(p['valor'] * 1e6))}")
                if pid in vistos:
                    continue
            vistos.add(pid)
            linhas.append({"col": "proventos", "id": pid, "data": {
                "ticker": a["ticker"], "tipo": tipo, "dataCom": p["dataCom"], "dataPagamento": p["dataPagamento"],
                "valor": p["valor"], "moeda": p["moeda"], "fonte": fonte_prov, "pagamentoEstimado": bool(p.get("estimado")), "atualizadoEm": agora}})
            n_prov += 1
        recentes = sorted(provs, key=lambda x: x["dataCom"], reverse=True)[:3]
        resumo = "; ".join(f"{p['dataCom']}→{p['dataPagamento'] or '?'} {p['valor']} {tipo_padrao(p['tipoTxt'], a['classe'])}" for p in recentes)
        log(f"{a['ticker']:<8} preço={mercado['preco'] if mercado else '—':<10} proventos={len(provs):<3} fonte={fonte_prov or '—'}  {resumo}" + (f"  AVISOS: {' | '.join(avisos)}" if avisos else ""))
        if not mercado:
            erros.append(a["ticker"])
        time.sleep(0.4)

    # histórico mensal de preços e índices (para a aba Rentabilidade)
    idx, erros_idx = indices_mensais()
    if idx:
        linhas.append({"col": "indices", "id": "mensal", "data": {**idx, "atualizadoEm": agora, "obs": "IFIX, SMLL e IDIV aproximados pelos ETFs XFIX11, SMAL11 e DIVO11"}})
    log(f"Índices: {', '.join(f'{k}={len(v)}' for k, v in idx.items())}" + (f"  ERROS: {erros_idx}" if erros_idx else ""))
    n_hist = 0
    for a in ativos:
        try:
            h, cur = historico_ativo(a["ticker"], a["classe"], a["moeda"], idx.get("USDBRL", {}))
            if h:
                linhas.append({"col": "historico", "id": safe_id(a["ticker"]), "data": {"ticker": a["ticker"], "moeda": cur, "meses": h, "atualizadoEm": agora}})
                n_hist += 1
        except Exception as e:
            log(f"  histórico {a['ticker']}: {e}")
        time.sleep(0.25)
    log(f"Históricos mensais: {n_hist}/{len(ativos)}")

    novos_set = setores_faltando(url, key, ativos, bool(teste))
    linhas += novos_set
    log(f"Setores novos: {len(novos_set)}" + "".join(f"\n  SETOR {l['id']}: {l['data'].get('setor')} / {l['data'].get('subsetor')} / {l['data'].get('segmento')}" for l in novos_set[:12]))

    resumo = f"{ok}/{len(ativos)} cotações, {n_prov} proventos" + (f"; sem cotação: {', '.join(erros)}" if erros else "")
    linhas.append({"col": "config", "id": "mercado", "data": {"usdbrl": usd, "atualizadoEm": agora, "resumo": resumo}})
    log("RESUMO: " + resumo)
    if teste:
        print(json.dumps([l for l in linhas if l["col"] not in ("indices", "historico")][:4], ensure_ascii=False, indent=1))
        for l in linhas:
            if l["col"] == "historico":
                m = l["data"]["meses"]; ks = sorted(m)
                print("HIST", l["id"], l["data"]["moeda"], len(ks), ks[:1], ks[-3:], [m[k] for k in ks[-3:]])
        return
    if usd is None:  # mantém o dólar anterior
        try:
            ant = http_json(f"{url}/rest/v1/mercado_docs?col=eq.config&id=eq.mercado&select=data", headers=sb_headers(key))
            linhas[-1]["data"]["usdbrl"] = (ant or [{}])[0].get("data", {}).get("usdbrl")
        except Exception:
            linhas[-1]["data"].pop("usdbrl")
    sb_upsert(url, key, linhas)
    log(f"Gravado no Supabase: {len(linhas)} registros")

if __name__ == "__main__":
    main()
