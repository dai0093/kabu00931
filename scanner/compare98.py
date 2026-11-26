# 1321の値の確認：日経との比率が途中で跳んでいないか（分割の扱い）
import yfinance as yf,pandas as pd
e=yf.download("1321.T",period="2y",progress=False,auto_adjust=False)["Close"].squeeze().dropna();n=yf.download("^N225",period="2y",progress=False,auto_adjust=False)["Close"].squeeze().dropna()
r=(n/e).dropna();print(r.resample("ME").last().round(1).tail(26).to_string());print(e.tail(5).to_string())
print(yf.Ticker("1321.T").splits.tail(5))
