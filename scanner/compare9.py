"""検証9：前日の後場（15:25まで）に判断して、引けで売る／買い戻す
判断時点で分かる情報だけ使う：
- 前夜までの米国（SOX・VIX・米10年）＝ t-2 の米国終値まで
- 当日の日経の寄り（t-1 の始値）、日経の25日線（t-2 終値まで）
- 今夜の米国の予定イベント：CPI（BLSの公表日）、FOMC（FRBの日程）、雇用統計（第1金曜）
運用：警告の日（t-1）の大引けでETFを売り、翌日（t）の大引けで買い戻す → 翌日 t の1日分を丸ごと避ける
学習 2005-2016（イベントは取れた年から）／試験 2017-"""
import re, urllib.request
import pandas as pd, yfinance as yf

def get(s, col="Close"):
    x = yf.download(s, start="2003-01-01", auto_adjust=False, progress=False)
    x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None)
    return x[col].dropna()

nk, nko = get("^N225"), get("^N225", "Open")
sox, vix, tnx = get("^SOX"), get("^VIX"), get("^TNX")
if tnx.median() > 20: tnx = tnx / 10
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def fetch(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "ignore")

MON = {m: i for i, m in enumerate(["January","February","March","April","May","June","July","August",
                                     "September","October","November","December"], 1)}
log = []
cpi = set()
try:
    h = fetch("https://www.bls.gov/bls/news-release/cpi.htm")
    for m, d, y in re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})", h):
        cpi.add(pd.Timestamp(int(y), MON[m], int(d)))
    log.append(f"CPI公表日 {len(cpi)}件（BLS）")
except Exception as e:
    log.append(f"CPI公表日の取得失敗 {e}")
