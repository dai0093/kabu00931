import json
import urllib.request
import urllib.parse
import os
"""期限切れの日次・週次系列を、自動で取れるものだけ最新化する（data/series_live.json）。
VIX（Yahoo、確定終値のみ）・VIX25超の連続日数・米10年（Yahoo）、HY/IG OAS・NFCI・10年-2年（FRED。失敗したら米財務省の利回り曲線で10年-2年だけ補う）。
取れなかった系列は何も書かない（推測値で埋めない）。"""
import io, json, urllib.request, warnings
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
JST = timezone(timedelta(hours=9)); out = {}
def get(u, t=25):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode("utf-8", "ignore")
def settled(s):
    n = datetime.now(ZoneInfo("America/New_York"))
    return s.iloc[:-1] if len(s) and s.index[-1].date() == n.date() and n.hour + n.minute / 60 < 16.5 else s
def y(t):
    x = yf.download(t, period="3mo", auto_adjust=False, progress=False)["Close"].squeeze().dropna()
    x.index = pd.to_datetime(x.index).tz_localize(None); return settled(x)
try:
    v = y("^VIX"); d = str(v.index[-1].date()); n = 0
    for z in reversed(v.values):
        if z >= 25: n += 1
        else: break
    out["vix"] = {"value": round(float(v.iloc[-1]), 2), "observedAt": d, "change": f"前日比 {float(v.iloc[-1]-v.iloc[-2]):+.2f}（Yahoo確定終値）", "source": "https://finance.yahoo.com/quote/%5EVIX/"}
    out["vixd"] = {"value": n, "observedAt": d, "change": "VIX25以上の連続日数（確定終値から計算）", "source": "https://finance.yahoo.com/quote/%5EVIX/"}
    t = y("^TNX"); out["us10"] = {"value": round(float(t.iloc[-1]), 3), "observedAt": str(t.index[-1].date()), "change": f"前日比 {float(t.iloc[-1]-t.iloc[-2]):+.3f}（Yahoo確定終値）", "source": "https://finance.yahoo.com/quote/%5ETNX/"}
except Exception as e:
    print("Yahoo失敗", e)
