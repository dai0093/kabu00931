# 至急：11/20の米国終値で信用の線を確認
import yfinance as yf, pandas as pd
def g(t):
    d=yf.download(t,period="3mo",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
hy=g("HYG");ie=g("IEF");r=(hy/ie).dropna()
print("最新",r.index[-1].date(),"HYG÷IEF 1日",round((r.iloc[-1]/r.iloc[-2]-1)*100,2),"% 20日",round((r.iloc[-1]/r.iloc[-21]-1)*100,2),"%")
for t,n in [("^SOX","SOX"),("^IXIC","NASDAQ"),("^GSPC","S&P500"),("^VIX","VIX"),("KRE","米地銀"),("XLF","米金融"),("BX","ブラックストーン"),("KKR","KKR"),("APO","アポロ"),("ARES","アレス"),("REM","住宅ローンREIT"),("HYG","HYG"),("LQD","LQD"),("JPM","JPM"),("GS","GS"),("C","シティ")]:
    s=g(t);print(f"{n:10s} {s.index[-1].date()} {s.iloc[-1]:.2f} 1日{(s.iloc[-1]/s.iloc[-2]-1)*100:+.2f}% 5日{(s.iloc[-1]/s.iloc[-6]-1)*100:+.2f}%")
