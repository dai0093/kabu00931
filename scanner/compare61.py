"""検証61：『私募信用株5日≤−8%・社債HYG÷IEF20日≤−2%・VIX急騰が、日経の急落の4〜7営業日前に先行点灯する』は本当か。
急落＝日経が10営業日以内に−8%（検証28と同じ、初日を基準）。各指標について
①急落の4〜7営業日前（T-7〜T-4）に点灯していた割合（捕捉率） ②点灯した日のうち、その後4〜10営業日に急落が始まった割合（的中率）、ふだんの急落開始率と比較。
HYG(2007〜)・BX等(2007〜)のため前半は2007〜2011。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
def dl(t, adj=False, s="1995-01-01"):
    x = yf.download(t, start=s, auto_adjust=adj, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
nk = dl("^N225"); cal = nk.index; mid = pd.Timestamp("2012-01-01")
def prev(s):
    idx = cal.searchsorted(s.index, side="right"); m = idx < len(cal); o = pd.Series(s.values[m], index=cal[idx[m]]); return o[~o.index.duplicated(keep="last")].reindex(cal).ffill()
f10 = pd.Series([(nk.iloc[i+1:i+11].min()/nk.iloc[i]-1) if i+11 <= len(nk) else np.nan for i in range(len(nk))], index=cal)
ev = []
for d in cal[(f10 <= -0.08).values]:
    if not ev or (d - ev[-1]).days > 40: ev.append(d)
pc = prev(pd.concat([dl(t).pct_change(5) for t in ("BX", "APO", "KKR", "ARES")], axis=1).median(axis=1))
hy = prev((dl("HYG", True) / dl("IEF", True)).pct_change(20))
vix = prev(dl("^VIX")); vs = vix / vix.rolling(20).mean() - 1
S = {"私募信用株5日≤−8%": pc <= -0.08, "社債20日≤−2%": hy <= -0.02, "VIX急騰（20日平均比+30%以上）": vs >= 0.30,
     "いずれか": (pc <= -0.08) | (hy <= -0.02) | (vs >= 0.30)}
start = pd.Series(False, index=cal); start.loc[ev] = True
fut = pd.Series([start.iloc[i+4:i+11].any() for i in range(len(cal))], index=cal)
for half, m in (("前半(2007-2011)", (cal < mid) & (cal >= pd.Timestamp("2007-06-01"))), ("後半(2012〜)", cal >= mid)):
    E = [d for d in ev if m[cal.get_loc(d)]]
    print(f"\n{half}: 急落 {len(E)}件／ふだん、ある日から4〜10日後に急落が始まる割合 {fut[m].mean()*100:.1f}%")
    for nm, s in S.items():
        s = s.reindex(cal).fillna(False)
        cap = [s.iloc[max(0, cal.get_loc(d)-7):cal.get_loc(d)-3].any() for d in E]
        on = s & m
        print(f"  {nm}: 4〜7日前に点灯 {sum(cap)}/{len(E)}件（{np.mean(cap)*100:.0f}%）／点灯日{int(on.sum())}日のうち4〜10日後に急落開始 {fut[on].mean()*100:.1f}%")
