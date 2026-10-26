"""検証35：動画「94%的中する底打ちサイン」の主張を、日経225・S&P500・ナスダックで再現できるか。
動画の主張（ナスダック55年）：高値から10%以上下落した局面で、
 手法A 週足で「戻り高値」を終値で上抜け＝的中70%／週足の上昇N波動の完成＝76%
 手法B 月足で戻り高値上抜け／N波動完成＝94%（16回中15回）
 的中の定義：サイン後6か月間、サイン時点の「直近1か月の安値」を一度も下回らない。
再現の定義：週足(金曜)／月足。谷＝高値からの最安値の足。戻り高値＝谷の直前8足(月足は6足)の最高値。
 N波動＝谷のあと、反発高値→押し安値（谷より高い）→反発高値を終値で上抜け。
 サイン＝谷が更新されていない間の最初の上抜け。比較の基準＝同じ下落局面(高値から−10%以下)の全ての足。
前半＝2011年まで、後半＝2012年以降で分けて、同じ的中率が出るかを見る。"""
import warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
def dl(t):
    x = yf.download(t, start="1950-01-01", auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None); return x.dropna(subset=["Close"])
def bars(d, rule):
    return d.resample(rule).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
def analyze(W, rebwin, hz, ddth, lbk):
    H, L, C = W.High.values, W.Low.values, W.Close.values; n = len(W); idx = W.index
    sig = {"戻り高値": [], "N波動": []}; base = []
    peak = H[0]; pk = 0; m = None; used = set(); usedN = set()
    for i in range(1, n):
        if H[i] >= peak: peak, pk, m = H[i], i, None; continue
        if m is None or L[i] < L[m]: m = i
        if L[m] / peak - 1 > -ddth: continue
        if C[i] / peak - 1 <= -ddth and i + hz < n:
            base.append((i, np.min(L[i + 1:i + hz + 1]) >= np.min(L[max(0, i - lbk + 1):i + 1]), C[i + hz] / C[i] - 1, C[i] / L[m] - 1))
        if i > m and i + hz < n:
            lo = max(pk, m - rebwin); reb = H[lo:m].max() if m > lo else None
            if reb is not None and C[i] > reb and m not in used:
                used.add(m); ml = np.min(L[max(0, i - lbk + 1):i + 1])
                sig["戻り高値"].append((i, np.min(L[i + 1:i + hz + 1]) >= ml, C[i + hz] / C[i] - 1, C[i] / L[m] - 1))
            if i - m >= 3 and m not in usedN:
                seg = H[m + 1:i]
                if len(seg) >= 2:
                    b = int(np.argmax(seg)) + m + 1
                    if b < i - 1:
                        p = L[b + 1:i].min()
                        if p > L[m] and C[i] > H[b]:
                            usedN.add(m); ml = np.min(L[max(0, i - lbk + 1):i + 1])
                            sig["N波動"].append((i, np.min(L[i + 1:i + hz + 1]) >= ml, C[i + hz] / C[i] - 1, C[i] / L[m] - 1))
    return sig, base, idx
def show(name, W, tf, rebwin, hz, ddth, lbk):
    sig, base, idx = analyze(W, rebwin, hz, ddth, lbk)
    f = lambda L: f"{len(L)}回 的中{np.mean([x[1] for x in L])*100:.0f}%（{int(np.sum([x[1] for x in L]))}/{len(L)}） 後{hz}足の騰落 中央{np.median([x[2] for x in L])*100:+.1f}% 谷から{np.median([x[3] for x in L])*100:+.0f}%上" if L else "0回"
    print(f"\n【{name} {tf} 下落{int(ddth*100)}%以上】")
    print("  基準（同じ下落局面の全ての足）:", f(base))
    for k, L in sig.items():
        print(f"  {k}: {f(L)}")
        pre = [x for x in L if idx[x[0]].year <= 2011]; post = [x for x in L if idx[x[0]].year >= 2012]
        print(f"     前半(〜2011) {f(pre)}\n     後半(2012〜) {f(post)}")
for name, t in (("ナスダック", "^IXIC"), ("S&P500", "^GSPC"), ("日経225", "^N225")):
    d = dl(t); print(f"\n==== {name} {d.index[0].date()}〜 ====")
    Wk = bars(d, "W-FRI"); Mo = bars(d, "ME")
    show(name, Wk, "週足", 8, 26, 0.10, 4)
    show(name, Mo, "月足", 6, 6, 0.10, 1)
    show(name, Mo, "月足", 6, 6, 0.20, 1)