fomc = set()
try:
    pages = [fetch("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")]
    for y in range(2005, 2021):
        try: pages.append(fetch(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm"))
        except Exception: pass
    for h in pages:
        for y, mo, d in re.findall(r"monetary(\d{4})(\d{2})(\d{2})a\.htm", h):   # 声明文のリンク＝決定日
            fomc.add(pd.Timestamp(int(y), int(mo), int(d)))
    log.append(f"FOMC決定日 {len(fomc)}件（FRB）")
except Exception as e:
    log.append(f"FOMCの取得失敗 {e}")
def nfp(d):   # 第1金曜（近似）
    return d.weekday() == 4 and d.day <= 7

def before(s, idx):
    i = s.index.searchsorted(idx, side="left") - 1
    return pd.Series([s.iloc[k] if k >= 0 else float("nan") for k in i], index=idx)

# 行 = 判断日 t-1（東京）。結果 = 翌日 t の日経の騰落（t-1 引け → t 引け）
f = pd.DataFrame(index=nk.index)
f["next"] = nk.shift(-1) / nk - 1
f["gap"] = nko.reindex(nk.index) / nk.shift(1) - 1                  # 当日の寄り（判断時に分かる）
f["sox1"] = before(sox.pct_change(), f.index)                        # 前夜の米国
f["sox5"] = before(sox.pct_change(5), f.index)
f["vix"] = before(vix, f.index)
f["vix1"] = before(vix.pct_change(), f.index)
f["below"] = (nk < nk.rolling(25).mean()).shift(1)
f["nk5"] = (nk / nk.shift(5) - 1).shift(1)
# 今夜（東京 t-1 の夜）の米国日付 = t-1 と同じ暦日
f["ev_cpi"] = [d in cpi for d in f.index]
f["ev_fomc"] = [d in fomc for d in f.index]
f["ev_nfp"] = [nfp(d) for d in f.index]
f["ev_any"] = f.ev_cpi | f.ev_fomc | f.ev_nfp
f = f.dropna(subset=["next", "gap", "sox1", "vix", "nk5"])

C = {
 "今夜CPI": lambda r: r.ev_cpi, "今夜FOMC": lambda r: r.ev_fomc, "今夜雇用統計": lambda r: r.ev_nfp,
 "今夜 重要指標のどれか": lambda r: r.ev_any,
 "寄り −1%以下": lambda r: r.gap <= -0.01, "寄り −2%以下": lambda r: r.gap <= -0.02,
 "前夜SOX −3%以下": lambda r: r.sox1 <= -0.03, "SOX5日 −8%以下": lambda r: r.sox5 <= -0.08,
 "VIX 25以上": lambda r: r.vix >= 25, "VIX前日比 +20%以上": lambda r: r.vix1 >= 0.2,
 "日経5日 −4%以下": lambda r: r.nk5 <= -0.04,
 "今夜CPI かつ 日経25日線の下": lambda r: r.ev_cpi and bool(r.below),
 "今夜CPI かつ SOX5日 −3%以下": lambda r: r.ev_cpi and r.sox5 <= -0.03,
 "今夜 重要指標 かつ 日経5日マイナス": lambda r: r.ev_any and r.nk5 < 0,
 "今夜 重要指標 かつ VIX前日比プラス": lambda r: r.ev_any and r.vix1 > 0,
 "寄り −1%以下 かつ 日経25日線の下": lambda r: r.gap <= -0.01 and bool(r.below),
 "SOX5日 −8%以下 または 寄り −2%以下": lambda r: r.sox5 <= -0.08 or r.gap <= -0.02,
}
FEE = 0.0005
def ev(sig, a, b):
    g, s = f[(f.index >= a) & (f.index < b)], sig[(sig.index >= a) & (sig.index < b)]
    crash = g.next <= -0.03
    day = g.next.where(~s, 0.0) - s.astype(int) * 2 * FEE
    eq, eqb = (1 + day).cumprod(), (1 + g.next).cumprod()
    on = int(s.sum()); hit = int((s & crash).sum())
    return {"crash": int(crash.sum()), "hit": hit, "on": on, "prec": hit / on if on else 0,
            "base": float(crash.mean()), "avg": float(g.next[s].mean()) if on else 0.0,
            "st": float(eq.iloc[-1] - 1), "bh": float(eqb.iloc[-1] - 1),
            "mdd": float((eq / eq.cummax() - 1).min()), "mddb": float((eqb / eqb.cummax() - 1).min())}
TR, TE, END = pd.Timestamp("2005-01-01"), pd.Timestamp("2017-01-01"), f.index[-1] + pd.Timedelta(days=1)
rows = []
for nm, fn in C.items():
    sig = f.apply(fn, axis=1).astype(bool)
    rows.append((nm, sig, ev(sig, TR, TE), ev(sig, TE, END)))
rows.sort(key=lambda x: -(x[2]["st"] - x[2]["bh"]))
L = log + [f"判断：t-1 の後場（15:25まで）→ 引けで売り、翌日 t の引けで買い戻し。暴落＝翌日の日経 −3%以下", ""]
for nm, sig, a, b in rows:
    L.append(f"### {nm}")
    for lab, r in (("学習", a), ("試験", b)):
        L.append(f"{lab}：警告{r['on']}日→翌日暴落{r['hit']}日（当たり{r['prec']*100:.1f}%、普段の暴落率{r['base']*100:.1f}%）"
                 f"／暴落{r['crash']}日中 {r['hit']}日を事前に回避／警告翌日の平均 {r['avg']*100:+.2f}%"
                 f"／ETFのみ {r['bh']*100:+.1f}% → 警告で逃げる {r['st']*100:+.1f}%（差 {(r['st']-r['bh'])*100:+.1f}pt）"
                 f"／最大落ち込み {r['mddb']*100:.1f}% → {r['mdd']*100:.1f}%")
best = rows[0]
L.append(f"\n学習で一番良かった：{best[0]} → 試験の差 {(best[3]['st']-best[3]['bh'])*100:+.1f}pt → "
         + ("予測出来た" if best[3]["st"] > best[3]["bh"] else "予測出来なかった"))
L.append("\n## 2026年の暴落の前日に、判断時点で警告が出ていたか")
for dt in f.index[f.next <= -0.03]:
    if dt.year < 2026: continue
    r = f.loc[dt]; on = [nm for nm, sig, a, b in rows if sig.get(dt, False)]
    L.append(f"判断日 {dt.date()}（翌日 {r.next*100:+.1f}%）：今夜CPI{'○' if r.ev_cpi else '×'} FOMC{'○' if r.ev_fomc else '×'} 雇用{'○' if r.ev_nfp else '×'} "
             f"寄り{r.gap*100:+.1f}% 前夜SOX{r.sox1*100:+.1f}% → {'、'.join(on[:6]) or '警告なし'}")
r = f.loc[pd.Timestamp("2026-10-14")] if pd.Timestamp("2026-10-14") in f.index else None
if r is not None:
    L.append(f"\n10/14（判断日）→ 10/15：今夜CPI{'○' if r.ev_cpi else '×'} 寄り{r.gap*100:+.1f}% 前夜SOX{r.sox1*100:+.1f}% VIX{r.vix:.1f}")
L.append("\n今後のCPI予定（取得分）：" + "、".join(str(d.date()) for d in sorted(cpi) if d >= pd.Timestamp.now().normalize())[:200])
L.append("今後のFOMC予定（取得分）：" + "、".join(str(d.date()) for d in sorted(fomc) if d >= pd.Timestamp.now().normalize()))
open("data/compare9.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
