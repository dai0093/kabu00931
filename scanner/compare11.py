"""検証11：暴落の前日予測（網羅版）
判断時点＝前日 t-1 の場中（15:25の引け注文まで）。使うのはその時点で確定している値だけ：
 米国・為替・商品・アジア：t-1 より前に確定した終値（前夜まで）
 日経：t-2 までの終値 と t-1 の始値
 予定イベント：t-1 の夜の米国（CPI・FOMC・雇用統計）、t の日銀会合・SQ
結果：翌日 t の日経（t-1 引け → t 引け）。暴落＝ −2%以下（件数確保）と −3%以下
手法：①単独指標の閾値 ②ロジスティック回帰 ③勾配ブースティング（年ごとに過去だけで学習→翌年を予測）
     ④変動の大きさで保有比率を下げる（ボラティリティ・ターゲット） ⑤逆指値（検証10）との組み合わせ"""
import re, json, urllib.request, warnings
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score

def get(s, col="Close", start="2000-01-01"):
    try:
        x = yf.download(s, start=start, auto_adjust=False, progress=False)
        x.columns = [c[0] if isinstance(c, tuple) else c for c in x.columns]
        x.index = pd.to_datetime(x.index).tz_localize(None)
        return x[col].replace(0, np.nan).dropna()
    except Exception as e:
        print("取得失敗", s, e); return pd.Series(dtype=float)

log = []
nk, nko, nkh, nkl = get("^N225"), get("^N225", "Open"), get("^N225", "High"), get("^N225", "Low")
US = {k: get(s) for k, s in {"spx": "^GSPC", "ndx": "^NDX", "sox": "^SOX", "vix": "^VIX", "vix3m": "^VIX3M",
      "tnx": "^TNX", "irx": "^IRX", "hyg": "HYG", "ief": "IEF", "oil": "CL=F", "gold": "GC=F",
      "dxy": "DX-Y.NYB", "jpy": "JPY=X", "copper": "HG=F", "kospi": "^KS11", "twii": "^TWII", "hsi": "^HSI"}.items()}
for k, v in US.items(): log.append(f"{k}: {len(v)}日 {v.index[0].date() if len(v) else '-'}〜")

UA = {"User-Agent": "kabu00931 research script (github.com/dai0093/kabu00931)", "Accept": "text/html",
      "Accept-Language": "en-US,en;q=0.9"}
def fetch(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "ignore")
MON = {m: i for i, m in enumerate(["January","February","March","April","May","June","July","August",
                                     "September","October","November","December"], 1)}
DRX = r"(January|February|March|April|May|June|July|August|September|October|November|December)\.?\s+(\d{1,2}),\s+(\d{4})"
def dates_from(h): return {pd.Timestamp(int(y), MON[m], int(d)) for m, d, y in re.findall(DRX, h)}
cpi = set()
for u in ("https://www.bls.gov/bls/news-release/cpi.htm",
          "https://web.archive.org/web/2026/https://www.bls.gov/bls/news-release/cpi.htm",
          "https://web.archive.org/web/2025/https://www.bls.gov/schedule/news_release/cpi.htm"):
    try: cpi |= dates_from(fetch(u)); log.append(f"CPI {u[:60]} → 累計{len(cpi)}")
    except Exception as e: log.append(f"CPI取得失敗 {u[:60]} {e}")
