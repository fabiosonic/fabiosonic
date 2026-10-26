"""Biblioteca comum do day-trader-b3: relógio de Brasília, calendário e
horários da B3, tickers, dados do Yahoo, arquivos de estado e formatação.

Só biblioteca padrão. Todas as skills importam este módulo:

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
    import b3lib

Horários (Ofício Circular B3 050/2026-VNC e anteriores): o mercado à vista
negocia das 10h00 até 5 minutos antes do call de fechamento. O fim muda com o
horário de verão americano: 16h55 enquanto os EUA estão no horário de verão
(2º domingo de março ao 1º domingo de novembro), 17h55 no resto do ano. Na
Quarta-feira de Cinzas a negociação começa às 13h00. Qualquer dia pode ser
sobrescrito em config.json ("sessoes": {"AAAA-MM-DD": ["10:00", "16:55"]}).

Feriados: os nacionais fixos, os móveis (Carnaval, Sexta-feira Santa, Corpus
Christi) e 24/12 e 31/12, sem pregão. 2026 confere com o Ofício Circular
041/2026-VNC; outros anos são calculados e devem ser conferidos no calendário
que a B3 publica no fim do ano anterior.
"""

import datetime
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request

BRT = datetime.timezone(datetime.timedelta(hours=-3))  # sem horário de verão desde 2019
EPOCH = datetime.datetime(1970, 1, 1)
UA = "Mozilla/5.0 (compatible; day-trader-b3/1.0)"
YAHOO_HOSTS = ("query2", "query1")
PAUSA = 0.4        # segundos entre requisições aos endpoints gratuitos
ESPERA_429 = 5.0   # segundos antes da única nova tentativa após HTTP 429

ABERTURA = datetime.time(10, 0)
ABERTURA_CINZAS = datetime.time(13, 0)
FIM_VERAO_EUA = datetime.time(16, 55)
FIM_INVERNO_EUA = datetime.time(17, 55)
CALENDARIO_OFICIAL = {2026: "Ofício Circular B3 041/2026-VNC"}

PASTA = os.environ.get("B3_DIR", "trader-b3")

DEFAULTS = {
    "orcamento": None,
    "reserva_caixa_pct": 10,
    "max_posicao_pct": 75,
    "max_ordem": 20000,
    "min_ordem": 50,
    "max_perda_por_operacao": 100,
    "max_perda_diaria": 300,
    "max_operacoes_dia": 3,
    "max_ordens_dia": 10,
    "min_risco_retorno": 1.0,
    "exigir_stop": True,
    "sem_entradas_antes": "10:15",
    "sem_entradas_ultimos_min": 40,
    "zerar_min_antes_fechamento": 10,
    "lote_padrao": 100,
    "permitir_fracionario": True,
    "custos_pct": 0.03,
    "corretagem_por_ordem": 0.0,
    "simulacao": True,
    "bloqueados": [],
    "permitir_opcoes": False,
    "permitir_vendido": False,
    "permitir_alavancagem": False,
    "tipos": {},
    "sessoes": {},
    # swing trade (posições de vários pregões, compradas ou vendidas)
    "swing_prazo_pregoes": 15,
    "swing_max_posicoes": 5,
    "aluguel_taxa_aa_pct": 2.0,
    "garantia_vendido_pct": 100,
    "max_exposicao_vendida_pct": 50,
    "vendido_somente_lote": True,
    "folga_stop_pct": 0.5,
}


class B3Erro(Exception):
    """Erro com mensagem simples para o usuário."""


# ---------------------------------------------------------------- relógio

def agora_utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)


def para_brt(utc):
    """datetime UTC ingênuo -> horário de Brasília ingênuo."""
    return utc - datetime.timedelta(hours=3)


def para_utc(brt):
    return brt + datetime.timedelta(hours=3)


def ts_para_brt(ts):
    return para_brt(EPOCH + datetime.timedelta(seconds=int(ts)))


def brt_para_ts(brt):
    return int((para_utc(brt) - EPOCH).total_seconds())


def ler_agora(texto):
    """--now "AAAA-MM-DD HH:MM" (Brasília) -> UTC ingênuo. Vazio = agora."""
    if not texto:
        return agora_utc()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return para_utc(datetime.datetime.strptime(texto.strip(), fmt))
        except ValueError:
            pass
    raise B3Erro("--now espera \"AAAA-MM-DD HH:MM\" no horário de Brasília (recebi %r)" % texto)


