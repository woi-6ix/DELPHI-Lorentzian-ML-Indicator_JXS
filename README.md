# DELPHI Lorentzian ML Indicator

![Pine Script](https://img.shields.io/badge/Pine%20Script-v6-blue)
![Platform](https://img.shields.io/badge/Platform-TradingView-black)
![License](https://img.shields.io/badge/License-MPL--2.0-purple)

**DELPHI** is a TradingView strategy built from jdehorty's Lorentzian Classification. It trades new LC signals when the kernel trend agrees.

## Lorentzian Classification

[Jdehorty's original indicator](https://www.tradingview.com/script/WhBzgfDu-Machine-Learning-Lorentzian-Classification/) compares current RSI, WaveTrend, CCI, and ADX readings with past bars. Selected past patterns vote long or short. Its logarithmic distance reduces the weight of unusually large differences. The author's “price-time” idea is an analogy for market outliers; the code does not read news.

DELPHI enters when the LC signal **changes direction**, the enabled filters pass, and the separate kernel trend agrees. The signal bar must close within your Trading Session hours (default 09:30 to before 15:00 New York time). Bars that stay the same color do not create another entry.

## How the signal is made

1. **Feature values:** Each bar calculates up to five normalized indicators chosen from RSI, WaveTrend, CCI, and ADX. The defaults are RSI (14, 1), WT (10, 11), CCI (20, 1), ADX (20), and RSI (9, 1). Choose two to five features.
2. **Historical comparison:** For each candidate historical feature vector, the script sums `log(1 + abs(current feature − historical feature))` across the enabled features. Its approximate neighbor loop accepts distances according to a moving threshold, skips indices divisible by four, keeps at most the configured neighbor count (default eight), and sums their training labels for a prediction. This is the algorithm in the source, not a conventional nearest-neighbor search over every bar.
3. **Four-bar training label:** The code assigns `short` if `src[4] < src[0]`, `long` if `src[4] > src[0]`, and neutral if equal. These signs are shown exactly as implemented; inspect or change them if your intended direction differs.
4. **Signal filters:** A positive prediction becomes a long classification and a negative prediction becomes a short classification only when enabled volatility, regime, and ADX filters pass. Otherwise the previous classification persists. A **new trade setup requires a classification change**.
5. **Entry confirmation:** A new long also needs the bullish kernel state and any enabled EMA/SMA uptrend filters. A new short needs their bearish equivalents. The kernel defaults to the rational quadratic estimate's slope; optional smoothing switches the trend check to a Gaussian-versus-rational-quadratic comparison. The kernel filter can be disabled.

## Orders and session

| Event | Strategy action |
| --- | --- |
| New long or short setup | Enter at the signal bar's close inside your chosen New York trading hours. An opposite entry can reverse; the strategy will not add another entry in the same direction. |
| Default exit | Follow the original strict four-bar signal exit rules; an opposite entry may reverse first. |
| Optional dynamic exit | Close on the qualifying opposite kernel rate change. This option only applies when EMA, SMA, and kernel smoothing are all off; otherwise the strict exit applies. |
| Session cutoff | Close any remaining position on the first bar ending at or after your cutoff (default 15:00 New York). No new entries at or after it. |

Set **Start hour/minute** and **Cutoff hour/minute** in Trading Session. Times use `America/New_York` and the cutoff must be later than the start on the same day. Use an intraday time based chart. If the chosen cutoff falls between bar closes, the position closes at the next available bar close, which may be later than the selected minute.

With `process_orders_on_close=true`, historical entries **and normal market exits** fill at the signal bar's close. The Pythia execution block does not change that. For next-bar-open market exits, turn off **Process orders on close** in TradingView's strategy properties; entries then also fill at the next bar's open and a signal just before cutoff can fill after it. A single ordinary Pine strategy cannot guarantee close-of-signal entries and next-open exits simultaneously in historical Strategy Tester.

There is **no stop loss or profit target** in this version. Set position size, commissions, and slippage in TradingView's strategy properties. The orders use the chart symbol's price and do not simulate option premium, Greeks, spread fills, or broker execution.

## Display, controls, and alerts

- **Chart:** Entry labels, optional exit crosses, a kernel estimate line, bar colors, and numeric prediction labels. Confidence gradient, solid colors, and label offsets can be adjusted.
- **General settings:** Source, neighbor count, maximum history, feature count, color compression, default exit markers, dynamic exits, trade statistics, and historical range.
- **Filters:** Volatility and regime filters are on by default. ADX, EMA, and SMA trend filters are optional. Kernel agreement is on by default.
- **Statistics:** The upper-right box comes from the original `ml.backtest()` signal calculation, including win rate, trade count, win/loss ratio, and early signal flips. It is **not** calculated from actual closed `strategy.*` orders. Use Strategy Tester to evaluate the executed orders.
- **Trade alerts:** Create a TradingView strategy alert for **order fills**; entries, normal exits, and the session cutoff supply `alert_message` text. Select **Order fills and alert() function calls** if you also want kernel bullish/bearish change messages. Existing TradingView alerts must be recreated after code changes because alerts use a snapshot of the script.

## Use

1. Copy the entire [Pine source](DELPHI_Lorentzian_ML_Indicator_JXS_918.pine) into TradingView's Pine Editor.
2. Add it to an intraday chart. The published `jdehorty/MLExtensions/2` and `jdehorty/KernelFunctions/2` libraries must be available.
3. Review the inputs, configure strategy properties for the instrument, and compare the chart signals with Strategy Tester orders.

## Files and attribution

- [`DELPHI_Lorentzian_ML_Indicator_JXS_918.pine`](DELPHI_Lorentzian_ML_Indicator_JXS_918.pine) — full strategy source.
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — original work and dependency attribution.
- [`LICENSE`](LICENSE) — Mozilla Public License 2.0.

**Author:** JXS · [@woi-6ix](https://github.com/woi-6ix). Adapted from Lorentzian Classification by **jdehorty** under MPL 2.0.