fomc = set()
try:
    pages = [fetch("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")]
    for y in range(2000, 2021):
        try: pages.append(fetch(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm"))
        except Exception: pass
    for h in pages:
        for y, mo, d in re.findall(r"monetary(\d{4})(\d{2})(\d{2})a\d?\.htm", h):
            fomc.add(pd.Timestamp(int(y), int(mo), int(d)))
except Exception as e: log.append(f"FOMC取得失敗 {e}")
log.append(f"FOMC {len(fomc)}件")
boj = set()
for u in ["https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"] + \
         [f"https://www.boj.or.jp/en/mopo/mpmsche_minu/past/minu{y}.htm" for y in range(2005, 2026)] + \
         [f"https://www.boj.or.jp/en/mopo/mpmdeci/state_{y}/index.htm" for y in range(2005, 2027)]:
    try:
        h = fetch(u)
        for m, d, y in re.findall(DRX, h): boj.add(pd.Timestamp(int(y), MON[m], int(d)))
    except Exception: pass
# 日銀ページの日付は会合以外も含むので、声明文のリンク（kRYYMMDD等）に絞る
boj_stmt = set()
for u in [f"https://www.boj.or.jp/en/mopo/mpmdeci/state_{y}/index.htm" for y in range(2005, 2027)]:
    try:
        for yy, mm, dd in re.findall(r"k(\d{2})(\d{2})(\d{2})[a-z]?\.pdf", fetch(u)):
            boj_stmt.add(pd.Timestamp(2000 + int(yy), int(mm), int(dd)))
    except Exception: pass
log.append(f"日銀会合（声明文）{len(boj_stmt)}件")

def before(s, idx):   # idx の日より前に確定した最後の値
    if not len(s): return pd.Series(np.nan, index=idx)
    i = s.index.searchsorted(idx, side="left") - 1
    v = s.values
    return pd.Series([v[k] if k >= 0 else np.nan for k in i], index=idx)

ix = nk.index
f = pd.DataFrame(index=ix)
f["y"] = nk.shift(-1) / nk - 1                       # 翌日 t の騰落
nk2 = nk.shift(1)                                     # t-2 終値（判断日 t-1 から見て前日）
f["gap"] = nko.reindex(ix) / nk2 - 1
for n in (1, 5, 20): f[f"nk{n}"] = (nk / nk.shift(n) - 1).shift(1)
for n in (25, 75, 200): f[f"nk_ma{n}"] = (nk / nk.rolling(n).mean() - 1).shift(1)
r = nk.pct_change()
f["nk_vol20"] = (r.rolling(20).std() * np.sqrt(252)).shift(1)
f["nk_volr"] = (r.rolling(5).std() / r.rolling(60).std()).shift(1)
f["nk_dd60"] = (nk / nk.rolling(60).max() - 1).shift(1)
d = r.clip(lower=0).rolling(14).mean() / (-r.clip(upper=0)).rolling(14).mean()
f["nk_rsi"] = (100 - 100 / (1 + d)).shift(1)
f["nk_range"] = ((nkh - nkl) / nk).rolling(5).mean().reindex(ix).shift(1)
for k in ("spx", "ndx", "sox", "kospi", "twii", "hsi", "oil", "gold", "dxy", "copper", "jpy"):
    s = US[k]
    for n in (1, 5, 20):
        f[f"{k}{n}"] = before(s.pct_change(n), ix)
for k in ("tnx", "irx"):
    s = US[k] / (10 if US[k].median() > 20 and k == "tnx" else 1)
    f[f"{k}"] = before(s, ix); f[f"{k}_d5"] = before(s.diff(5), ix)
f["curve"] = f["tnx"] - f["irx"]
f["vix"] = before(US["vix"], ix); f["vix1"] = before(US["vix"].pct_change(), ix)
f["vix5"] = before(US["vix"].pct_change(5), ix)
f["vix_term"] = before((US["vix"] / US["vix3m"]).dropna(), ix)
cr = (US["hyg"] / US["ief"]).dropna()
f["credit5"] = before(cr.pct_change(5), ix); f["credit20"] = before(cr.pct_change(20), ix)
f["ev_cpi"] = [int(x in cpi) for x in ix]
f["ev_fomc"] = [int(x in fomc) for x in ix]
f["ev_nfp"] = [int(x.weekday() == 4 and x.day <= 7) for x in ix]
nxt = pd.Series(ix[1:].tolist() + [ix[-1] + pd.Timedelta(days=1)], index=ix)
f["ev_boj"] = [int(n in boj_stmt) for n in nxt]
f["ev_sq"] = [int(n.weekday() == 4 and 8 <= n.day <= 14) for n in nxt]
f["dow"] = [n.weekday() for n in nxt]
f["mon_end"] = [int(n.month != x.month) for x, n in zip(ix, nxt)]
f = f[f.index >= "2004-01-01"]
FE = [c for c in f.columns if c != "y"]
live = f.iloc[-1:].copy()          # 今日（判断日）の値：翌日の結果はまだ無い
f = f.dropna(subset=["y"])

# ---------- ① 単独指標：学習2005-2016で上位/下位5%を閾値に → 試験2017- ----------
TR, TE = pd.Timestamp("2005-01-01"), pd.Timestamp("2017-01-01")
def econ(sig, g, fee=0.0005):
    day = g.y.where(~sig, 0.0) - sig.astype(int) * 2 * fee
    eq, eqb = (1 + day).cumprod(), (1 + g.y).cumprod()
    return float(eq.iloc[-1] / eqb.iloc[-1] - 1), float((eq / eq.cummax() - 1).min()), float((eqb / eqb.cummax() - 1).min())
tr, te = f[(f.index >= TR) & (f.index < TE)], f[f.index >= TE]
L = log + ["", "## ① 単独指標（学習期間の上位/下位5%を超えた日の引けで逃げる）",
           "学習→試験の『翌日−2%以下の確率』（普段 学習{:.1f}% 試験{:.1f}%）と、ETF持ち続けに対する成績差".format(
               (tr.y <= -0.02).mean() * 100, (te.y <= -0.02).mean() * 100)]
single = []
for c in FE:
    if f[c].nunique() <= 2:
        cond_tr, cond_te = tr[c] == 1, te[c] == 1; lab = f"{c}=1"
    else:
        a = tr[c].dropna()
        if len(a) < 500: continue
        lo, hi = a.quantile(0.05), a.quantile(0.95)
        p_lo, p_hi = (tr.y[tr[c] <= lo] <= -0.02).mean(), (tr.y[tr[c] >= hi] <= -0.02).mean()
        if p_lo >= p_hi: cond_tr, cond_te, lab = tr[c] <= lo, te[c] <= lo, f"{c}≦{lo:.4g}"
        else: cond_tr, cond_te, lab = tr[c] >= hi, te[c] >= hi, f"{c}≧{hi:.4g}"
    if cond_tr.sum() < 20 or cond_te.sum() < 5: continue
    ptr, pte = (tr.y[cond_tr] <= -0.02).mean(), (te.y[cond_te] <= -0.02).mean()
    e_tr, e_te = econ(cond_tr, tr)[0], econ(cond_te, te)[0]
    single.append((lab, ptr, pte, int(cond_tr.sum()), int(cond_te.sum()), e_tr, e_te))
single.sort(key=lambda x: -x[1])
for lab, ptr, pte, ntr, nte, etr, ete in single[:25]:
    L.append(f"- {lab}：学習 {ptr*100:.1f}%（{ntr}日, 成績差{etr*100:+.0f}%） → 試験 {pte*100:.1f}%（{nte}日, 成績差{ete*100:+.0f}%）")
ok = [s for s in single if s[5] > 0 and s[6] > 0 and s[2] > (te.y <= -0.02).mean() * 2]
L.append(f"学習・試験とも成績がプラスで、試験でも暴落確率が普段の2倍以上：{len(ok)}個 → " + "、".join(s[0] for s in ok[:10]))

# ---------- ②③ 多変量モデル（年ごとのウォークフォワード） ----------
L.append("\n## ②③ 全指標を使うモデル（毎年、その年より前だけで学習して、その年を予測）")
X = f[FE]
res = {}
for name, mk in (("ロジスティック回帰", lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced"))),
                 ("勾配ブースティング", lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, class_weight="balanced"))):
    prob = pd.Series(np.nan, index=f.index); thr = {}
    for Y in range(2010, f.index[-1].year + 1):
        trn = f[(f.index < pd.Timestamp(Y, 1, 1)) & (f.index >= TR)]
        tst = f[(f.index >= pd.Timestamp(Y, 1, 1)) & (f.index < pd.Timestamp(Y + 1, 1, 1))]
        if not len(tst): continue
        Xt = trn[FE].fillna(trn[FE].median()); m = mk().fit(Xt, (trn.y <= -0.02).astype(int))
        ptr = m.predict_proba(Xt)[:, 1]
        thr[Y] = {q: float(np.quantile(ptr, q)) for q in (0.90, 0.95, 0.98)}
        prob[tst.index] = m.predict_proba(tst[FE].fillna(trn[FE].median()))[:, 1]
        if Y == f.index[-1].year: final_model, final_med = m, trn[FE].median()
    g = f[prob.notna()]; p = prob[g.index]
    auc2 = roc_auc_score((g.y <= -0.02).astype(int), p); auc3 = roc_auc_score((g.y <= -0.03).astype(int), p)
    L.append(f"### {name}：2010-2026の予測精度 AUC（0.5=当てずっぽう、1.0=完璧） −2%以下 {auc2:.3f} / −3%以下 {auc3:.3f}")
    for q in (0.90, 0.95, 0.98):
        sig = pd.Series([p[i] >= thr[i.year][q] for i in g.index], index=g.index)
        crash = g.y <= -0.03
        ex, mdd, mddb = econ(sig, g)
        L.append(f"- 上位{(1-q)*100:.0f}%で警告：警告{int(sig.sum())}日／翌日−3%以下 {int(crash.sum())}日のうち事前警告 {int((sig & crash).sum())}日"
                 f"（{(sig & crash).sum()/max(crash.sum(),1)*100:.0f}%）／警告日の翌日平均 {g.y[sig].mean()*100:+.2f}%（普段 {g.y.mean()*100:+.2f}%）"
                 f"／ETF持ち続けに対し {ex*100:+.1f}%／最大落ち込み {mddb*100:.1f}% → {mdd*100:.1f}%")
        for a, b in (("2010-01-01", "2017-01-01"), ("2017-01-01", "2027-01-01")):
            gg = g[(g.index >= a) & (g.index < b)]; ss = sig[gg.index]
            L.append(f"    {a[:4]}〜{int(b[:4])-1}：ETF比 {econ(ss, gg)[0]*100:+.1f}%")
    res[name] = (final_model, final_med, thr[max(thr)], p)
    # 2026年の暴落前日の確率
    L.append("  2026年 翌日−3%以下の前日の予測順位（その年の全日の中で上位何%か）：")
    p26 = p[p.index.year == 2026]
    for dt in g.index[(g.y <= -0.03) & (g.index.year == 2026)]:
        L.append(f"    {dt.date()}→翌日{g.y[dt]*100:+.1f}%：確率 {p[dt]*100:.1f}%（上位 {(p26 >= p[dt]).mean()*100:.0f}%）")
    try:
        imp = pd.Series(final_model[-1].coef_[0], index=FE) if name.startswith("ロジ") else None
        if imp is not None:
            L.append("  効いている指標（係数の大きい順、＋は暴落しやすい）：" + "、".join(f"{k}{v:+.2f}" for k, v in imp.reindex(imp.abs().sort_values(ascending=False).index)[:12].items()))
    except Exception: pass

# ---------- ④ ボラティリティ・ターゲット ----------
L.append("\n## ④ 変動が大きい時は保有を減らす（保有比率 = 目標変動率 ÷ 直近20日の変動率、上限100%）")
for tv in (0.15, 0.20, 0.25):
    w = (tv / f.nk_vol20).clip(upper=1.0).fillna(1.0)
    for a, b in ((TR, TE), (TE, pd.Timestamp("2100-01-01"))):
        g = f[(f.index >= a) & (f.index < b)]; ww = w[g.index]
        day = ww * g.y - ww.diff().abs().fillna(0) * 0.0005
        eq, eqb = (1 + day).cumprod(), (1 + g.y).cumprod()
        L.append(f"- 目標{tv*100:.0f}% {a.year}〜：ETF持ち続け {(eqb.iloc[-1]-1)*100:+.0f}% → {(eq.iloc[-1]-1)*100:+.0f}%／最大落ち込み {(eqb/eqb.cummax()-1).min()*100:.1f}% → {(eq/eq.cummax()-1).min()*100:.1f}%／平均保有 {ww.mean()*100:.0f}%")

# ---------- 今日の値（判断日＝最新日） ----------
L.append(f"\n## 最新の判断日 {live.index[-1].date()} の値")
for name, (m, med, th, p) in res.items():
    pr = float(m.predict_proba(live[FE].fillna(med))[:, 1][0])
    L.append(f"- {name}：翌日−2%以下の確率 {pr*100:.1f}%（警告ライン 上位5%={th[0.95]*100:.1f}% / 上位10%={th[0.90]*100:.1f}%）")
json.dump({"features": FE}, open("data/compare11_features.json", "w"))
open("data/compare11.md", "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
