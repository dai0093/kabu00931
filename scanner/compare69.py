# 検証69：類似局面（アナログ）予測のウォークフォワード検証
# 各日tで、t-60日より前の日だけを候補に「似た局面」上位K個を探し、その後60日に日経が−10%以上下げた割合を予測値とする。
# 実際の結果と比べ、ふだんの確率（t時点までの平均）より当たるかを測る（Brierスコア・上位10%の的中率）。
import yfinance as yf, pandas as pd, numpy as np, json
def g(t):
    d=yf.download(t,period="max",progress=False,auto_adjust=True)["Close"].squeeze().dropna();d.index=pd.to_datetime(d.index).tz_localize(None);return d
nk=g("^N225");sp=g("^GSPC").reindex(nk.index).ffill();sx=g("^SOX").reindex(nk.index).ffill()
df=pd.DataFrame({"nk":nk,"sp":sp,"sx":sx}).dropna()
F=pd.DataFrame(index=df.index)
F["dd"]=df.nk/df.nk.rolling(250).max()-1                 # 日経 1年高値から
F["r20"]=df.nk/df.nk.shift(20)-1                          # 日経 20日
F["r60"]=df.nk/df.nk.shift(60)-1                          # 日経 60日
F["ma"]=df.nk/df.nk.rolling(200).mean()-1                 # 日経 200日線乖離
F["spma"]=df.sp/df.sp.rolling(200).mean()-1               # S&P 200日線乖離
F["sxdd"]=df.sx/df.sx.rolling(250).max()-1                # SOX 1年高値から
F["vol"]=df.nk.pct_change().rolling(20).std()*np.sqrt(250)# 日経 変動率
F=F.dropna()
fut=(df.nk[::-1].rolling(60,min_periods=60).min()[::-1].shift(-1)/df.nk-1).reindex(F.index)
Y=(fut<=-0.10).astype(float);Y[fut.isna()]=np.nan
X=(F-F.mean())/F.std();Xv=X.values;idx=F.index
K=30;preds=[];base=[];ys=[];dates=[]
for i in range(len(idx)):
    if idx[i]<pd.Timestamp("2000-01-01") or np.isnan(Y.iloc[i]): continue
    cand=np.arange(0,i-60)
    cand=cand[~np.isnan(Y.values[cand])]
    if len(cand)<500: continue
    if i%3: continue   # 計算量のため3日おき
    d=np.sqrt(((Xv[cand]-Xv[i])**2).sum(1));nn=cand[np.argsort(d)[:K]]
    preds.append(Y.values[nn].mean());base.append(Y.values[cand].mean());ys.append(Y.values[i]);dates.append(idx[i])
p=np.array(preds);b=np.array(base);y=np.array(ys)
bs=lambda q:np.mean((q-y)**2)
print("検証日数",len(y),"実際に60日内−10%が起きた割合",round(y.mean()*100,1),"%")
print("Brier（小さいほど良い）類似予測",round(bs(p),4),"ふだんの確率",round(bs(b),4),"改善率",round((1-bs(p)/bs(b))*100,1),"%")
for th in [0.3,0.5]:
    m=p>=th;print(f"類似予測≥{int(th*100)}%の日",m.sum(),"日 実際に起きた",round(y[m].mean()*100,1) if m.sum() else '-',"%（ふだん",round(y.mean()*100,1),"%）")
q=np.quantile(p,0.9);m=p>=q;print("類似予測の上位10%の日 実際に起きた",round(y[m].mean()*100,1),"% 下位50%の日",round(y[p<=np.median(p)].mean()*100,1),"%")
# 年代ごと（傾向が崩れていないか）
D=pd.DataFrame({"p":p,"y":y,"b":b},index=dates)
for a,z in [("2000","2007"),("2008","2012"),("2013","2019"),("2020","2026")]:
    s=D[a:z]
    if len(s): print(a,"〜",z,"Brier改善",round((1-np.mean((s.p-s.y)**2)/np.mean((s.b-s.y)**2))*100,1),"% 上位10%日の発生率",round(s.y[s.p>=q].mean()*100,1) if (s.p>=q).sum() else '-',"%")
# 今日
i=len(idx)-1;cand=np.arange(0,i-60);cand=cand[~np.isnan(Y.values[cand])]
d=np.sqrt(((Xv[cand]-Xv[i])**2).sum(1));o=np.argsort(d)[:K];nn=cand[o]
print("今日",idx[i].date(),"類似予測（60日内に日経−10%以上）",round(Y.values[nn].mean()*100,1),"% ふだん",round(Y.values[cand].mean()*100,1),"%")
print("似ている過去の日（近い順10）",[str(idx[j].date()) for j in nn[:10]])
fr=fut.values[nn];print("その後60日の最安の中央値",round(np.nanmedian(fr)*100,1),"% −20%以上",round(np.mean(fr<=-0.2)*100,1),"%")
json.dump({"asOf":str(idx[i].date()),"p10":round(float(Y.values[nn].mean()),3),"base":round(float(Y.values[cand].mean()),3),"near":[str(idx[j].date()) for j in nn[:10]],"min_med":round(float(np.nanmedian(fr)),3),"p20":round(float(np.mean(fr<=-0.2)),3)},open("data/analog_today.json","w"),ensure_ascii=False)
