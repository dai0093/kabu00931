# 検証99（週次点検 2026-11-28）：確率予測は「荒れた相場」で下落確率を低く見積もり過ぎていないか
# 事実（実行前）：10/29〜11/19の15日分、「5日以内に−5%」の予測は平均18%、実際は8/15（53%）で到達。
# 事前登録（実行前に固定）：
#  似た局面＝日経の20日変動率（年率）≥30% かつ 60日高値から−10%以下（今日は 39.8%・−16.9%）
#  比べる案：V0 現行（ロジスティック C=0.3）／V1 交互作用（変動率×下落幅、VIX×下落幅、変動率²）を追加／V2 正則化を弱める（C=3）／V3 V1+V2
#  採用の条件：前半(〜2011)で学習→後半(2012〜)で採点、後半で学習→前半で採点 の両方向で、
#   (a) 全日のBrierがV0より悪化しない（+0.5%以内）、(b) 似た局面のBrierがV0より2%以上良い、(c) 似た局面の「実際−予測平均」の差が縮む。
#   3つとも両方向で満たした案だけを outlook.py に入れる。満たさなければ入れない（表示の注意書きのみ）。
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
from sklearn.linear_model import LogisticRegression
def dl(t, start="1995-01-01"):
    x = yf.download(t, start=start, auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]; x.index = pd.to_datetime(x.index).tz_localize(None); return x["Close"].dropna()
# ---- A. 今週の実データ（確定終値）
print("== A. 直近の確定終値")
hy, ief, lqd = dl("HYG", "2026-08-01"), dl("IEF", "2026-08-01"), dl("LQD", "2026-08-01")
q = (hy / ief).dropna(); q2 = (lqd / ief).dropna()
t = pd.DataFrame({"HYG÷IEF20日%": ((q / q.shift(20) - 1) * 100).round(2), "LQD÷IEF20日%": ((q2 / q2.shift(20) - 1) * 100).round(2)})
print(t.tail(12).to_string())
for tk in ("^N225", "1321.T", "^SOX", "^VIX", "^GSPC"):
    s = dl(tk, "2026-10-25"); print(tk, " ".join(f"{d:%m/%d}:{v:,.1f}" for d, v in s.tail(10).items()))
# ---- B. 確率予測の較正（似た局面）
C = dl("^N225"); cal = C.index
def prev(s):
    idx = cal.searchsorted(s.index, side="right"); m = idx < len(cal)
    o = pd.Series(s.values[m], index=cal[idx[m]]); return o[~o.index.duplicated(keep="last")].reindex(cal).ffill()
S, V, B, J = (prev(dl(x)) for x in ("^SOX", "^VIX", "^BKX", "JPY=X"))
r1 = C.pct_change()
F = pd.DataFrame({"nk_dd60": C / C.rolling(60).max() - 1, "nk_dd250": C / C.rolling(250).max() - 1, "nk_r5": C.pct_change(5), "nk_r20": C.pct_change(20),
    "nk_vol20": r1.rolling(20).std() * np.sqrt(252), "nk_ma200": C / C.rolling(200).mean() - 1, "sox_r1": S.pct_change(), "sox_r5": S.pct_change(5),
    "sox_r20": S.pct_change(20), "sox_dd60": S / S.rolling(60).max() - 1, "vix": V, "vix_r5": V / V.shift(5) - 1, "bk_r5": B.pct_change(5),
    "bk_dd60": B / B.rolling(60).max() - 1, "jpy_r20": J.pct_change(20)}).dropna()
def fut_min(h):
    a = C.values; o = np.full(len(a), np.nan)
    for i in range(len(a) - h): o[i] = a[i + 1:i + 1 + h].min() / a[i] - 1
    return pd.Series(o, index=cal)
