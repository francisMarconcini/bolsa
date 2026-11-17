"""
Maiores altas e baixas da B3 e dos EUA - interface web (Flask).

Rodar:
    pip install -r requirements.txt
    python app.py
Abrir: http://localhost:5000
"""

import math
import re
import time

import yfinance as yf
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

TOP_N = 20

# ------------------------------------------------------------ universos ----
# Edite à vontade. Tickers que não existirem no Yahoo são ignorados.
TICKERS_B3 = [
    "PETR4", "PETR3", "VALE3", "ITUB4", "BBDC4", "BBDC3", "BBAS3", "B3SA3",
    "ABEV3", "WEGE3", "RENT3", "SUZB3", "JBSS3", "ELET3", "ELET6", "EQTL3",
    "RADL3", "RAIL3", "LREN3", "GGBR4", "CSNA3", "USIM5", "CMIG4", "CPLE6",
    "SBSP3", "VIVT3", "TIMS3", "HAPV3", "RDOR3", "BBSE3", "BPAC11", "SANB11",
    "ITSA4", "PRIO3", "RRRP3", "CSAN3", "UGPA3", "VBBR3", "BRFS3", "MRFG3",
    "BEEF3", "MGLU3", "CVCB3", "AZUL4", "GOAU4", "CYRE3", "MRVE3", "EZTC3",
    "CCRO3", "EGIE3", "TAEE11", "CPFE3", "KLBN11", "NATU3", "ASAI3", "CRFB3",
    "PCAR3", "COGN3", "YDUQ3", "BRKM5", "CASH3", "LWSA3", "EMBR3", "HYPE3",
    "FLRY3", "RAIZ4", "ALOS3", "MULT3", "IGTI11", "BRAP4", "DXCO3", "SMFT3",
    "CMIN3", "AURE3", "MOTV3", "ENEV3", "ONCO3", "VAMO3", "SLCE3", "TOTS3",
]

TICKERS_EUA = [
    # big techs e semicondutores
    "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "AMD",
    "NFLX", "SPCX", "PLTR", "ORCL", "INTC", "MU", "QCOM", "TSM", "ASML",
    "ARM", "SMCI", "CRM", "ADBE", "NOW", "SNOW", "CRWV", "IONQ", "RGTI",
    # internet, fintech e cripto
    "UBER", "ABNB", "SHOP", "COIN", "MSTR", "HOOD", "SOFI", "PYPL", "XYZ",
    "CRCL", "RBLX", "SNAP", "PINS", "SPOT", "DKNG", "MELI", "NU", "SE",
    # China
    "BABA", "PDD", "JD", "BIDU", "NIO", "LI", "XPEV",
    # consumo e varejo
    "DIS", "KO", "PEP", "MCD", "NKE", "SBUX", "WMT", "COST", "TGT", "HD",
    # bancos e financeiras
    "JPM", "BAC", "GS", "MS", "V", "MA", "BRK-B",
    # energia, indústria, defesa e espaço
    "XOM", "CVX", "COP", "BA", "LMT", "RTX", "GE", "CAT", "RKLB", "ASTS",
    "CEG", "VST", "OKLO", "SMR",
    # automotivo
    "F", "GM", "RIVN", "LCID",
    # saúde
    "JNJ", "PFE", "LLY", "NVO", "MRK", "ABBV", "UNH",
]

MERCADOS = {
    "b3": {"tickers": TICKERS_B3, "sufixo": ".SA", "moeda": "R$"},
    "eua": {"tickers": TICKERS_EUA, "sufixo": "", "moeda": "US$"},
}

# Busca por nome (o usuário pode digitar "nvidia" em vez de "NVDA")
NOMES = {
    "NVIDIA": "NVDA", "SPACEX": "SPCX", "APPLE": "AAPL", "TESLA": "TSLA",
    "MICROSOFT": "MSFT", "GOOGLE": "GOOGL", "ALPHABET": "GOOGL",
    "AMAZON": "AMZN", "NETFLIX": "NFLX", "DISNEY": "DIS", "INTEL": "INTC",
    "ORACLE": "ORCL", "UBER": "UBER", "COCA-COLA": "KO", "COCA COLA": "KO",
    "BOEING": "BA", "PALANTIR": "PLTR", "COINBASE": "COIN",
    "PETROBRAS": "PETR4", "VALE": "VALE3", "ITAU": "ITUB4", "ITAÚ": "ITUB4",
    "BRADESCO": "BBDC4", "BANCO DO BRASIL": "BBAS3", "AMBEV": "ABEV3",
    "MAGALU": "MGLU3", "WEG": "WEGE3", "NUBANK": "NU", "BITCOIN": "BTC-USD",
    "IBOVESPA": "^BVSP", "IBOV": "^BVSP", "S&P 500": "^GSPC", "NASDAQ": "^IXIC",
    "DOLAR": "USDBRL=X", "DÓLAR": "USDBRL=X",
}

# período do site -> (period, interval) do Yahoo Finance
PERIODOS = {
    "1d": ("1d", "5m"),
    "5d": ("5d", "30m"),
    "1m": ("1mo", "1d"),
    "6m": ("6mo", "1d"),
    "1a": ("1y", "1d"),
    "5a": ("5y", "1d"),
}

B3_RE = re.compile(r"^[A-Z]{4}\d{1,2}$")
SIMBOLO_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.=^-]{0,14}$")

# ---------------------------------------------------------------- cache ----
_cache: dict = {}