def fred(i):
    for k in range(1):
        try:
            d = pd.read_csv(io.StringIO(get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={i}", 20)))
            d.index = pd.to_datetime(d.iloc[:, 0]); s = pd.to_numeric(d.iloc[:, 1], errors="coerce").dropna()
            if len(s): return s
        except Exception as e:
            print("FRED失敗", i, k, str(e)[:80])
    return None
for sid, fid, unit in (("hy", "BAMLH0A0HYM2", "%"), ("ig", "BAMLC0A0CM", "%"), ("nfci", "NFCI", ""), ("t10y2y", "T10Y2Y", "")):
    s = fred(fid)
    if s is not None:
        out[sid] = {"value": round(float(s.iloc[-1]), 3), "observedAt": str(s.index[-1].date()),
                    "change": f"直近比 {float(s.iloc[-1]-s.iloc[-2]):+.3f}（FRED）", "source": f"https://fred.stlouisfed.org/series/{fid}"}
if "t10y2y" not in out:
    try:
        yr = datetime.now(JST).year
        d = pd.read_csv(io.StringIO(get(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{yr}/all?type=daily_treasury_yield_curve&field_tdr_date_value={yr}&page&_format=csv")))
        d["Date"] = pd.to_datetime(d["Date"]); d = d.sort_values("Date")
        r = d.iloc[-1]; out["t10y2y"] = {"value": round(float(r["10 Yr"] - r["2 Yr"]), 3), "observedAt": str(r["Date"].date()),
                                          "change": "財務省の利回り曲線（10年−2年）", "source": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve"}
    except Exception as e:
        print("財務省失敗", str(e)[:80])

# ---- 2026-11-04 追加：手入力・FREDの代わりにYahooから自動で取る（検証46） ----
def yy(t, per="3y", adj=False):
    x = yf.download(t, period=per, auto_adjust=adj, progress=False)["Close"].squeeze().dropna()
    x.index = pd.to_datetime(x.index).tz_localize(None); return settled(x)
try:
    sx = yy("^SOX", "2y"); dd = float((sx.iloc[-1] / sx.iloc[-250:].max() - 1) * 100)
    out["soxdd"] = {"value": round(dd, 1), "observedAt": str(sx.index[-1].date()), "change": "250日高値比（Yahoo）", "source": "https://finance.yahoo.com/quote/%5ESOX/"}
    # SOXが高値から−40%超：2009年以降に例のない領域（岡崎氏資料の循環表。前半のみ例あり→判定には入れず注意のみ）
    _hi = float(sx.max()); _ddall = (float(sx.iloc[-1]) / _hi - 1) * 100
    out["sox40"] = {"value": round(_ddall, 1), "on": _ddall <= -40, "observedAt": str(sx.index[-1].date())}
    try:
        _sf = "data/sox40_sent.json"; _was = json.load(open(_sf)).get("on", False) if os.path.exists(_sf) else False
        if _ddall <= -40 and not _was and os.environ.get("NTFY_TOPIC"):
            _q = urllib.parse.urlencode({"title": "【注意】SOXが高値から−40%超", "priority": "4", "click": "https://dai0093.github.io/kabu00931/signals.html"})
            _b = f"SOX {float(sx.iloc[-1]):,.0f}（高値{_hi:,.0f}から{_ddall:.1f}%）。2009年以降に例のない下げ。1997〜2008年に−40%を超えた5回は最終的に−42〜−69%まで下げた（後半の例がなく未検証のため目標%には入れない）"
            urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{os.environ['NTFY_TOPIC']}?{_q}", data=_b.encode("utf-8"), method="POST"), timeout=30)
        json.dump({"on": _ddall <= -40}, open(_sf, "w"))
    except Exception as _e: print("sox40通知失敗", _e)
    out["sox"] = {"value": round(float(sx.iloc[-1]), 2), "observedAt": str(sx.index[-1].date()), "change": "", "source": "https://finance.yahoo.com/quote/%5ESOX/"}
except Exception as e: print("SOX失敗", e)
try:
    nf = yy("NKD=F", "3mo"); out["nkf"] = {"value": round(float((nf.iloc[-1] / nf.iloc[-2] - 1) * 100), 2), "observedAt": str(nf.index[-1].date()), "change": "CME日経先物 前日比%（Yahoo）", "source": "https://finance.yahoo.com/quote/NKD%3DF/"}
except Exception as e: print("日経先物失敗", e)
try:
    hy = yy("HYG", "4y", True) / yy("IEF", "4y", True); vix = yy("^VIX", "4y"); bk = yy("^BKX", "4y")
    h20 = hy.pct_change(20); b20 = bk.pct_change(20)
    z = lambda s: (s - s.rolling(500, min_periods=250).mean()) / s.rolling(500, min_periods=250).std()
    fs = ((z(vix) + z(-h20) + z(-b20)) / 3).dropna()
    out["hy_px"] = {"value": round(float(h20.dropna().iloc[-1] * 100), 2), "observedAt": str(h20.dropna().index[-1].date()), "change": "HYG÷IEF 20日変化%（HY OASの代替・検証46）", "source": "https://finance.yahoo.com/quote/HYG/"}
    out["nfci_px"] = {"value": round(float(fs.iloc[-1]), 2), "observedAt": str(fs.index[-1].date()), "change": "金融ストレス合成（VIX・社債・米銀のzスコア平均、NFCIの代替・検証46）", "source": "https://finance.yahoo.com/quote/%5EVIX/"}
    pcm = pd.concat([yy(t, "3mo").pct_change(5) for t in ("BX", "APO", "KKR", "ARES")], axis=1).median(axis=1).dropna()
    out["pc_px"] = {"value": round(float(pcm.iloc[-1] * 100), 2), "observedAt": str(pcm.index[-1].date()), "change": "私募信用運用会社株（BX・APO・KKR・ARES）5日中央値%（代替・検証46）", "source": "https://finance.yahoo.com/quote/BX/"}
except Exception as e: print("代替指標失敗", e)
try:  # 欧州ソブリン：ECBの長期金利（月次）で仏−独スプレッド
    def ecb(c):
        d = pd.read_csv(io.StringIO(get(f"https://data-api.ecb.europa.eu/service/data/IRS/M.{c}.L.L40.CI.0000.EUR.N.Z?format=csvdata&lastNObservations=3")))
        return d[["TIME_PERIOD", "OBS_VALUE"]].dropna().iloc[-1]
    fr, de = ecb("FR"), ecb("DE")
    out["frspread_m"] = {"value": round((float(fr.OBS_VALUE) - float(de.OBS_VALUE)) * 100, 1), "observedAt": str(fr.TIME_PERIOD) + "-28", "change": "仏−独10年 月次平均（ECB）", "source": "https://data.ecb.europa.eu/"}
except Exception as e: print("ECB失敗", str(e)[:80])
out["_at"] = datetime.now(JST).isoformat(timespec="minutes")
json.dump(out, open("data/series_live.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: (v["value"], v["observedAt"]) for k, v in out.items() if k != "_at"})
# run 21:50:50
