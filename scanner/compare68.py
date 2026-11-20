# 検証68：米国不動産関連の今の下落率と、2007年の同じ時点（日経が高値から同じ営業日数）を比べる
import yfinance as yf, pandas as pd
T={"ITB":"住宅建設株","XHB":"住宅関連株","VNQ":"米REIT","KRE":"地方銀行","IYR":"米不動産株","REM":"住宅ローンREIT","HYG":"ハイイールド社債"}
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
for t,n in T.items():
    try:
        s=g(t)
        now=s.iloc[-1];hi=s[-260:].max();d5=(s.iloc[-1]/s.iloc[-6]-1)*100;d20=(s.iloc[-1]/s.iloc[-21]-1)*100
        o=s["2006-01-01":"2007-11-30"];o_hi=o.max();o_now=s[:"2007-11-30"].iloc[-1]
        print(f"{n}({t}) 最新{s.index[-1].date()} 1年高値から{(now/hi-1)*100:.1f}% 5日{d5:+.1f}% 20日{d20:+.1f}% ｜2007年11月末時点：高値から{(o_now/o_hi-1)*100:.1f}%")
    except Exception as e: print(t,"取得失敗",e)