def com_cache(chave, ttl, fn):
    """Evita bater no Yahoo a cada clique."""
    agora = time.time()
    if chave in _cache and agora - _cache[chave][0] < ttl:
        return _cache[chave][1]
    valor = fn()
    _cache[chave] = (agora, valor)
    return valor


def num(x, casas=2):
    """float seguro para JSON (NaN vira None)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, casas)


# ---------------------------------------------------------------- dados ----
def calcular_ranking(mercado: str) -> dict:
    cfg = MERCADOS[mercado]
    sufixo = cfg["sufixo"]
    simbolos = [t + sufixo for t in cfg["tickers"]]

    dados = yf.download(
        simbolos, period="1y", auto_adjust=True, progress=False, threads=True
    )
    close = dados["Close"]
    if sufixo:
        close.columns = [c.replace(sufixo, "") for c in close.columns]
    # thresh baixo de propósito: aceita IPOs recentes (ex.: SpaceX)
    close = close.dropna(axis=1, thresh=10).sort_index().ffill()
    if len(close) < 10:
        raise RuntimeError("dados insuficientes")

    primeiro = close.bfill().iloc[0]  # primeiro preço disponível de cada papel
    dia = close.iloc[-1] / close.iloc[-2] - 1
    semana = close.iloc[-1] / close.iloc[-6] - 1
    ano = close.iloc[-1] / primeiro - 1

    def linha(t):
        return {
            "ticker": t,
            "preco": num(close[t].iloc[-1]),
            "dia": num(dia[t] * 100),
            "semana": num(semana[t] * 100),
            "ano": num(ano[t] * 100),
        }

    dia_ok = dia.dropna()
    return {
        "mercado": mercado,
        "moeda": cfg["moeda"],
        "data_ref": f"{close.index[-1]:%d/%m/%Y}",
        "baixas": [linha(t) for t in dia_ok.nsmallest(TOP_N).index],
        "altas": [linha(t) for t in dia_ok.nlargest(TOP_N).index],
    }


def resolver_simbolo(entrada: str) -> str:
    """PETR4 -> PETR4.SA ; NVDA -> NVDA ; ^BVSP -> ^BVSP."""
    t = entrada.upper().strip()
    return t + ".SA" if B3_RE.match(t) else t


def moeda_de(simbolo: str) -> str:
    if simbolo.endswith(".SA"):
        return "R$"
    if "." in simbolo or simbolo.startswith("^") or "=" in simbolo:
        return ""  # outras praças/índices: mostra só o número
    return "US$"


def buscar_historico(simbolo: str, periodo: str) -> dict | None:
    period, interval = PERIODOS[periodo]
    df = yf.Ticker(simbolo).history(
        period=period, interval=interval, auto_adjust=True
    )
    df = df.dropna(subset=["Close"])
    if df.empty:
        return None

    intraday = interval != "1d"
    fmt = "%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"

    # horário do pregão, para esconder as noites no gráfico intraday
    abre = fecha = None
    if intraday:
        passo = 5 if interval == "5m" else 30
        minutos = [d.hour * 60 + d.minute for d in df.index]
        abre = min(minutos) / 60
        fecha = min((max(minutos) + passo) / 60, 24)

    return {
        "ticker": simbolo.replace(".SA", ""),
        "moeda": moeda_de(simbolo),
        "intraday": intraday,
        "abre": abre,
        "fecha": fecha,
        "datas": [d.strftime(fmt) for d in df.index],
        "abertura": [num(v) for v in df["Open"]],
        "maxima": [num(v) for v in df["High"]],
        "minima": [num(v) for v in df["Low"]],
        "fechamento": [num(v) for v in df["Close"]],
    }


# ---------------------------------------------------------------- rotas ----
@app.route("/")
def index():
    todos = sorted(set(TICKERS_B3) | set(TICKERS_EUA))
    return render_template("index.html", tickers=todos, nomes=NOMES)


@app.route("/api/ranking")
def api_ranking():
    mercado = request.args.get("mercado", "b3")
    if mercado not in MERCADOS:
        return jsonify({"erro": "Mercado inválido."}), 400
    try:
        return jsonify(
            com_cache(f"rank:{mercado}", 300, lambda: calcular_ranking(mercado))
        )
    except Exception:
        return jsonify({"erro": "Não foi possível buscar as cotações."}), 502


@app.route("/api/historico/<ticker>")
def api_historico(ticker):
    ticker = ticker.upper().strip()
    periodo = request.args.get("periodo", "1a")

    if not SIMBOLO_RE.match(ticker):
        return jsonify({"erro": "Código de ativo inválido."}), 400
    if periodo not in PERIODOS:
        return jsonify({"erro": "Período inválido."}), 400

    simbolo = resolver_simbolo(ticker)
    try:
        dados = com_cache(
            f"hist:{simbolo}:{periodo}",
            60 if periodo in ("1d", "5d") else 600,
            lambda: buscar_historico(simbolo, periodo),
        )
    except Exception:
        return jsonify({"erro": "Falha ao consultar o Yahoo Finance."}), 502

    if dados is None:
        return jsonify({"erro": f"Sem dados para {ticker}."}), 404
    return jsonify(dados)


if __name__ == "__main__":
    # host 0.0.0.0 permite abrir pelo celular na mesma rede Wi-Fi.
    # Não ative debug=True com 0.0.0.0 (expõe o console do Werkzeug na rede).
    app.run(host="0.0.0.0", port=5000)
