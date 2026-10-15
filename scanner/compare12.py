"""検証12：米国の重要指標の『事前予測値』で、上振れ／下振れと日経の暴落を予測出来たか
データ：investing.com 経済指標の履歴（予想・結果、2001年〜）、クリーブランド連銀CPIナウキャスト（2013年〜）
A. 発表翌日の日経：暴落しやすいか（普段との比較）
B. 予想との差（サプライズ）の向きで、翌日の日経はどう動いたか（反応の大きさ）
C. 事前に向きを当てられたか：
   - CPI：クリーブランド連銀ナウキャスト − 市場予想 の符号 → 実際のサプライズの符号
   - 雇用統計：ADP（2日前）のサプライズの符号 → 雇用統計のサプライズの符号
   - 前回のサプライズの符号 → 今回（同じ向きが続くか）
D. 予測が『悪い向き』の時だけ発表前の引けで逃げた場合の成績"""
import json, urllib.request, time
import numpy as np, pandas as pd, yfinance as yf
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
     "Accept": "application/json", "Origin": "https://www.investing.com", "Referer": "https://www.investing.com/"}
EV = {56: ("コアCPI 前月比", +1), 733: ("CPI 前年比", +1), 69: ("CPI 前月比", +1), 227: ("雇用統計 雇用者数", -2),
      300: ("失業率", -2), 61: ("コアPCE 前月比", +1), 173: ("ISM製造業", -2), 256: ("小売売上高", -2),
      238: ("PPI 前月比", +1), 1: ("ADP雇用者数", -2), 168: ("FOMC 政策金利", +1)}
# 符号 +1：上振れが株に悪い（インフレ・利上げ） / -2：景気指標（どちらの向きも悪材料になり得るので両方見る）
def occ(eid):
    rows, cur = [], None
    for _ in range(6):
        u = f"https://endpoints.investing.com/pd-instruments/v1/calendars/economic/events/{eid}/occurrences?domain_id=1&limit=300"
        if cur: u += f"&cursor={cur}"
        try: d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60).read())
        except Exception as e: print("取得失敗", eid, e); break
        rows += d.get("occurrences", []); cur = d.get("next_page_cursor")
        if not cur: break
        time.sleep(1)
    df = pd.DataFrame(rows)
    if df.empty: return df
    df["t"] = pd.to_datetime(df.occurrence_time).dt.tz_localize(None)
    return df.drop_duplicates("occurrence_id").sort_values("t")
E = {k: occ(k) for k in EV}

nk = yf.download("^N225", start="2000-01-01", auto_adjust=False, progress=False)
nk.columns = [c[0] if isinstance(c, tuple) else c for c in nk.columns]
nk.index = pd.to_datetime(nk.index).tz_localize(None)
c = nk.Close.replace(0, np.nan).dropna(); r = c.pct_change()
def tokyo_after(t):  # 米国発表（UTC）のあとに来る最初の東京の取引日 と その前日（逃げる判断日）
    d = (t + pd.Timedelta(hours=9)).normalize()     # JST日付
    i = c.index.searchsorted(d + pd.Timedelta(days=1)) if t.hour + 9 >= 24 or True else None
    # 米国の発表は日本時間の夜（21:30〜翌4:00）。翌朝以降の最初の東京取引日
    i = c.index.searchsorted((t + pd.Timedelta(hours=9)).normalize() + pd.Timedelta(days=1))
    if (t + pd.Timedelta(hours=9)).hour < 9:   # 日本時間の早朝発表（FOMC 3:00等）は当日
        i = c.index.searchsorted((t + pd.Timedelta(hours=9)).normalize())
    return (c.index[i], c.index[i - 1]) if 0 < i < len(c) else (None, None)
base2, base3 = (r <= -0.02).mean(), (r <= -0.03).mean()
L = [f"日経の普段の確率（2001〜）：−2%以下 {base2*100:.1f}% / −3%以下 {base3*100:.1f}% / 平均の振れ幅 {r.abs().mean()*100:.2f}%", ""]
L.append("## A・B 発表翌日の日経（全回）と、サプライズの向き別")
rec = {}
for eid, (nm, sg) in EV.items():
    df = E[eid]
    if df.empty or "actual" not in df: L.append(f"- {nm}：データなし"); continue
    df = df.dropna(subset=["actual"]).copy()
    df["fc"] = df.get("forecast")
    df["sur"] = df.actual - df.fc
    nxt = [tokyo_after(t) for t in df.t]
    df["day"] = [a for a, b in nxt]; df["eve"] = [b for a, b in nxt]
    df = df.dropna(subset=["day"])
    df["nk"] = r.reindex(df.day).values
    rec[eid] = df
    v = df.nk.dropna()
    L.append(f"### {nm}（{len(v)}回、{df.t.min().date()}〜）")
    L.append(f"翌日の日経：−2%以下 {(v<=-0.02).mean()*100:.1f}%（普段{base2*100:.1f}%） / −3%以下 {(v<=-0.03).mean()*100:.1f}%（普段{base3*100:.1f}%） / 平均の振れ幅 {v.abs().mean()*100:.2f}%")
    for lab, m in (("上振れ", df.sur > 0), ("予想どおり", df.sur == 0), ("下振れ", df.sur < 0)):
        x = df.nk[m].dropna()
        if len(x): L.append(f"  {lab} {len(x)}回：翌日平均 {x.mean()*100:+.2f}% / −2%以下 {(x<=-0.02).mean()*100:.1f}%")

