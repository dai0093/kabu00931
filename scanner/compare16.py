"""検証16：金融機関の株価（私募信用運用会社・欧州銀・米銀・邦銀・BDC）の急落は、日経の下落を事前に示したか
判断時点＝日付d（米欧はdの終値、日本はdの引け）。結果＝dの次の東証営業日の日経
  A: 翌日 -3%以下   B: 翌日 -2%以下   C: dの終値から10営業日以内に最大 -7%以下の下落（ロジックツリーは遅い現象なのでCが本命）
指標：各群の中央値の 1日騰落 / 5日騰落 / 60日高値比、群内の警戒社数割合
合格条件：前半・後半の両方で、信号日の発生率が全期間の平均の1.3倍以上、かつ各半期の信号日が20日以上"""
import json, warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
G = {"PC": ["BX", "KKR", "APO", "CG", "ARES", "OWL", "TPG"], "EU": ["BNP.PA", "GLE.PA", "DBK.DE", "INGA.AS", "BARC.L", "HSBA.L", "SAN.MC", "ACA.PA", "UBSG.SW"],
     "US": ["JPM", "BAC", "C", "GS", "MS", "WFC"], "JP": ["8306.T", "8316.T", "8411.T"], "BDC": ["ARCC", "FSK", "BIZD"]}
def get(t):
    try:
        x = yf.download(t, start="2005-01-01", auto_adjust=False, progress=False)
        x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
        x.index = pd.to_datetime(x.index).tz_localize(None)
        return x["Close"].replace(0, np.nan).dropna()
    except Exception as e:
        print("取得失敗", t, e); return pd.Series(dtype=float)
nk = get("^N225")
P = {g: pd.DataFrame({t: get(t) for t in ts}) for g, ts in G.items()}
cal = nk.index
def feat(df):
    df = df.reindex(df.index.union(cal)).ffill(limit=3).reindex(cal)
    r1, r5 = df.pct_change(), df.pct_change(5)
    dd = df / df.rolling(60, min_periods=40).max() - 1
    n = df.notna().sum(axis=1)
    ok = n >= max(2, df.shape[1] // 2)
    o = pd.DataFrame({"d1": r1.median(axis=1) * 100, "d5": r5.median(axis=1) * 100, "dd": dd.median(axis=1) * 100,
                      "f1": ((r1 <= -0.04).sum(axis=1) / n), "f5": ((r5 <= -0.08).sum(axis=1) / n),
                      "fd": ((dd <= -0.20).sum(axis=1) / n)})
    return o.where(ok)
F = {g: feat(df) for g, df in P.items()}
nr = nk.pct_change().shift(-1)
fwd10 = pd.concat([nk.shift(-k) / nk - 1 for k in range(1, 11)], axis=1).min(axis=1)
Y = {"A_翌日-3%": nr <= -0.03, "B_翌日-2%": nr <= -0.02, "C_10日内-7%": fwd10 <= -0.07}
valid = nr.notna() & fwd10.notna()
mid = nk.index[valid][len(nk.index[valid]) // 2]
out, rules, lines = [], [], []
lines.append(f"期間 {nk.index[valid][0].date()}〜{nk.index[valid][-1].date()}  前半/後半の境 {mid.date()}  営業日{valid.sum()}")
for yn, y in Y.items():
    base = y[valid].mean(); lines.append(f"\n## {yn}  全期間の発生率 {base*100:.1f}%")
    for g, f in F.items():
        for c in f.columns:
            s = f[c]
            for th in ([-1, -1.5, -2, -3, -4, -5, -6, -8, -10, -15, -20, -25] if c in ("d1", "d5", "dd") else [0.1, 0.2, 0.3, 0.4, 0.5]):
                sig = (s <= th) if c in ("d1", "d5", "dd") else (s >= th)
                res = []
                for half in (valid & (nk.index <= mid), valid & (nk.index > mid)):
                    m = sig & half & s.notna()
                    n = int(m.sum()); r = float(y[m].mean()) if n else np.nan
                    b = float(y[half].mean()); res.append((n, r, b, r / b if n and b else np.nan))
                ok = all(x[0] >= 20 and x[3] >= 1.3 for x in res)
                row = dict(y=yn, g=g, f=c, th=th, n1=res[0][0], r1=res[0][1], l1=res[0][3], n2=res[1][0], r2=res[1][1], l2=res[1][3], ok=bool(ok))
                out.append(row)
                if ok: rules.append(row)
    sel = [r for r in rules if r["y"] == yn]
    lines.append(f"合格 {len(sel)}件（前後半とも発生率が平均の1.3倍以上・信号20日以上）")
    for r in sorted(sel, key=lambda r: -min(r["l1"], r["l2"]))[:15]:
        lines.append(f'  {r["g"]}.{r["f"]} {"≤" if r["f"] in ("d1","d5","dd") else "≥"}{r["th"]}: 前半 n={r["n1"]} 発生{r["r1"]*100:.0f}%(×{r["l1"]:.1f}) / 後半 n={r["n2"]} 発生{r["r2"]*100:.0f}%(×{r["l2"]:.1f})')
open("data/compare16.md", "w").write("\n".join(lines))
json.dump({"rules": rules, "all": out}, open("data/compare16.json", "w"), ensure_ascii=False, default=float)
print("\n".join(lines))

# ---- 合成判定（ロジックツリーに入れる判定そのもの）の検証 ----
LITR = [("EU", "d5", -15), ("US", "d1", -5), ("US", "d5", -10), ("JP", "d5", -10)]
NEARR = [("PC", "d5", -8), ("EU", "d1", -3), ("EU", "d5", -8), ("US", "d5", -5), ("JP", "d5", -6)]
def anyr(R):
    m = pd.Series(False, index=cal)
    for g, c, th in R: m |= (F[g][c] <= th).fillna(False)
    return m
lit, near = anyr(LITR), anyr(NEARR) & ~anyr(LITR)
lines2 = ["\n## 合成判定（点灯＝点灯条件のどれか／接近＝接近条件のみ）"]
for yn, y in Y.items():
    for nm, sig in (("点灯", lit), ("接近", near)):
        s = []
        for lab, half in (("前半", valid & (nk.index <= mid)), ("後半", valid & (nk.index > mid))):
            m = sig & half; n = int(m.sum()); b = float(y[half].mean())
            s.append(f"{lab} n={n} 発生{(y[m].mean()*100 if n else 0):.0f}%(×{(y[m].mean()/b if n and b else 0):.1f})")
        lines2.append(f"{yn} {nm}: " + " / ".join(s))
open("data/compare16.md", "a").write("\n".join(lines2)); print("\n".join(lines2))