def ler_hhmm(texto, nome="horário"):
    m = re.match(r"^\s*([01]?\d|2[0-3]):([0-5]\d)\s*$", str(texto or ""))
    if not m:
        raise B3Erro("%s espera HH:MM (recebi %r)" % (nome, texto))
    return datetime.time(int(m.group(1)), int(m.group(2)))


def hm(t):
    return t.strftime("%H:%M")


def mais_min(dia, t, minutos):
    return (datetime.datetime.combine(dia, t) + datetime.timedelta(minutes=minutos)).time()


# ---------------------------------------------------------------- calendário

def pascoa(ano):
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return datetime.date(ano, mes, dia)


def feriados(ano):
    """{data: nome} dos dias sem pregão na B3 que caem em dia útil ou não."""
    p = pascoa(ano)
    d = datetime.date
    dias = {
        d(ano, 1, 1): "Confraternização Universal",
        p - datetime.timedelta(days=48): "Carnaval",
        p - datetime.timedelta(days=47): "Carnaval",
        p - datetime.timedelta(days=2): "Sexta-feira Santa",
        d(ano, 4, 21): "Tiradentes",
        d(ano, 5, 1): "Dia do Trabalho",
        p + datetime.timedelta(days=60): "Corpus Christi",
        d(ano, 9, 7): "Independência do Brasil",
        d(ano, 10, 12): "Nossa Senhora Aparecida",
        d(ano, 11, 2): "Finados",
        d(ano, 11, 15): "Proclamação da República",
        d(ano, 11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
        d(ano, 12, 24): "Véspera de Natal (sem pregão)",
        d(ano, 12, 25): "Natal",
        d(ano, 12, 31): "Último dia do ano (sem pregão)",
    }
    return dias


def quarta_de_cinzas(ano):
    return pascoa(ano) - datetime.timedelta(days=46)


def _domingo(ano, mes, n):
    dia = datetime.date(ano, mes, 1)
    dia += datetime.timedelta(days=(6 - dia.weekday()) % 7)
    return dia + datetime.timedelta(weeks=n - 1)


def verao_eua(dia):
    """True se os EUA estão no horário de verão nessa data."""
    return _domingo(dia.year, 3, 2) <= dia < _domingo(dia.year, 11, 1)


def dia_de_pregao(dia, cfg=None):
    """(True, "") ou (False, motivo)."""
    especial = ((cfg or {}).get("sessoes") or {}).get(dia.isoformat())
    if especial is not None:
        return (True, "") if especial else (False, "sem pregão (config.json)")
    if dia.weekday() >= 5:
        return False, "fim de semana"
    nome = feriados(dia.year).get(dia)
    if nome:
        return False, "feriado: " + nome
    return True, ""


def sessao(dia, cfg=None):
    """(abertura, fim da negociação contínua) do mercado à vista, ou None."""
    ok, _ = dia_de_pregao(dia, cfg)
    if not ok:
        return None
    especial = ((cfg or {}).get("sessoes") or {}).get(dia.isoformat())
    if especial:
        return ler_hhmm(especial[0], "sessoes"), ler_hhmm(especial[1], "sessoes")
    abre = ABERTURA_CINZAS if dia == quarta_de_cinzas(dia.year) else ABERTURA
    return abre, (FIM_VERAO_EUA if verao_eua(dia) else FIM_INVERNO_EUA)


def aviso_calendario(dia):
    """Texto de alerta quando o ano não tem calendário oficial conferido."""
    if dia.year in CALENDARIO_OFICIAL:
        return None
    return ("o calendário de %d foi calculado (feriados nacionais e móveis); confira o ofício "
            "de feriados da B3 para esse ano" % dia.year)


def proximo_pregao(dia, cfg=None):
    d = dia + datetime.timedelta(days=1)
    while not dia_de_pregao(d, cfg)[0]:
        d += datetime.timedelta(days=1)
    return d


def pregoes_anteriores(hoje, n, cfg=None):
    """Os últimos n pregões até hoje (inclusive), do mais recente para o mais antigo."""
    out, d = [], hoje
    while len(out) < n:
        if dia_de_pregao(d, cfg)[0]:
            out.append(d)
        d -= datetime.timedelta(days=1)
    return out


def janela_entradas(dia, cfg):
    """(primeiro horário, último horário) para novas entradas e o horário de zerar."""
    s = sessao(dia, cfg)
    if s is None:
        return None
    abre, fecha = s
    antes = max(ler_hhmm(cfg["sem_entradas_antes"], "sem_entradas_antes"), abre)
    depois = mais_min(dia, fecha, -int(cfg["sem_entradas_ultimos_min"]))
    zerar = mais_min(dia, fecha, -int(cfg["zerar_min_antes_fechamento"]))
    return antes, depois, zerar


def janela_swing(dia, cfg):
    """(primeiro, último) horário para entradas de swing: o pregão contínuo inteiro."""
    s = sessao(dia, cfg)
    return None if s is None else (s[0], s[1])


def pregoes_a_frente(dia, n, cfg=None):
    """O n-ésimo pregão depois de `dia` (n=0 devolve o próprio dia, se for pregão)."""
    d = dia
    if n <= 0:
        return d if dia_de_pregao(d, cfg)[0] else proximo_pregao(d, cfg)
    for _ in range(n):
        d = proximo_pregao(d, cfg)
    return d


def pregoes_entre(inicio, fim, cfg=None):
    """Quantos pregões há depois de `inicio` até `fim` (inclusive)."""
    n, d = 0, inicio
    while d < fim:
        d = proximo_pregao(d, cfg)
        if d <= fim:
            n += 1
    return n


def sinal_lado(lado):
    """+1 para compra (comprado), -1 para venda (vendido)."""
    if lado not in ("compra", "venda"):
        raise B3Erro("lado precisa ser compra ou venda (recebi %r)" % lado)
    return 1 if lado == "compra" else -1


# ---------------------------------------------------------------- tickers

TICKER = re.compile(r"^([A-Z0-9]{3}[A-Z])(\d{1,2})(F?)$")
OPCAO = re.compile(r"^[A-Z0-9]{4}[A-X]\d{2,3}[A-Z]?$")


def normalizar(sym):
    s = str(sym or "").strip().upper()
    if s.endswith(".SA"):
        s = s[:-3]
    return s


def valido(sym):
    return bool(TICKER.match(normalizar(sym)))


def sem_fracionario(sym):
    """PETR4F -> PETR4 (os dados do Yahoo são do lote padrão)."""
    s = normalizar(sym)
    m = TICKER.match(s)
    return m.group(1) + m.group(2) if m else s


def yahoo(sym):
    return sem_fracionario(sym) + ".SA"


def tipo_ativo(sym, cfg=None):
    """ACAO, BDR, FII, ETF ou UNIT conforme config "tipos" e o número do código.
    Final 11 é ambíguo (unit, ETF ou FII): sem "tipos" no config devolve None."""
    s = sem_fracionario(sym)
    mapa = {normalizar(k): str(v).upper() for k, v in ((cfg or {}).get("tipos") or {}).items()}
    if s in mapa:
        return mapa[s]
    m = TICKER.match(s)
    if not m:
        return None
    n = int(m.group(2))
    if 3 <= n <= 8:
        return "ACAO"
    if n in (31, 32, 33, 34, 35, 39):
        return "BDR"
    return None


# ---------------------------------------------------------------- arquivos

def caminho(*partes):
    return os.path.join(PASTA, *partes)


def ler_json(path, padrao=None, obrigatorio=False, o_que="arquivo"):
    if not os.path.exists(path):
        if obrigatorio:
            raise B3Erro("não encontrei %s (%s)" % (o_que, path))
        return padrao
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except ValueError as e:
        raise B3Erro("%s não é um JSON válido: %s" % (path, e))


def gravar_json(path, doc):
    pasta = os.path.dirname(path)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
    os.replace(tmp, path)


def ler_config(path=None):
    cfg = dict(DEFAULTS)
    cfg.update(ler_json(path or caminho("config.json"), {}) or {})
    return cfg


def ler_texto(path):
    with open(path, "rb") as f:
        data = f.read()
    if path.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8")


# ---------------------------------------------------------------- rede

def http_get(url, timeout=30, headers=None):
    req = urllib.request.Request(url, headers=dict({"User-Agent": UA}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def yahoo_get(path):
    """GET em query2 e, em 429 ou 5xx, em query1; uma nova tentativa após 429."""
    ultimo = None
    for tentativa in range(2):
        for host in YAHOO_HOSTS:
            try:
                time.sleep(PAUSA)
                return http_get("https://%s.finance.yahoo.com%s" % (host, path)).decode("utf-8")
            except urllib.error.HTTPError as e:
                ultimo = "HTTP %d" % e.code
                if e.code == 404:
                    raise B3Erro("o Yahoo não conhece esse ativo (%s)" % path)
                if e.code != 429 and e.code < 500:
                    raise B3Erro("o Yahoo respondeu %s" % ultimo)
            except (urllib.error.URLError, OSError) as e:
                ultimo = str(e)
        time.sleep(ESPERA_429)
    raise B3Erro("o Yahoo não respondeu (%s)" % ultimo)


def chart_path(sym, rng, interval):
    return "/v8/finance/chart/%s?range=%s&interval=%s&includePrePost=false" % (yahoo(sym), rng, interval)


def ler_chart(texto, sym=""):
    """JSON do v8 chart -> {"symbol", "meta", "bars": [{t,o,h,l,c,v}]} (sem candles vazios)."""
    doc = json.loads(texto) if isinstance(texto, str) else texto
    chart = (doc or {}).get("chart") or {}
    if chart.get("error"):
        raise B3Erro("Yahoo: %s" % (chart["error"].get("description") or chart["error"]))
    res = (chart.get("result") or [None])[0]
    if not res:
        raise B3Erro("o Yahoo não mandou dados para %s" % sym)
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    bars = []
    for i, t in enumerate(res.get("timestamp") or []):
        c = (q.get("close") or [None])[i] if q.get("close") else None
        if c is None:
            continue
        def g(k, padrao):
            v = (q.get(k) or [None] * (i + 1))[i]
            return float(v) if v is not None else padrao
        bars.append({"t": int(t), "o": g("open", float(c)), "h": g("high", float(c)),
                     "l": g("low", float(c)), "c": float(c), "v": int(g("volume", 0) or 0)})
    meta = res.get("meta") or {}
    return {"symbol": normalizar(meta.get("symbol") or sym), "meta": meta, "bars": bars,
            "data_time": meta.get("regularMarketTime")}


def arquivo_offline(path, sym):
    """--offline: um arquivo ou uma pasta com <TICKER>.json(.gz)."""
    if os.path.isdir(path):
        base = sem_fracionario(sym)
        for nome in (base, base + ".SA", base.lower()):
            for ext in (".json", ".json.gz"):
                p = os.path.join(path, nome + ext)
                if os.path.exists(p):
                    return p
        raise B3Erro("não há %s.json em %s" % (base, path))
    return path


def obter_chart(sym, rng="1d", interval="5m", offline=None):
    if offline:
        return ler_chart(ler_texto(arquivo_offline(offline, sym)), sym)
    return ler_chart(yahoo_get(chart_path(sym, rng, interval)), sym)


def candles_do_dia(chart, dia, passo=300, cfg=None):
    """{slot: candle} da sessão regular de `dia` na grade do intervalo."""
    s = sessao(dia, cfg)
    if s is None:
        return {}
    abre = datetime.datetime.combine(dia, s[0])
    fecha = datetime.datetime.combine(dia, s[1])
    out = {}
    for b in chart["bars"]:
        if b["t"] % passo:
            continue  # o tick ao vivo fora da grade não é candle
        local = ts_para_brt(b["t"])
        if local.date() != dia or not (abre <= local < fecha):
            continue
        slot = int((local - abre).total_seconds()) // passo
        out[slot] = dict(b, local=local, fim=local + datetime.timedelta(seconds=passo), slot=slot)
    return out


def candles_por_sessao(chart, cfg=None, passo=300):
    """{data: [candles em ordem]} de todas as sessões no gráfico."""
    datas = sorted({ts_para_brt(b["t"]).date() for b in chart["bars"]})
    out = {}
    for d in datas:
        c = candles_do_dia(chart, d, passo, cfg)
        if c:
            out[d] = [c[k] for k in sorted(c)]
    return out


def n_candles(dia, passo=300, cfg=None):
    s = sessao(dia, cfg)
    if s is None:
        return 0
    delta = datetime.datetime.combine(dia, s[1]) - datetime.datetime.combine(dia, s[0])
    return int(delta.total_seconds()) // passo


# ---------------------------------------------------------------- formatação

def reais(x, casas=2):
    """1234.5 -> "R$ 1.234,50"."""
    if x is None:
        return "-"
    s = ("{:,.%df}" % casas).format(abs(float(x)))
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-R$ " if float(x) < 0 else "R$ ") + s


def num(x, casas=2):
    if x is None:
        return "-"
    s = ("{:,.%df}" % casas).format(float(x))
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, casas=2):
    return "-" if x is None else num(x, casas) + "%"


def centavos(x):
    return round(float(x) + 1e-9, 2)
