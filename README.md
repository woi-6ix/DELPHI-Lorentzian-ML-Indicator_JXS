# DELPHI Lorentzian ML Indicator_{JXS_918}

![Pine Script](https://img.shields.io/badge/Pine%20Script-v6-blue)
![Platform](https://img.shields.io/badge/Platform-TradingView-black)
![License](https://img.shields.io/badge/License-MPL--2.0-purple)

**DELPHI** is a TradingView strategy adapted from jdehorty's *Machine Learning: Lorentzian Classification*. The title says “Indicator” to retain the JXS name, but the script uses `strategy()` and reports orders in Strategy Tester. It trades changes in a filtered Lorentzian classification signal when the kernel trend agrees.

## What Lorentzian Classification trading means

Jdehorty's [original TradingView indicator](https://www.tradingview.com/script/WhBzgfDu-Machine-Learning-Lorentzian-Classification/) compares the current bar's indicator readings with patterns from historical bars. The readings can include RSI, WaveTrend, CCI, and ADX. Each selected historical pattern contributes a directional label, and the sum produces a positive or negative vote. This is history-based pattern classification, not a trained neural network or a prediction of option premium.

The script's *Lorentzian distance* adds `log(1 + absolute difference)` across the chosen features. This makes very large feature differences count less than they would in a simple straight-line (Euclidean) comparison. The original author's “price-time” discussion uses unusually disruptive market events as an analogy for outliers; the code does **not** read an FOMC calendar or recognize news. Its approximate neighbor selection is also not a textbook search for the mathematically closest bars.

A positive vote favors the long classification and a negative vote favors the short classification after the enabled market filters. The chart's prediction number and color convey vote direction and intensity, **not a calibrated win probability**. The kernel regression line is a separate trend estimate that DELPHI uses to check the LC signal. Similar past indicator patterns can still lead to different future prices.

**DELPHI trades a change in that LC classification.** It does not enter merely because a bar is colored bullish or bearish, and it does not wait for several consecutive confirmation bars. A new buy or sell signal must pass the enabled market filters, agree with the kernel direction, and occur within the entry window:

| LC event | Additional checks | DELPHI action |
| --- | --- | --- |
| Classification changes to long | Bullish kernel, optional EMA/SMA uptrend, closing time from 09:30 to before 15:00 New York | Enter long at that bar's close |
| Classification changes to short | Bearish kernel, optional EMA/SMA downtrend, same session rule | Enter short at that bar's close |
| Classification stays the same or a check fails | No new eligible signal | Do not open a new trade |

For example, if the neighbor labels produce a positive vote and the filtered classification flips to long at 10:15, DELPHI buys at that candle's close only if the kernel and any enabled trend filters also agree. Subsequent positive bars alone do not create another entry. The exit and 15:00 cutoff rules below then manage the position. In ARES, LC can be used alongside extra color-bar and price-slope confirmations; those optional ARES confirmations are not part of DELPHI.

## How the signal is made

1. **Feature values:** Each bar calculates up to five normalized indicators chosen from RSI, WaveTrend, CCI, and ADX. The defaults are RSI (14, 1), WT (10, 11), CCI (20, 1), ADX (20), and RSI (9, 1). Choose two to five features.
2. **Historical comparison:** For each candidate historical feature vector, the script sums `log(1 + abs(current feature − historical feature))` across the enabled features. Its approximate neighbor loop accepts distances according to a moving threshold, skips indices divisible by four, keeps at most the configured neighbor count (default eight), and sums their training labels for a prediction. This is the algorithm in the source, not a conventional nearest-neighbor search over every bar.
3. **Four-bar training label:** The code assigns `short` if `src[4] < src[0]`, `long` if `src[4] > src[0]`, and neutral if equal. These signs are shown exactly as implemented; inspect or change them if your intended direction differs.
4. **Signal filters:** A positive prediction becomes a long classification and a negative prediction becomes a short classification only when enabled volatility, regime, and ADX filters pass. Otherwise the previous classification persists. A **new trade setup requires a classification change**.
5. **Entry confirmation:** A new long also needs the bullish kernel state and any enabled EMA/SMA uptrend filters. A new short needs their bearish equivalents. The kernel defaults to the rational quadratic estimate's slope; optional smoothing switches the trend check to a Gaussian-versus-rational-quadratic comparison. The kernel filter can be disabled.

## Orders and session

| Event | Strategy action |
| --- | --- |
| New long or short setup | Enter at the signal bar's close if its **closing time** is at least 09:30 and before 15:00 in `America/New_York`. An opposite entry can reverse an existing position. |
| Default exit | Follow the original strict four-bar signal exit rules; an opposite entry may reverse first. |
| Optional dynamic exit | Close on the qualifying opposite kernel rate change. This option only applies when EMA, SMA, and kernel smoothing are all off; otherwise the strict exit applies. |
| 15:00 cutoff | Close any remaining position when a bar closes **exactly** at 15:00 New York time. No entry can fill on or after that boundary. |

The strategy uses `process_orders_on_close=true`. In historical Strategy Tester, entries **and ordinary market exits** are simulated at the triggering bar's close. The previously requested next-bar-open normal exits are **not implemented**. The cutoff is also a simulated close fill. Use a time based intraday chart, such as 1 minute or 5 minutes, with a bar closing at 15:00; a chart with no such bar cannot execute the exact cutoff.

There is **no stop loss or profit target** in this version. Set position size, commissions, and slippage in TradingView's strategy properties. The orders use the chart symbol's price and do not simulate option premium, Greeks, spread fills, or broker execution.

## Display, controls, and alerts

- **Chart:** Entry labels, optional exit crosses, a kernel estimate line, bar colors, and numeric prediction labels. Confidence gradient, solid colors, and label offsets can be adjusted.
- **General settings:** Source, neighbor count, maximum history, feature count, color compression, default exit markers, dynamic exits, trade statistics, and historical range.
- **Filters:** Volatility and regime filters are on by default. ADX, EMA, and SMA trend filters are optional. Kernel agreement is on by default.
- **Statistics:** The upper-right box comes from the original `ml.backtest()` signal calculation, including win rate, trade count, win/loss ratio, and early signal flips. It is **not** calculated from actual closed `strategy.*` orders. Use Strategy Tester to evaluate the executed orders.
- **Trade alerts:** Create a TradingView strategy alert for **order fills**; entries, normal exits, and the 15:00 cutoff supply `alert_message` text. Select **Order fills and alert() function calls** if you also want kernel bullish/bearish change messages. Existing TradingView alerts must be recreated after code changes because alerts use a snapshot of the script.

## Use

1. Copy the entire [Pine source](DELPHI_Lorentzian_ML_Indicator_JXS_918.pine) into TradingView's Pine Editor.
2. Add it to an intraday chart. The published `jdehorty/MLExtensions/2` and `jdehorty/KernelFunctions/2` libraries must be available.
3. Review the inputs, configure strategy properties for the instrument, and compare the chart signals with Strategy Tester orders.

## Files and attribution

- [`DELPHI_Lorentzian_ML_Indicator_JXS_918.pine`](DELPHI_Lorentzian_ML_Indicator_JXS_918.pine) — full strategy source.
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — original work and dependency attribution.
- [`LICENSE`](LICENSE) — Mozilla Public License 2.0.

**Author:** JXS · [@woi-6ix](https://github.com/woi-6ix). Adapted from Lorentzian Classification by **jdehorty** under MPL 2.0.