Y = {f"{h}d_-{int(th*100)}": (fut_min(h) <= -th).astype(float).where(fut_min(h).notna()) for h, th in ((5, .05), (20, .05), (20, .10))}
def addx(X):
    X = X.copy(); X["vol_x_dd"] = X.nk_vol20 * X.nk_dd60; X["vix_x_dd"] = X.vix * X.nk_dd60; X["vol2"] = X.nk_vol20 ** 2; return X
VAR = {"V0 現行": (False, 0.3), "V1 交互作用": (True, 0.3), "V2 正則化弱": (False, 3.0), "V3 V1+V2": (True, 3.0)}
def fitpred(tr, te, inter, c):
    Xtr, Xte = tr.drop(columns="y"), te.drop(columns="y")
    if inter: Xtr, Xte = addx(Xtr), addx(Xte)
    mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
    m = LogisticRegression(C=c, max_iter=3000).fit((Xtr - mu) / sd, tr.y); return m.predict_proba((Xte - mu) / sd)[:, 1]
mid = pd.Timestamp("2012-01-01"); adopt = {}
for k, y in Y.items():
    d = F.join(y.rename("y")).dropna(); A, Bh = d[d.index < mid], d[d.index >= mid]
    print(f"\n== B. {k}（似た局面＝変動率≥30%かつ60日高値から−10%以下）")
    ok = {v: True for v in VAR}; base = {}
    for name, (tr, te) in {"前半で学習→後半で採点": (A, Bh), "後半で学習→前半で採点": (Bh, A)}.items():
        reg = (te.nk_vol20 >= 0.30) & (te.nk_dd60 <= -0.10)
        print(f" {name}：全{len(te)}日・似た局面{int(reg.sum())}日（実際の到達率 全{te.y.mean()*100:.1f}%・似た局面{te.y[reg].mean()*100:.1f}%）")
        for v, (inter, c) in VAR.items():
            p = fitpred(tr, te, inter, c); ba = np.mean((p - te.y) ** 2); br = np.mean((p[reg] - te.y[reg]) ** 2); gap = te.y[reg].mean() - p[reg].mean()
            if v.startswith("V0"): base = (ba, br, gap)
            else:
                cond = ba <= base[0] * 1.005 and br <= base[1] * 0.98 and abs(gap) < abs(base[2])
                ok[v] &= cond
            print(f"   {v}: 似た局面の予測平均{p[reg].mean()*100:.1f}%→実際{te.y[reg].mean()*100:.1f}%（差{gap*100:+.1f}pt） Brier 全{ba:.4f} 似た局面{br:.4f}")
            if v.startswith("V0"):  # 局面ごと（似た局面に入った最初の日）
                ep = te[reg].index; firsts = [ep[0]] + [ep[i] for i in range(1, len(ep)) if (ep[i] - ep[i - 1]).days > 30]
                pr = pd.Series(p, index=te.index)
                print("     局面ごと（初日:予測→その局面中の実際の到達率）：" + " ".join(f"{f:%Y-%m}:{pr[f]*100:.0f}%→{te.y[(te.index>=f)&(te.index<f+pd.Timedelta(days=45))&reg].mean()*100:.0f}%" for f in firsts[:25]))
    adopt[k] = [v for v, o in ok.items() if o and not v.startswith("V0")]
    print(f" → 両方向で条件を満たした案：{adopt[k] or 'なし'}")
# 今日の値（全期間で学習）
print("\n== C. 今日の確率（全期間で学習）")
today = F.iloc[[-1]]
for k, y in Y.items():
    d = F.join(y.rename("y")).dropna(); te = today.assign(y=0.0)
    print(k, today.index[-1].date(), " ".join(f"{v}:{fitpred(d, te, i, c)[0]*100:.1f}%" for v, (i, c) in VAR.items()))
    reg = (d.nk_vol20 >= 0.30) & (d.nk_dd60 <= -0.10); print(f"   全期間の似た局面での実際の到達率 {d.y[reg].mean()*100:.1f}%（{int(reg.sum())}日）・ふだん {d.y.mean()*100:.1f}%")
print("\n採用：", adopt)
