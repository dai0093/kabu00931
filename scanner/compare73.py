# 検証73：今日と同じ状態の日から、事前登録の「リーマン級」に至った割合（類似と傾向）
import yfinance as yf, pandas as pd, numpy as np
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
sp=g("^GSPC");sx=g("^SOX").reindex(sp.index).ffill();vx=g("^VIX").reindex(sp.index).ffill();nk=g("^N225").reindex(sp.index).ffill()
hy=(g("HYG")/g("IEF")).reindex(sp.index);ig=(g("LQD")/g("IEF")).reindex(sp.index);kre=g("KRE").reindex(sp.index)
spdd=sp/sp.rolling(250).max()-1;nkdd=nk/nk.rolling(250).max()-1
# 結果：その後250営業日のうちに S&P が1年高値から−40%以下 or 日経が−50%以下
spfut=pd.Series([ (sp.iloc[i:i+250]/sp.iloc[max(0,i-250):i+1].max()-1).min() if i+250<len(sp) else np.nan for i in range(len(sp))],index=sp.index)
nkfut=pd.Series([ (nk.iloc[i:i+250]/nk.iloc[max(0,i-250):i+1].max()-1).min() if i+250<len(nk) else np.nan for i in range(len(nk))],index=nk.index)
leh=((spfut<=-0.40)|(nkfut<=-0.50)).astype(float);leh[spfut.isna()]=np.nan
sx5=sx/sx.shift(5)-1;sp5=sp/sp.shift(5)-1;hy20=hy/hy.shift(20)-1
conds={
 "A 株の暴落（SOX5日≤−15% かつ VIX≥30）":(sx5<=-0.15)&(vx>=30),
 "B Aに加えS&P5日≤−7%":(sx5<=-0.15)&(vx>=30)&(sp5<=-0.07),
 "C 社債20日≤−1%（HYGのある2007年以降）":(hy20<=-0.01),
 "D 今日とほぼ同じ（A かつ 社債20日≤−1%）":(sx5<=-0.15)&(vx>=30)&(hy20<=-0.01),
 "E 社債20日≤−2%（事前登録の条件1）":(hy20<=-0.02),
 "ふだん（全日）":sp.notna()}
def ep(m):  # 連続する日を1つの局面にまとめる（60日以内は同じ局面）
    d=m[m].index;out=[];prev=None
    for x in d:
        if prev is None or (x-prev).days>90: out.append(x)
        prev=x
    return out
for k,m in conds.items():
    m=m.fillna(False)
    y=leh[m].dropna();e=ep(m)
    ey=[leh.get(x) for x in e if not np.isnan(leh.get(x,np.nan))]
    print(f"{k}: 該当{len(y)}日・局面{len(e)}回 → リーマン級に至った日{y.mean()*100 if len(y) else float('nan'):.1f}% 局面{(np.mean(ey)*100 if ey else float('nan')):.0f}%（{int(sum(ey))}/{len(ey)}）")
    if k!="ふだん（全日）": print("   局面の開始日:",[f"{x.date()}{'★' if leh.get(x)==1 else ''}" for x in e])
print("★＝その後250営業日でリーマン級（S&P−40% or 日経−50%）に至った局面")
