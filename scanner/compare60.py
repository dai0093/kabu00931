"""検証60：月足の『下落のN波動』（高値→安値→高値を超えない戻り高値→直前の安値割れ）の中で、
A 反発した月（安値更新後に陽線で引けた月）の安値は、24か月以内にもう一度割られたか
B 月足の戻り高値（下落N波動の戻り高値）を終値で上抜けた後、24か月以内に底（それまでの最安値）を割ったか
日経・S&P500・SOX、前半(〜2011)/後半(2012〜)。山谷は前後2か月の極値。"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
mid = pd.Timestamp("2012-01-01")
def mo(t):
    x = yf.download(t, start="1970-01-01", interval="1mo", auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]; x.index = pd.to_datetime(x.index).tz_localize(None); return x.dropna()
for nm, t in (("日経", "^N225"), ("S&P500", "^GSPC"), ("SOX", "^SOX")):
    x = mo(t); H, L, C, O = x.High.values, x.Low.values, x.Close.values, x.Open.values; n = len(x)
    pk = [i for i in range(2, n - 2) if H[i] == max(H[i-2:i+3])]; tr = [i for i in range(2, n - 2) if L[i] == min(L[i-2:i+3])]
    A = {"前半": [], "後半": []}; B = {"前半": [], "後半": []}; seen = set()
    for a in pk:                         # 高値a → 安値b → 戻り高値c(<a) → 安値割れの月d
        bs = [b for b in tr if b > a]
        if not bs: continue
        b = bs[0]; cs = [c for c in pk if c > b]
        if not cs or H[cs[0]] >= H[a]: continue
        c = cs[0]; ds = [d for d in range(c + 1, n) if L[d] < L[b]]
        if not ds: continue
        d = ds[0]
        if d in seen: continue
        seen.add(d); half = "前半" if x.index[d] < mid else "後半"
        # A: d以降、戻り高値を超えるまでの反発月（その月までの最安値を更新した後の陽線月）
        lo = L[b]; j = d
        while j < n and C[j] <= H[c]:
            lo = min(lo, L[j])
            if j > d and C[j] > O[j] and L[j] <= lo * 1.03 and j + 1 < n:
                fut = L[j+1:j+25]
                if len(fut) >= 6: A[half].append(bool((fut < L[j]).any()))
            j += 1
        # B: 戻り高値の終値上抜け
        if j < n and j + 6 < n:
            bot = min(L[b:j+1]); fut = L[j+1:j+25]
            B[half].append((bool((fut < bot).any()), C[j] / bot - 1))
    for half in ("前半", "後半"):
        a = A[half]; b = B[half]
        sa = f"反発月 {len(a)}回 → 24か月内に安値割れ {sum(a)}回（{np.mean(a)*100:.0f}%）" if a else "反発月 0回"
        sb = f"戻り高値の上抜け {len(b)}回 → 24か月内に底割れ {sum(v for v,_ in b)}回（{np.mean([v for v,_ in b])*100:.0f}%）、上抜け時点で底から中央値{np.median([g for _,g in b])*100:+.0f}%" if b else "戻り高値の上抜け 0回"
        print(f"{nm} {half}：{sa}／{sb}")
