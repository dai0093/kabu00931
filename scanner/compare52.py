"""つれ安候補：日経平均への寄与が大きい（先物の裁定売りで機械的に売られやすい）主力株のうち半導体以外。
業績の質（ROE・営業利益率）と、直近の下げ（5日・60日高値比）、日経との連動（ベータ）を並べる。"""
import warnings; warnings.filterwarnings("ignore")
import pandas as pd, numpy as np, yfinance as yf, json
L = {"9983.T":"ファーストリテイリング","9433.T":"KDDI","6762.T":"TDK","6954.T":"ファナック","4519.T":"中外製薬","4543.T":"テルモ","4568.T":"第一三共",
"6098.T":"リクルートHD","6367.T":"ダイキン","6971.T":"京セラ","6988.T":"日東電工","9766.T":"コナミG","7832.T":"バンダイナムコ","7974.T":"任天堂",
"6758.T":"ソニーG","8001.T":"伊藤忠","8031.T":"三井物産","8766.T":"東京海上","7203.T":"トヨタ","6501.T":"日立","6861.T":"キーエンス","2802.T":"味の素",
"4661.T":"オリエンタルランド","9984.T":"ソフトバンクG","6273.T":"SMC","6981.T":"村田製作所","4901.T":"富士フイルム","7741.T":"HOYA","6301.T":"コマツ",
"6503.T":"三菱電機","6902.T":"デンソー","4502.T":"武田薬品","4503.T":"アステラス","2413.T":"エムスリー","4063.T":"信越化学","9432.T":"NTT",
"9434.T":"ソフトバンク","8058.T":"三菱商事","7267.T":"ホンダ","4704.T":"トレンドマイクロ","6326.T":"クボタ","3382.T":"セブン&アイ","8035.T":None}
semi = {"9984.T","4063.T","7741.T","6981.T"}  # 半導体の色が濃いもの（参考表示）
px = yf.download([k for k in L if L[k]] + ["^N225"], period="1y", auto_adjust=False, progress=False)["Close"]
r = px.pct_change(); rows = []
for t, nm in L.items():
    if not nm or t not in px: continue
    s = px[t].dropna()
    if len(s) < 100: continue
    b = r[t].iloc[-120:].cov(r["^N225"].iloc[-120:]) / r["^N225"].iloc[-120:].var()
    try:
        inf = yf.Ticker(t).info
    except Exception:
        inf = {}
    rows.append({"code": t[:-2], "name": nm, "semi": t in semi, "close": round(float(s.iloc[-1])), "d5": round(float(s.iloc[-1]/s.iloc[-6]-1)*100, 1),
                 "dd60": round(float(s.iloc[-1]/s.iloc[-60:].max()-1)*100, 1), "beta": round(float(b), 2),
                 "roe": round((inf.get("returnOnEquity") or np.nan)*100, 1), "opm": round((inf.get("operatingMargins") or np.nan)*100, 1),
                 "per": round(inf.get("forwardPE") or inf.get("trailingPE") or np.nan, 1), "pbr": round(inf.get("priceToBook") or np.nan, 1),
                 "date": str(s.index[-1].date())})
df = pd.DataFrame(rows)
df["est_today"] = (df["beta"] * -7.7).round(1)   # 日経先物 −7.7% をベータで割り当てた今日の想定下げ
df = df.sort_values("dd60")
pd.set_option("display.width", 250); print(df.to_string(index=False))
json.dump(df.to_dict("records"), open("data/tsureyasu.json", "w"), ensure_ascii=False)
