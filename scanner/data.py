import time
import yfinance as yf
from universe import STOCKS


def load(period="5y"):
    """全銘柄の日足を取得。{code: DataFrame}"""
    tickers = [f"{c}.T" for c in STOCKS]
    out = {}
    for attempt in range(3):
        raw = yf.download(tickers, period=period, group_by="ticker",
                          auto_adjust=True, threads=True, progress=False)
        for c in STOCKS:
            t = f"{c}.T"
            if t in raw.columns.get_level_values(0):
                df = raw[t].dropna(subset=["Close"])
                if len(df) > 100:
                    out[c] = df
        if len(out) >= len(STOCKS) * 0.8:
            break
        time.sleep(30)
    return out
