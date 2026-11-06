"""個別株の急落検知（取引時間中・引け後）：監視93銘柄で前日比 −7% 以下を検知し、ニュースの見出しを添えて通知。
先物・指数では分からない個別の悪材料（接収・不祥事・業績急変など）を拾うため。data/jumps.json"""
import json, os, sys, urllib.parse, urllib.request, re, html
from datetime import datetime, timedelta, timezone
import pandas as pd, yfinance as yf
sys.path.insert(0, os.path.dirname(__file__))
from universe import STOCKS
JST = timezone(timedelta(hours=9)); TH = -7.0
tk = [c + ".T" for c in STOCKS]
d = yf.download(tk, period="5d", interval="1d", auto_adjust=False, progress=False)["Close"]
m = yf.download(tk, period="1d", interval="5m", auto_adjust=False, progress=False)["Close"]
hits = []
for c, nm in STOCKS.items():
    t = c + ".T"
    try:
        s = d[t].dropna(); last = float(m[t].dropna().iloc[-1]) if t in m and m[t].notna().any() else float(s.iloc[-1])
        today = datetime.now(JST).date()
        prev = float(s[s.index.date < today].iloc[-1]) if (s.index.date < today).any() else float(s.iloc[-2])
        r = (last / prev - 1) * 100
        if r <= TH: hits.append({"code": c, "name": nm, "r": round(r, 1), "price": round(last), "prev": round(prev)})
    except Exception:
        pass
    # 今日、他の銘柄は売買があるのにこの銘柄だけ売買が成立していない＝ストップ高・安の気配や売買停止の可能性
    try:
        today = datetime.now(JST).date(); ms = m[t].dropna() if t in m else pd.Series(dtype=float)
        others = m.dropna(how="all").index; trading = len(others) and pd.Timestamp(others[-1]).tz_convert(JST).date() == today
        if trading and (len(ms) == 0 or pd.Timestamp(ms.index[-1]).tz_convert(JST).date() < today):
            s = d[t].dropna(); prev = float(s[s.index.date < today].iloc[-1])
            hits.append({"code": c, "name": nm, "r": -99.0, "price": None, "prev": round(prev), "note": "本日まだ売買不成立（ストップ気配・売買停止の可能性）"})
    except Exception:
        pass
def news(q):
    try:
        u = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "ja", "gl": "JP", "ceid": "JP:ja"})
        x = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore")
        its = re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>", x, re.S)[:3]
        return [{"title": html.unescape(a), "url": b, "date": c} for a, b, c in its]
    except Exception as e:
        return []
for h in hits: h["news"] = news(f"{h['name']} 株価")
# 引け後・夜間：PTS（夜間取引）の急落・ストップ安と、海外の政府措置などの見出しを拾い、監視銘柄の名前と照合する
_have = {h["code"] for h in hits}
for q in ("PTS ストップ安", "PTS 急落", "夜間取引 急落 株価", "特別気配 売り気配"):
    for n in news(q) + []:
        for c, nm in STOCKS.items():
            if c in _have or nm not in n["title"]: continue
            hits.append({"code": c, "name": nm, "r": -98.0, "price": None, "prev": None, "note": "見出しで検知（PTS・特別気配など。値段は未確認）", "news": [n]}); _have.add(c)
hits.sort(key=lambda h: h["r"])
out = {"at": datetime.now(JST).isoformat(timespec="minutes"), "th": TH, "hits": hits}
try: old = {h["code"] for h in json.load(open("data/jumps.json"))["hits"]} if json.load(open("data/jumps.json"))["at"][:10] == out["at"][:10] else set()
except Exception: old = set()
json.dump(out, open("data/jumps.json", "w"), ensure_ascii=False, indent=1)
new = [h for h in hits if h["code"] not in old]
T = os.environ.get("NTFY_TOPIC")
if T and new:
    body = "\n".join(f"{h['name']}({h['code']}) " + (h.get("note") or f"{h['r']}% {h['price']:,}円") + (f"\n  {h['news'][0]['title']}" if h["news"] else "") for h in new)
    q = urllib.parse.urlencode({"title": "【個別株の急落】前日比−7%以下", "priority": "4", "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{T}?{q}", data=body.encode("utf-8"), method="POST"), timeout=30)
print(out["at"], [(h["name"], h["r"]) for h in hits])
try:
    print("JT", float(m["2914.T"].dropna().iloc[-1]), d["2914.T"].dropna().tail(3).to_dict())
except Exception as e: print("JT取得失敗", e)
