import yfinance as yf, pandas as pd
for tick in (["JPM","BAC","^SOX","BNP.PA","8306.T"], ["JPM"], ["BNP.PA"]):
    df = yf.download(tick, period="10d", auto_adjust=False, progress=False)["Close"]
    print(tick); print(df.tail(4))
