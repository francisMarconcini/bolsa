#!/usr/bin/env python3
"""
Maiores baixas da B3 - relatório diário.

Mostra as 20 ações que mais caíram no último pregão, com:
  - variação do dia
  - variação dos últimos 5 pregões (dia a dia)
  - variação em 12 meses + gráfico do último ano
  - distância da máxima de 12 meses

Saídas: tabela no terminal + relatório HTML (relatorio_baixas_b3.html).
Opcional: envio por Telegram (defina TELEGRAM_TOKEN e TELEGRAM_CHAT_ID).

Instalação:  pip install yfinance pandas requests
Uso:         python baixas_b3.py
"""

import os
import sys
from datetime import datetime

import pandas as pd
import requests
import yfinance as yf

TOP_N = 20
ARQUIVO_HTML = "relatorio_baixas_b3.html"

# Universo de ações líquidas da B3 (edite à vontade).
# Tickers que não existirem mais no Yahoo são ignorados automaticamente.
TICKERS = [
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

DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


# ---------------------------------------------------------------- dados ----
def baixar_precos() -> pd.DataFrame:
    """Baixa 1 ano de preços de fechamento ajustados."""
    simbolos = [f"{t}.SA" for t in TICKERS]
    dados = yf.download(
        simbolos, period="1y", auto_adjust=True, progress=False, threads=True
    )
    close = dados["Close"]
    close.columns = [c.replace(".SA", "") for c in close.columns]
    # descarta papéis sem histórico suficiente (deslistados / muito novos)
    close = close.dropna(axis=1, thresh=150).sort_index().ffill()
    if close.shape[0] < 10:
        sys.exit("Não consegui baixar dados suficientes. Verifique a internet.")
    return close


def calcular(close: pd.DataFrame):
    """Monta a tabela das maiores baixas e os retornos diários."""
    ret = close.pct_change()
    dia = ret.iloc[-1]
    piores = dia.nsmallest(TOP_N).index

    df = pd.DataFrame(
        {
            "Preço": close.iloc[-1],
            "Dia": dia,
            "Semana": close.iloc[-1] / close.iloc[-6] - 1,
            "12m": close.iloc[-1] / close.iloc[0] - 1,
            "vs Máx 12m": close.iloc[-1] / close.max() - 1,
        }
    ).loc[piores]
    df.index.name = "Ação"
    return df, ret


def pct(x: float) -> str:
    return f"{x * 100:+.2f}%"


# ------------------------------------------------------------- terminal ----
def imprimir_terminal(df: pd.DataFrame, data_ref) -> None:
    out = df.copy()
    out["Preço"] = out["Preço"].map(lambda v: f"R$ {v:,.2f}")
    for c in ["Dia", "Semana", "12m", "vs Máx 12m"]:
        out[c] = out[c].map(pct)
    print(f"\nMaiores baixas da B3 - pregão de {data_ref:%d/%m/%Y}\n")
    print(out.to_string())
    print()


def texto_telegram(df: pd.DataFrame, data_ref) -> str:
    linhas = [f"<b>Maiores baixas da B3 - {data_ref:%d/%m/%Y}</b>", "<pre>"]
    linhas.append(f"{'Ação':<7}{'Dia':>8}{'Semana':>9}{'12m':>9}")
    for t, r in df.iterrows():
        linhas.append(f"{t:<7}{pct(r['Dia']):>8}{pct(r['Semana']):>9}{pct(r['12m']):>9}")
    linhas.append("</pre>")
    return "\n".join(linhas)


# ----------------------------------------------------------------- HTML ----
def sparkline(serie: pd.Series, w: int = 180, h: int = 40) -> str:
    s = serie.dropna()
    lo, hi = s.min(), s.max()
    faixa = (hi - lo) or 1
    n = len(s) - 1 or 1
    pontos = " ".join(
        f"{i / n * w:.1f},{h - (v - lo) / faixa * h:.1f}" for i, v in enumerate(s)
    )
    cor = "#c0392b" if s.iloc[-1] < s.iloc[0] else "#27ae60"
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<polyline fill="none" stroke="{cor}" stroke-width="1.5" points="{pontos}"/>'
        "</svg>"
    )


def cor(x: float) -> str:
    return "#c0392b" if x < 0 else "#27ae60"


def gerar_html(df, ret, close, data_ref) -> str:
    ultimos5 = ret.tail(5)
    cab_dias = "".join(f"<th>{DIAS_SEMANA[d.weekday()]}<br>{d:%d/%m}</th>" for d in ultimos5.index)

    linhas = []
    for t, r in df.iterrows():
        dias = "".join(
            f'<td style="color:{cor(v)}">{pct(v)}</td>' for v in ultimos5[t]
        )
        linhas.append(
            f"<tr><td><b>{t}</b></td><td>R$ {r['Preço']:,.2f}</td>"
            f'<td style="color:{cor(r["Dia"])}"><b>{pct(r["Dia"])}</b></td>'
            f"{dias}"
            f'<td style="color:{cor(r["Semana"])}">{pct(r["Semana"])}</td>'
            f'<td style="color:{cor(r["12m"])}">{pct(r["12m"])}</td>'
            f'<td style="color:{cor(r["vs Máx 12m"])}">{pct(r["vs Máx 12m"])}</td>'
            f"<td>{sparkline(close[t])}</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maiores baixas da B3</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:16px;color:#222}}
 .wrap{{overflow-x:auto}}
 table{{border-collapse:collapse;font-size:14px}}
 th,td{{padding:6px 10px;border-bottom:1px solid #ddd;text-align:right;white-space:nowrap}}
 th{{background:#f4f4f4;position:sticky;top:0}}
 td:first-child,th:first-child{{text-align:left}}
 small{{color:#666}}
</style></head><body>
<h2>Maiores baixas da B3</h2>
<p>Pregão de {data_ref:%d/%m/%Y} &middot; <small>gerado em {datetime.now():%d/%m/%Y %H:%M}</small></p>
<div class="wrap"><table>
<tr><th>Ação</th><th>Preço</th><th>Dia</th>{cab_dias}<th>Semana</th><th>12 meses</th><th>vs Máx 12m</th><th>Gráfico 1 ano</th></tr>
{''.join(linhas)}
</table></div>
<p><small>Dados do Yahoo Finance, podem ter atraso. Informativo, não é recomendação de investimento.</small></p>
</body></html>"""


# ------------------------------------------------------------- telegram ----
def enviar_telegram(texto: str, arquivo: str) -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    base = f"https://api.telegram.org/bot{token}"
    requests.post(
        f"{base}/sendMessage",
        data={"chat_id": chat_id, "text": texto, "parse_mode": "HTML"},
        timeout=30,
    )
    with open(arquivo, "rb") as f:
        requests.post(
            f"{base}/sendDocument",
            data={"chat_id": chat_id},
            files={"document": f},
            timeout=60,
        )
    print("Enviado para o Telegram.")


# ----------------------------------------------------------------- main ----
def main() -> None:
    close = baixar_precos()
    df, ret = calcular(close)
    data_ref = close.index[-1]

    imprimir_terminal(df, data_ref)

    html = gerar_html(df, ret, close, data_ref)
    with open(ARQUIVO_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Relatório salvo em {ARQUIVO_HTML}")

    enviar_telegram(texto_telegram(df, data_ref), ARQUIVO_HTML)


if __name__ == "__main__":
    main()