# C. 事前に向きを当てられたか
L.append("\n## C. サプライズの向きを事前に当てられたか")
# C1 クリーブランド連銀ナウキャスト
try:
    req = urllib.request.Request("https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json", headers={"User-Agent": H["User-Agent"]})
    J = json.loads(urllib.request.urlopen(req, timeout=120).read())
    now = {}
    for ch in J:
        y, m = map(int, ch["chart"]["subcaption"].split("-"))
        for ds in ch["dataset"]:
            vals = [float(p["value"]) for p in ds["data"] if p.get("value") not in ("", None)]
            if vals: now[(ds["seriesname"], y, m)] = vals[-1]
    L.append(f"ナウキャスト：{len(now)}系列×月")
    MON = {mm: i for i, mm in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}
    for eid, sname in ((56, "Core CPI Inflation"), (69, "CPI Inflation")):
        if eid not in rec: continue
        df = rec[eid].copy()
        ym = [(t.year - (1 if MON.get(p, 1) > t.month else 0), MON.get(p)) for t, p in zip(df.t, df.reference_period)]
        df["nc"] = [now.get((sname, y, m)) for y, m in ym]
        df = df.dropna(subset=["nc", "fc"])
        df["pred"] = np.sign(np.round(df.nc, 2) - df.fc)
        k = df[(df.pred != 0) & (df.sur != 0)]
        hit = (np.sign(k.sur) == k.pred).mean() if len(k) else float("nan")
        L.append(f"- {EV[eid][0]}：ナウキャスト−予想 の向きで当たり {hit*100:.1f}%（{len(k)}回、50%が当てずっぽう）")
        up = k[k.pred > 0]
        L.append(f"  ナウキャストが上振れを示した {len(up)}回：実際に上振れ {(up.sur>0).mean()*100:.1f}% / 翌日の日経 平均 {up.nk.mean()*100:+.2f}% / −2%以下 {(up.nk<=-0.02).mean()*100:.1f}%")
        last = df.iloc[-1]
        L.append(f"  直近（{last.t.date()}）：予想 {last.fc} / ナウキャスト {last.nc:.2f} / 実際 {last.actual} → {'当たり' if np.sign(last.sur)==last.pred else '外れ'}")
        rec[f"nc{eid}"] = df
except Exception as e:
    L.append(f"ナウキャストの取得失敗 {e}")
# C2 ADP → 雇用統計
if 1 in rec and 227 in rec:
    a, n = rec[1][["t", "sur"]].copy(), rec[227][["t", "sur", "nk", "eve", "day"]].copy()
    n["adp"] = [a.sur[(a.t < t) & (a.t > t - pd.Timedelta(days=7))].iloc[-1] if ((a.t < t) & (a.t > t - pd.Timedelta(days=7))).any() else np.nan for t in n.t]
    k = n.dropna(subset=["adp"]); k = k[(k.adp != 0) & (k.sur != 0)]
    L.append(f"- 雇用統計：ADPのサプライズの向き → 雇用統計の向き 当たり {(np.sign(k.adp)==np.sign(k.sur)).mean()*100:.1f}%（{len(k)}回）")
# C3 前回と同じ向き
for eid in (56, 69, 733, 227, 238, 61, 256):
    if eid not in rec: continue
    s = np.sign(rec[eid].sur.dropna()); s = s[s != 0]
    L.append(f"- {EV[eid][0]}：前回と同じ向きになった割合 {(s.values[1:] == s.values[:-1]).mean()*100:.1f}%（{len(s)-1}回）")

# D. 『悪い向き』予測の時だけ前日の引けで逃げる（CPI）
L.append("\n## D. ナウキャストが『上振れ』を示したCPIの前日だけ、引けでETFを売り翌日引けで買い戻す")
for eid in (56, 69):
    k = rec.get(f"nc{eid}")
    if k is None: continue
    esc = k[k.pred > 0]
    saved = -esc.nk.dropna().sum(); cost = len(esc) * 0.001
    L.append(f"- {EV[eid][0]}：{len(esc)}回逃げた → 避けた値動きの合計 {saved*100:+.1f}%（プラスなら得）、手数料 {cost*100:.1f}% → 差引 {(saved-cost)*100:+.1f}%")
    for a, b in (("2013", "2019"), ("2020", "2026")):
        e2 = esc[(esc.t.dt.year >= int(a)) & (esc.t.dt.year <= int(b))]
        L.append(f"   {a}〜{b}：{len(e2)}回 差引 {(-e2.nk.dropna().sum() - len(e2)*0.001)*100:+.1f}%")

# 今後の予定（予想値つき）
L.append("\n## 今後の予定（日本時間）")
fut = []
for eid, (nm, sg) in EV.items():
    df = E[eid]
    if df.empty: continue
    for _, o in df[df.t >= pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(hours=12)].iterrows():
        fut.append((o.t + pd.Timedelta(hours=9), nm, o.get("forecast"), o.get("previous")))
for t, nm, fc, pv in sorted(fut)[:25]:
    L.append(f"- {t:%m/%d %H:%M} {nm}：予想 {fc} / 前回 {pv}")
json.dump([{"jst": str(t), "name": nm, "forecast": None if pd.isna(fc) else fc, "previous": None if pd.isna(pv) else pv}
           for t, nm, fc, pv in sorted(fut)], open("data/events.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
open("data/compare12.md", "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
