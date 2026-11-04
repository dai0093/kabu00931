"""検証47：暴落への想定経路の進行度は、暴落の前に上がっていたか。履歴のない手入力項目（地政学・AI債務・AI→銀行）は除き、
履歴の取れる代替で各項目の点灯(1)/接近(0.5)を作る。進行度＝平均。米国の値は東京の翌営業日に使う。
前半(〜2011。HYGがあるのは2007〜)／後半(2012〜)で、進行度が高い日の『60日以内に日経−10%/−20%』『20日以内に−5%』を全日と比較。
主要な暴落の前（20・10・5営業日前）の進行度も表示。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
def dl(t, adj=False, s="1995-01-01"):
    x = yf.download(t, start=s, auto_adjust=adj, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
nk = dl("^N225"); cal = nk.index; mid = pd.Timestamp("2012-01-01")
def prev(s):
    idx = cal.searchsorted(s.index, side="right"); m = idx < len(cal); o = pd.Series(s.values[m], index=cal[idx[m]]); return o[~o.index.duplicated(keep="last")].reindex(cal).ffill()
def lv(x, lit, near, up=False):
    return pd.Series(np.where((x >= lit) if up else (x <= lit), 1.0, np.where((x >= near) if up else (x <= near), 0.5, 0.0)), index=x.index).where(x.notna())
pc = prev(pd.concat([dl(t).pct_change(5) for t in ("BX", "APO", "KKR", "ARES")], axis=1).median(axis=1)) * 100
hy = prev((dl("HYG", True) / dl("IEF", True)).pct_change(20)) * 100
bk = prev(dl("^BKX").pct_change(5)) * 100
lf = prev(pd.concat([dl(t).pct_change(5) for t in ("MET", "PRU")], axis=1).median(axis=1)) * 100
vix = prev(dl("^VIX")); vix3 = (vix >= 25).astype(int).rolling(3).sum()
z = lambda s: (s - s.rolling(500, min_periods=250).mean()) / s.rolling(500, min_periods=250).std()
fs = (z(vix) + z(-hy) + z(-bk)) / 3
sx = prev(dl("^SOX")); sdd = (sx / sx.rolling(250).max() - 1) * 100
r1 = nk.pct_change() * 100
tnx = prev(dl("^TNX")); t20 = tnx - tnx.shift(20)
oil = prev(dl("CL=F")); o250 = oil.pct_change(250) * 100
N = {"私募信用": lv(pc, -8, -5), "HY OAS": lv(hy, -2, -1), "金融機関株価": lv(bk, -10, -5), "生保": lv(lf, -10, -6),
     "NFCI": lv(fs, 1.5, 1.0, True), "VIX": pd.Series(np.where(vix3 >= 3, 1.0, np.where(vix >= 25, .5, 0.0)), index=cal).where(vix.notna()),
     "SOX下落": lv(sdd, -20, -10), "日経先物": lv(r1, -2.5, -1.5), "日米金利": lv(t20, 0.4, 0.25, True), "原油": lv(o250, 50, 30, True)}
P = {"2008型（信用の伝播）": ["私募信用", "HY OAS", "金融機関株価", "生保", "NFCI", "VIX"],
     "鉄道型（AI）※代替できる項目のみ": ["SOX下落", "HY OAS", "金融機関株価"],
     "1987型（金利ショック）": ["日米金利", "VIX", "日経先物"],
     "地政学・エネルギー※原油以降": ["原油", "日米金利", "VIX"]}
m60 = pd.Series([(nk.iloc[i:i+61].min()/nk.iloc[i]-1) if i+61 <= len(nk) else np.nan for i in range(len(nk))], index=cal)
m20 = pd.Series([(nk.iloc[i:i+21].min()/nk.iloc[i]-1) if i+21 <= len(nk) else np.nan for i in range(len(nk))], index=cal)
H = {"前半": (cal < mid) & (cal >= pd.Timestamp("2008-01-01")), "後半": cal >= mid}
B = {k: ((m60[m] <= -.1).mean(), (m60[m] <= -.2).mean(), (m20[m] <= -.05).mean()) for k, m in H.items()}
print("全日 | " + " | ".join(f"{k}: 60日−10% {b[0]*100:.0f}% −20% {b[1]*100:.1f}% 20日−5% {b[2]*100:.0f}%" for k, b in B.items()))
V = {}
for nm, ns in P.items():
    v = pd.concat([N[n] for n in ns], axis=1).mean(axis=1, skipna=False); V[nm] = v
    for th in (0.34, 0.5, 0.67):
        row = []; ok = True
        for k, m in H.items():
            s = (v >= th) & m; n = int(s.sum())
            if n < 20: row.append(f"{n}日"); ok = False; continue
            a, b, c = (m60[s].dropna() <= -.1).mean(), (m60[s].dropna() <= -.2).mean(), (m20[s].dropna() <= -.05).mean()
            row.append(f"{n}日 {a*100:.0f}%/{b*100:.1f}%/{c*100:.0f}%")
            if not (a >= 1.3 * B[k][0] and c >= 1.3 * B[k][2]): ok = False
        print(f"{nm} 進行度≥{int(th*100)}% | 前半 {row[0]} | 後半 {row[1]} | {'予測出来た' if ok else '予測出来なかった'}")
    print(f"   今の進行度 {v.iloc[-1]*100:.0f}%（{cal[-1].date()}）")
print("\n主要な暴落の前の進行度（20・10・5・0営業日前）")
for ev, d in (("リーマン", "2008-09-29"), ("2008年10月", "2008-10-06"), ("2011震災", "2011-03-14"), ("2015チャイナ", "2015-08-21"), ("2016年初", "2016-01-07"), ("2018年2月", "2018-02-02"), ("2018年12月", "2018-12-17"), ("コロナ", "2020-02-24"), ("2022年", "2022-03-07"), ("2024夏", "2024-08-02"), ("2025春", "2025-04-03"), ("2026/10", "2026-10-15")):
    i = cal.searchsorted(pd.Timestamp(d))
    print(ev, d, " / ".join(f"{nm[:6]} " + "→".join(f"{V[nm].iloc[i-k]*100:.0f}" if i-k >= 0 and pd.notna(V[nm].iloc[i-k]) else "—" for k in (20, 10, 5, 0)) for nm in P))
