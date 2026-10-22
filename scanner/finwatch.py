"""私募信用運用会社・G-SIB・プライマリーディーラー・BDC の監視。
data/finwatch_source.txt（富士さん提供の名簿、2026-10-20）を元に、上場している主体の株価を毎回取得し、
急落（1日/5日/高値からの下落）を検知して data/finwatch.json に書く。非上場は報道監視（ダッシュボード側）に回す。
独自の売買判断はしない。警戒の閾値は下記 TH（検証前の暫定値）。"""
import json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
import yfinance as yf

JST = timezone(timedelta(hours=9))
TH = {"d1": -4.0, "d5": -8.0, "dd": -20.0}   # 暫定：1日≤-4%、5日≤-8%、60日高値から≤-20%
# (グループ, 名簿の表記, ティッカー)
L = [
 ("PC", "アレス", "ARES"), ("PC", "アポロ", "APO"), ("PC", "ブラックストーン", "BX"), ("PC", "KKR", "KKR"),
 ("PC", "ブルー・アウル", "OWL"), ("PC", "ブラックロック(HPS)", "BLK"), ("PC", "ブルックフィールド(オークツリー)", "BN"),
 ("PC", "カーライル", "CG"), ("PC", "TPG(アンジェロ・ゴードン)", "TPG"), ("PC", "T.ロウ(OHA)", "TROW"),
 ("PC", "フランクリン(BSP)", "BEN"), ("PC", "プルデンシャル(PGIM)", "PRU"), ("PC", "アリアンツ(AGI/PIMCO)", "ALV.DE"),
 ("PC", "ICG", "ICG.L"), ("PC", "CVC", "CVC.AS"), ("PC", "ティケオー", "TKO.PA"), ("PC", "ユーラゼオ", "RF.PA"),
 ("PC", "M&G", "MNG.L"), ("PC", "パートナーズ・グループ", "PGHN.SW"), ("PC", "ハミルトン・レーン", "HLNE"),
 ("PC", "ステップストーン", "STEP"), ("PC", "ケネディ・ウィルソン", "KW"), ("PC", "メトリクス", "MXT.AX"),
 ("PC", "チャレンジャー", "CGF.AX"), ("PC", "ニューバーガー系(参考)", "NMRK"),
 ("BDC", "Ares Capital", "ARCC"), ("BDC", "Blue Owl Capital Corp", "OBDC"), ("BDC", "FS KKR", "FSK"),
 ("BDC", "Blackstone Secured Lending", "BXSL"), ("BDC", "Golub BDC", "GBDC"), ("BDC", "BDC ETF", "BIZD"),
 ("米銀", "JPモルガン", "JPM"), ("米銀", "バンカメ", "BAC"), ("米銀", "シティ", "C"), ("米銀", "ゴールドマン", "GS"),
 ("米銀", "モルガン・スタンレー", "MS"), ("米銀", "ウェルズ・ファーゴ", "WFC"), ("米銀", "BNY", "BK"),
 ("米銀", "ステート・ストリート", "STT"), ("米銀", "ジェフリーズ", "JEF"),
 ("欧州銀", "HSBC", "HSBA.L"), ("欧州銀", "バークレイズ", "BARC.L"), ("欧州銀", "スタンチャート", "STAN.L"),
 ("欧州銀", "NatWest", "NWG.L"), ("欧州銀", "BNPパリバ", "BNP.PA"), ("欧州銀", "クレディ・アグリコル", "ACA.PA"),
 ("欧州銀", "ナティクシス(BPCE)", "KN.PA"), ("欧州銀", "ソシエテ・ジェネラル", "GLE.PA"),
 ("欧州銀", "ドイツ銀行", "DBK.DE"), ("欧州銀", "ING", "INGA.AS"), ("欧州銀", "UBS", "UBSG.SW"),
 ("欧州銀", "サンタンデール", "SAN.MC"),
 ("加豪銀", "RBC", "RY"), ("加豪銀", "TD", "TD"), ("加豪銀", "BMO", "BMO"), ("加豪銀", "スコシア", "BNS"),
 ("加豪銀", "マッコーリー", "MQG.AX"),
 ("日本", "三菱UFJ", "8306.T"), ("日本", "みずほ", "8411.T"), ("日本", "三井住友", "8316.T"),
 ("日本", "野村", "8604.T"), ("日本", "大和証券G", "8601.T"),
 ("中国", "中国工商銀行", "1398.HK"), ("中国", "中国農業銀行", "1288.HK"), ("中国", "中国銀行", "3988.HK"),
 ("中国", "中国建設銀行", "0939.HK"), ("中国", "交通銀行", "3328.HK"), ("中国", "中信証券", "600030.SS"),
]
L = [x for x in L if x[2] != "NMRK"]   # 参考枠は外す
tick = [x[2] for x in L]
df = yf.download(tick, period="6mo", auto_adjust=False, progress=False, threads=True)["Close"]
from zoneinfo import ZoneInfo
CUT = {".L": ("Europe/London", 17.5), ".PA": ("Europe/Paris", 18.0), ".DE": ("Europe/Berlin", 18.0), ".AS": ("Europe/Amsterdam", 18.0),
       ".SW": ("Europe/Zurich", 18.0), ".MC": ("Europe/Madrid", 18.0), ".T": ("Asia/Tokyo", 15.75), ".HK": ("Asia/Hong_Kong", 16.75),
       ".SS": ("Asia/Shanghai", 15.5), ".AX": ("Australia/Sydney", 16.75)}
def settled(s, t):
    """取引時間中の未確定バーを落とす（確定終値だけで判定する）"""
    tz, cut = next((v for k, v in CUT.items() if t.endswith(k)), ("America/New_York", 16.5))
    now = datetime.now(ZoneInfo(tz))
    if len(s) and s.index[-1].date() == now.date() and now.hour + now.minute / 60 < cut:
        return s.iloc[:-1]
    return s
