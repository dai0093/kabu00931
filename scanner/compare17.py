"""検証17：ロジックツリーの「点灯数」は、その後の日経の大きな下落（10営業日以内に-7%以下）を予測したか
使える過去データで再現できる点灯項目（過去判定可能なもの）:
  原油: Brent≥110   金利: 米10年≥5.0   逆イールド: 10年-2年<0   VIX: 25以上が3日連続   SOX下落: 52週高値から-20%以下
  金融機関株価: 点灯（compare16の合成判定）   NFCI≥0   HY OAS≥3.0 / IG OAS≥0.95（FRED。履歴が足りない期間は欠損）
判定日dの値だけを使い、結果は dの終値から10営業日以内の日経最大下落。前半/後半に分けて両方で確認。"""
import io, json, urllib.request, warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
exec(open("scanner/compare16.py").read().split("# ---- 合成判定")[0].split("out, rules, lines = [], [], []")[0])  # F, nk, cal, Y, valid, mid を再利用
def yf1(t):
    x = yf.download(t, start="2005-01-01", auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None); return x["Close"].dropna()
def fred(i):
    try:
        h = urllib.request.urlopen(urllib.request.Request(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={i}", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode()
        d = pd.read_csv(io.StringIO(h)); d.index = pd.to_datetime(d.iloc[:, 0]); return pd.to_numeric(d.iloc[:, 1], errors="coerce").dropna()
    except Exception as e:
        print("FRED失敗", i, e); return pd.Series(dtype=float)
al = lambda s: s.reindex(s.index.union(cal)).ffill(limit=5).reindex(cal)
brent, tnx, vix, sox = al(yf1("BZ=F")), al(yf1("^TNX")), al(yf1("^VIX")), al(yf1("^SOX"))
t10y2y, nfci, hy, ig = al(fred("T10Y2Y")), al(fred("NFCI")), al(fred("BAMLH0A0HYM2")), al(fred("BAMLC0A0CM"))
print("取得日数", {k: int(v.notna().sum()) for k, v in dict(brent=brent, tnx=tnx, vix=vix, sox=sox, t10y2y=t10y2y, nfci=nfci, hy=hy, ig=ig).items()})
fin = pd.Series(False, index=cal)
for g, c, th in [("EU", "d5", -15), ("US", "d1", -5), ("US", "d5", -10), ("JP", "d5", -10)]: fin |= (F[g][c] <= th).fillna(False)
v25 = (vix >= 25).astype(int).rolling(3).sum() >= 3
items = {"原油≥110": brent >= 110, "米10年≥5.0": tnx >= 5.0, "逆イールド": t10y2y < 0, "VIX25×3日": v25,
         "SOX高値比≤-20%": (sox / sox.rolling(252, min_periods=200).max() - 1) <= -0.20, "金融機関株価": fin,
         "NFCI≥0": nfci >= 0, "HY≥3.0": hy >= 3.0, "IG≥0.95": ig >= 0.95}
I = pd.DataFrame({k: v.fillna(False) for k, v in items.items()})
for nm, cols in (("A: 全項目", list(I.columns)), ("B: 長期履歴のある項目のみ（HY・IG・NFCIを除く）", [c for c in I.columns if c not in ("HY≥3.0", "IG≥0.95", "NFCI≥0")])):
    n = I[cols].sum(axis=1)
    print(f"\n## {nm}  項目数{len(cols)}")
    y = Y["C_10日内-7%"]
    print(f"全期間の発生率 {y[valid].mean()*100:.1f}%")
    for k in range(1, 6):
        r = []
        for lab, half in (("前半", valid & (nk.index <= mid)), ("後半", valid & (nk.index > mid))):
            m = (n >= k) & half; c = int(m.sum()); b = float(y[half].mean())
            r.append(f"{lab} {c}日 発生{(y[m].mean()*100 if c else 0):.0f}%(×{(y[m].mean()/b if c and b else 0):.1f})")
        print(f"点灯{k}個以上: " + " / ".join(r))
    print("今日（最新日）の点灯:", [c for c in cols if I[c].iloc[-1]], "→", int(n.iloc[-1]), "個")
