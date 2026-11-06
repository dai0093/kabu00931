"""検証54：FINRA信用残高（月次）の急増の後、S&P500は下げたか。前半(〜2011)/後半(2012〜)"""
import warnings, io, urllib.request; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
b = urllib.request.urlopen(urllib.request.Request("https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx", headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
x = pd.read_excel(io.BytesIO(b)); x.columns = ["ym", "debit", "fc_cash", "fc_margin"]
x["d"] = pd.to_datetime(x["ym"].astype(str).str[:7]) + pd.offsets.MonthEnd(0); x = x.set_index("d").sort_index()
print("期間", x.index[0].date(), "〜", x.index[-1].date(), "最新", x["debit"].iloc[-1])
sp = yf.download("^GSPC", start="1996-01-01", auto_adjust=False, progress=False)["Close"].squeeze().dropna(); sp.index = pd.to_datetime(sp.index).tz_localize(None)
spm = sp.resample("ME").last()
g12 = x["debit"].pct_change(12); g14 = x["debit"].pct_change(14)
# 純現金不足（資料の Cash Underwater の近似）＝ 信用残 − (現金口座の自由残高 + 信用口座の自由残高)
und = x["debit"] - x["fc_cash"] - x["fc_margin"]
f12 = spm.shift(-12) / spm - 1; dd12 = pd.Series([(spm.iloc[i+1:i+13].min()/spm.iloc[i]-1) if i+13 <= len(spm) else np.nan for i in range(len(spm))], index=spm.index)
mid = pd.Timestamp("2012-01-01")
for nm, cond in (("12か月で+30%以上", g12 >= 0.30), ("12か月で+40%以上", g12 >= 0.40), ("14か月で+65%以上（資料の条件）", g14 >= 0.65), ("純現金不足が過去最大を更新", und >= und.cummax())):
    for half, m in (("前半", x.index < mid), ("後半", x.index >= mid)):
        ev = x.index[(cond & m).fillna(False).values]
        ok = [d for d in ev if d in f12.index and pd.notna(f12.get(d))]
        if not ok: print(f"{nm} {half}: 該当{len(ev)}月（その後のデータなし）"); continue
        a = f12.reindex(ok); c = dd12.reindex(ok)
        base = f12[(f12.index < mid) if half == "前半" else (f12.index >= mid)].dropna(); based = dd12[(dd12.index < mid) if half == "前半" else (dd12.index >= mid)].dropna()
        print(f"{nm} {half}: {len(ok)}月 → 12か月後S&P 平均{a.mean()*100:+.1f}%（全月{base.mean()*100:+.1f}%） 下落{(a<0).mean()*100:.0f}%（全月{(base<0).mean()*100:.0f}%）／12か月内に−20%以下 {(c<=-0.2).mean()*100:.0f}%（全月{(based<=-0.2).mean()*100:.0f}%）  期間 {ok[0].date()}〜{ok[-1].date()}")
print("今:", x.index[-1].date(), f"12か月増加 {g12.iloc[-1]*100:+.1f}%  14か月 {g14.iloc[-1]*100:+.1f}%  純現金不足 {und.iloc[-1]:,.0f}（過去最大 {und.max():,.0f}）")
