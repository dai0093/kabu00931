"""なぜ抽出しなかったかの診断。各銘柄の判定条件を直近3日分出す（当日は途中経過の足）。"""
import pandas as pd, yfinance as yf
from core import add_indicators, MIN_TURNOVER
from universe import STOCKS
CODES = ["7974","2914","3498","7352","4260","6323","4493","4667","3042","6258"]
lines = []
for c in CODES:
    try:
        df = yf.download(f"{c}.T", period="1y", auto_adjust=True, progress=False)
        df.columns = [x[0] if isinstance(x, tuple) else x for x in df.columns]
        d = add_indicators(df.dropna(subset=["Close"]))
    except Exception as e:
        lines.append(f"{c} 取得失敗 {e}"); continue
    lines.append(f"## {c} 監視対象={'○' if c in STOCKS else '×'}")
    for i in range(len(d)-3, len(d)):
        r = d.iloc[i]; hi60 = d.High.iloc[i-60:i].max()
        lines.append(f"{d.index[i].date()} 終値{r.Close:.0f} 60日高値{hi60:.0f}[{'○' if r.Close>hi60 else '×'}] "
                     f"25線{r.sma25:.0f}>75線{r.sma75:.0f}[{'○' if r.sma25>r.sma75 else '×'}] "
                     f"出来高倍率{r.Volume/r.vol20:.2f}[{'○' if r.Volume>1.5*r.vol20 else '×'}] "
                     f"売買代金{r.turnover20/1e8:.0f}億[{'○' if r.turnover20>=MIN_TURNOVER else '×'}]")
open("data/diag.md","w",encoding="utf-8").write("\n".join(lines)+"\n"); print("\n".join(lines))
