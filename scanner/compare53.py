"""検証53：取り込み資料の主張を過去データで確認。前半(〜2011)/後半(2012〜)。
①中間選挙後のアノマリー：中間選挙の年の11月初めからの6か月・12か月のS&P500（全期間の同じ長さの平均と比較）
②急落後の二番底：S&P500 1日≤−4% または 日経 1日≤−5% の日のあと、5日以内に一旦反発（+3%）し、その後40営業日以内に急落日の安値を割ったか（W字）。60日後の騰落
③信用残高の急増：FINRAの月次信用残高（取得できれば）が12か月で+30%以上（資料は14か月で+65%超を3例と主張）の後、12か月のS&P500"""
import warnings, io, urllib.request; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
def dl(t, s="1950-01-01"):
    x = yf.download(t, start=s, auto_adjust=False, progress=False)["Close"].squeeze().dropna(); x.index = pd.to_datetime(x.index).tz_localize(None); return x
sp = dl("^GSPC"); nk = dl("^N225", "1970-01-01"); mid = pd.Timestamp("2012-01-01")
print("=== ①中間選挙後のS&P500（中間選挙の年の11/1〜） ===")
r6, r12 = [], []
for y in range(1950, 2025, 4):
    y0 = y + 2  # 中間選挙年：1950,1954,...  (1950は中間選挙年)
for y in range(1950, 2026, 4):
    d0 = sp.index[sp.index >= pd.Timestamp(f"{y}-11-01")]
    if not len(d0): continue
    d0 = d0[0]; i = sp.index.get_loc(d0)
    a = sp.iloc[min(i+126, len(sp)-1)] / sp.iloc[i] - 1; b = sp.iloc[i+252] / sp.iloc[i] - 1 if i + 252 < len(sp) else np.nan
    r6.append((y, a)); r12.append((y, b)); print(f"  {y}: 6か月 {a*100:+.1f}%  12か月 {b*100:+.1f}%" if pd.notna(b) else f"  {y}: 6か月 {a*100:+.1f}%")
base6 = (sp.shift(-126) / sp - 1).dropna(); base12 = (sp.shift(-252) / sp - 1).dropna()
for nm, lo, hi in (("前半(1950〜2010)", 1950, 2011), ("後半(2014〜2022)", 2012, 2026)):
    a = [x for y, x in r6 if lo <= y < hi]; b = [x for y, x in r12 if lo <= y < hi and pd.notna(x)]
    m = (base6.index.year >= lo) & (base6.index.year < hi); m2 = (base12.index.year >= lo) & (base12.index.year < hi)
    print(f"{nm}: 6か月 平均{np.mean(a)*100:+.1f}%（全期間{base6[m].mean()*100:+.1f}%） 上昇{np.mean([x>0 for x in a])*100:.0f}% ／ 12か月 平均{np.mean(b)*100:+.1f}%（全期間{base12[m2].mean()*100:+.1f}%） 上昇{np.mean([x>0 for x in b])*100:.0f}%  n={len(a)}")
print("\n=== ②急落日の後の二番底（W字） ===")
for nm, s, th in (("S&P500 1日≤−4%", sp, -0.04), ("日経 1日≤−5%", nk, -0.05)):
    r = s.pct_change(); ev = []
    for d in s.index[(r <= th).values]:
        if not ev or (d - ev[-1]).days > 30: ev.append(d)
    for half in ("前半", "後半"):
        E = [d for d in ev if (d < mid) == (half == "前半")]; w = 0; reb = 0; f60 = []; dd = []
        for d in E:
            i = s.index.get_loc(d); low0 = s.iloc[i]
            nxt = s.iloc[i+1:i+6]
            if len(nxt) and nxt.max() / low0 - 1 >= 0.03:
                reb += 1
                j = i + 1 + int(np.argmax(nxt.values))
                if (s.iloc[j+1:j+41] < low0).any(): w += 1
            if i + 60 < len(s): f60.append(s.iloc[i+60] / low0 - 1)
            dd.append(s.iloc[i+1:i+61].min() / low0 - 1)
        if E: print(f"{nm} {half}: {len(E)}回 5日内に+3%反発{reb}回 → そのうち40日内に安値割れ（W字）{w}回（{w/max(reb,1)*100:.0f}%）／60日後 平均{np.mean(f60)*100:+.1f}%・上昇{np.mean([x>0 for x in f60])*100:.0f}%／60日内にさらに−10%以下 {np.mean([x<=-0.1 for x in dd])*100:.0f}%")
print("\n=== ③信用残高（FINRA） ===")
ok = False
for u in ("https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx", "https://www.finra.org/sites/default/files/margin-statistics.xlsx"):
    try:
        b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
        x = pd.read_excel(io.BytesIO(b)); print("取得", u, x.shape, list(x.columns)[:4]); ok = True; break
    except Exception as e: print("取得失敗", u, str(e)[:80])
if not ok: print("FINRAの信用残高を取得できず、③は検証不能")