rows, bad = [], []
for g, nm, t in L:
    try:
        s = settled(df[t].dropna(), t)
        if len(s) < 25: raise ValueError("bars")
        c = float(s.iloc[-1]); d1 = (c / float(s.iloc[-2]) - 1) * 100; d5 = (c / float(s.iloc[-6]) - 1) * 100
        hi = float(s.iloc[-60:].max()); dd = (c / hi - 1) * 100
        flag = [k for k, v, th in (("1日", d1, TH["d1"]), ("5日", d5, TH["d5"]), ("高値比", dd, TH["dd"])) if v <= th]
        rows.append({"g": g, "name": nm, "t": t, "date": str(s.index[-1].date()), "close": round(c, 2),
                     "d1": round(d1, 1), "d5": round(d5, 1), "dd": round(dd, 1), "flag": flag})
    except Exception as e:
        bad.append(t)
if len(rows) < len(L) * 0.5:
    print("取得失敗が多いため書き込まない", bad); sys.exit(1)
import statistics as st
groups = {}
for g in dict.fromkeys(x[0] for x in L):
    r = [x for x in rows if x["g"] == g]
    if r:
        groups[g] = {"n": len(r), "med_dd": round(st.median(x["dd"] for x in r), 1), "med_d1": round(st.median(x["d1"] for x in r), 1),
                     "med_d5": round(st.median(x["d5"] for x in r), 1),
                     "n_flag": sum(1 for x in r if x["flag"])}
flagged = sorted([x for x in rows if x["flag"]], key=lambda x: x["dd"])
out = {"updatedAt": datetime.now(JST).isoformat(timespec="minutes"), "th": TH, "groups": groups,
       "rows": rows, "flagged": [f'{x["name"]}({x["t"]})' for x in flagged], "missing": bad,
       "note": "非上場の運用会社（Cerberus, Golub本体, Sixth Street等）は報道監視。名簿は data/finwatch_source.txt"}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fintree
try:
    _s = settled(yf.download("^SOX", period="1mo", auto_adjust=False, progress=False)["Close"].squeeze().dropna(), "^SOX")
    sox5 = float((_s.iloc[-1] / _s.iloc[-6] - 1) * 100)
except Exception:
    sox5 = None
tst, thit = fintree.state(groups)
strong, swhy = fintree.strong(groups, sox5)
out["tree"] = {"state": tst, "hits": thit, "strong": strong, "strong_why": swhy, "sox5": None if sox5 is None else round(sox5, 1)}
try:
    prev_tree = json.load(open("data/finwatch.json")).get("tree", {}).get("state", "ok")
except Exception:
    prev_tree = "ok"
try:
    lt = json.load(open("data/logic_tree.json"))
    json.dump(fintree.apply(lt, tst), open("data/logic_tree.json", "w"), ensure_ascii=False, indent=1)
except Exception as e:
    print("logic_tree反映失敗", e)
json.dump(out, open("data/finwatch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"取得{len(rows)}/{len(L)}  警戒{len(flagged)}  欠損{bad}")
for g, v in groups.items(): print(g, v)
for x in flagged[:15]: print(x["name"], x["d1"], x["d5"], x["dd"], x["flag"])
# 通知：警戒銘柄の顔ぶれが前回から増えた時だけ
SENT = "data/finwatch_sent.json"
prev = json.load(open(SENT)) if os.path.exists(SENT) else {"names": []}
new = [n for n in out["flagged"] if n not in prev["names"]]
TOPIC = os.environ.get("NTFY_TOPIC")
dk = [g for g, v in groups.items() if v["n_flag"] >= max(2, v["n"] // 4)]
prev_strong = False
try:
    prev_strong = json.load(open("data/finwatch_sent.json")).get("strong", False)
except Exception:
    pass
RANK = {"ok": 0, "near": 1, "lit": 2}
if TOPIC and (RANK[tst] > RANK[prev_tree] or (strong and not prev_strong)) and "--no-notify" not in sys.argv:
    q = urllib.parse.urlencode({"title": f"【ロジックツリー】金融機関株価が{'点灯' if tst=='lit' else '接近'}", "priority": "4",
                                "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}", data=("\n".join(thit) + ("\n【強警戒】" + "／".join(swhy) + "\n縮小の検討：日経関連・半導体ETFを半分程度に（自動売買はしません。判断は富士さん）" if strong else "") + "\n根拠：検証16（10営業日内に日経-7%の発生率が平均の約" + ("3" if tst=="lit" else "2") + "倍）").encode("utf-8"), method="POST"), timeout=30)
if TOPIC and (new and (len(new) >= 2 or dk)) and "--no-notify" not in sys.argv:
    body = "新しく警戒：" + "、".join(new[:10]) + ("\n群で警戒：" + "、".join(dk) if dk else "") + \
           "\n閾値：1日≤-4% / 5日≤-8% / 60日高値比≤-20%（暫定）"
    q = urllib.parse.urlencode({"title": "【金融機関 株価警戒】", "priority": "4",
                                "click": "https://dai0093.github.io/kabu00931/signals.html"})
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{TOPIC}?{q}", data=body.encode("utf-8"), method="POST"), timeout=30)
json.dump({"names": out["flagged"], "at": out["updatedAt"], "strong": strong}, open(SENT, "w"), ensure_ascii=False)
# run 2026-10-20_16:25:10
# run 2026-10-21 06:57 JST
# run 2026-10-22 06:58 JST
# run 2026-10-22T02:36:50
# run 2026-10-22T05:32:24
# run 2026-10-22T21:30:37
