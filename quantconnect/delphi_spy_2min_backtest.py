# DELPHI Lorentzian ML - QuantConnect / LEAN Python
# SPY 2-minute backtest port of DELPHI_2
# Original Lorentzian Classification: jdehorty
# DELPHI adaptation: JXS_918
#
# Requested configuration:
#   neighbors = 1
#   include full 2000-bar DELPHI history = True
#   default exits = OFF
#   dynamic exits = OFF
#   EMA filter = 200
#   SMA filter = 200
#   kernel smoothing = ON
#   kernel lag = 5
#   session = 09:30-14:00 America/New_York
#
# With both DELPHI exit modes disabled, positions exit/reverse only on a valid
# opposite DELPHI entry or at the 14:00 session cutoff.

from AlgorithmImports import *
from collections import deque
from datetime import timedelta
import math


class DelphiQuantConnectBacktest(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2026, 9, 25)
        self.set_cash(100000)
        self.set_time_zone("America/New_York")

        self.spy = self.add_equity(
            "SPY", Resolution.MINUTE,
            data_normalization_mode=DataNormalizationMode.RAW
        ).symbol
        self.set_benchmark(self.spy)

        # ---------------- REQUESTED DELPHI PARAMETERS ----------------
        self.neighbors_count = 1
        self.max_bars_back = 2000
        self.include_full_history = True

        self.ema_period = 200
        self.sma_period = 200

        self.kernel_h = 8
        self.kernel_r = 8.0
        self.kernel_x = 25
        self.kernel_lag = 5
        self.use_kernel_smoothing = True

        self.session_start = 9 * 60 + 30
        self.session_end = 14 * 60

        # Feature defaults from DELPHI source.
        self.feature_specs = [
            ("RSI", 14, 1),
            ("WT", 10, 11),
            ("CCI", 20, 1),
            ("ADX", 20, 2),
            ("RSI", 9, 1),
        ]

        # DELPHI's additional volatility/regime/ADX filters are not enabled
        # here; requested trend filters are EMA200 + SMA200 + kernel direction.

        self.bars = deque(maxlen=2600)
        self.features = deque(maxlen=self.max_bars_back + 10)
        self.labels = deque(maxlen=self.max_bars_back + 10)

        self.signal = 0
        self.previous_signal = 0
        self.bar_count = 0
        self.last_trade_date = None

        # Running extrema reproduce ml.normalize() behavior for WT / CCI.
        self.norm_min = [float("inf")] * 5
        self.norm_max = [float("-inf")] * 5

        # 2-minute bars built from SPY minute data.
        self.consolidator = TradeBarConsolidator(timedelta(minutes=2))
        self.consolidator.data_consolidated += self.on_two_minute_bar
        self.subscription_manager.add_consolidator(self.spy, self.consolidator)

        # Warm indicators/features before trading.
        self.set_warm_up(timedelta(days=10))

    # ==================================================================
    # BASIC SERIES HELPERS
    # ==================================================================

    @staticmethod
    def ema(values, length):
        if not values:
            return None
        alpha = 2.0 / (length + 1.0)
        out = float(values[0])
        for v in values[1:]:
            out = alpha * float(v) + (1.0 - alpha) * out
        return out

    @staticmethod
    def sma(values, length):
        if len(values) < length:
            return None
        x = values[-length:]
        return sum(x) / float(length)

    @staticmethod
    def rsi(values, length):
        if len(values) < length + 1:
            return None
        changes = [values[i] - values[i - 1] for i in range(1, len(values))]
        seed = changes[:length]
        avg_gain = sum(max(x, 0.0) for x in seed) / length
        avg_loss = sum(max(-x, 0.0) for x in seed) / length
        for x in changes[length:]:
            avg_gain = (avg_gain * (length - 1) + max(x, 0.0)) / length
            avg_loss = (avg_loss * (length - 1) + max(-x, 0.0)) / length
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    @staticmethod
    def cci(values, length):
        if len(values) < length:
            return None
        x = values[-length:]
        mean = sum(x) / length
        dev = sum(abs(v - mean) for v in x) / length
        if dev <= 1e-12:
            return 0.0
        return (values[-1] - mean) / (0.015 * dev)

    @staticmethod
    def adx(highs, lows, closes, length):
        if len(closes) < length * 2 + 2:
            return None
        trs, plus_dm, minus_dm = [], [], []
        for i in range(1, len(closes)):
            up = highs[i] - highs[i - 1]
            down = lows[i - 1] - lows[i]
            plus_dm.append(up if up > down and up > 0 else 0.0)
            minus_dm.append(down if down > up and down > 0 else 0.0)
            trs.append(max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            ))

        tr_s = sum(trs[:length])
        p_s = sum(plus_dm[:length])
        m_s = sum(minus_dm[:length])
        dxs = []

        for i in range(length, len(trs)):
            tr_s = tr_s - tr_s / length + trs[i]
            p_s = p_s - p_s / length + plus_dm[i]
            m_s = m_s - m_s / length + minus_dm[i]
            if tr_s <= 1e-12:
                dxs.append(0.0)
                continue
            pdi = 100.0 * p_s / tr_s
            mdi = 100.0 * m_s / tr_s
            den = pdi + mdi
            dxs.append(0.0 if den <= 1e-12 else 100.0 * abs(pdi - mdi) / den)

        if len(dxs) < length:
            return None
        out = sum(dxs[:length]) / length
        for d in dxs[length:]:
            out = (out * (length - 1) + d) / length
        return out

    def normalize_running(self, value, slot):
        if value is None or math.isnan(value):
            return None
        self.norm_min[slot] = min(self.norm_min[slot], value)
        self.norm_max[slot] = max(self.norm_max[slot], value)
        lo, hi = self.norm_min[slot], self.norm_max[slot]
        if hi - lo <= 1e-12:
            return 0.5
        return (value - lo) / (hi - lo)

    def normalized_rsi(self, closes, n1, n2):
        # ml.n_rsi = rescale(EMA(RSI,n2), 0..100 -> 0..1)
        need = min(len(closes), max(n1 + n2 + 80, 120))
        src = closes[-need:]
        vals = []
        for end in range(n1 + 1, len(src) + 1):
            r = self.rsi(src[:end], n1)
            if r is not None:
                vals.append(r)
        if not vals:
            return None
        smoothed = self.ema(vals, n2)
        return max(0.0, min(1.0, smoothed / 100.0))

    def normalized_cci(self, closes, n1, n2, slot):
        need = min(len(closes), max(n1 + n2 + 80, 120))
        src = closes[-need:]
        vals = []
        for end in range(n1, len(src) + 1):
            c = self.cci(src[:end], n1)
            if c is not None:
                vals.append(c)
        if not vals:
            return None
        return self.normalize_running(self.ema(vals, n2), slot)

    def normalized_wt(self, hlc3, n1, n2, slot):
        if len(hlc3) < n1 + n2 + 8:
            return None
        src = hlc3[-min(len(hlc3), 180):]

        esa, dev_ema, wt1 = [], [], []
        a1 = 2.0 / (n1 + 1.0)
        a2 = 2.0 / (n2 + 1.0)
        e = src[0]
        d = 0.0
        w = 0.0

        for price in src:
            e = a1 * price + (1 - a1) * e
            d = a1 * abs(price - e) + (1 - a1) * d
            ci = 0.0 if d <= 1e-12 else (price - e) / (0.015 * d)
            w = a2 * ci + (1 - a2) * w
            esa.append(e)
            dev_ema.append(d)
            wt1.append(w)

        if len(wt1) < 4:
            return None
        wt2 = sum(wt1[-4:]) / 4.0
        return self.normalize_running(wt1[-1] - wt2, slot)

    # ==================================================================
    # DELPHI FEATURES + LORENTZIAN CLASSIFIER
    # ==================================================================

    def current_features(self):
        bars = list(self.bars)
        closes = [b.close for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        hlc3 = [(b.high + b.low + b.close) / 3.0 for b in bars]

        if len(closes) < 210:
            return None

        out = []
        for slot, (name, a, b) in enumerate(self.feature_specs):
            if name == "RSI":
                v = self.normalized_rsi(closes, a, b)
            elif name == "WT":
                v = self.normalized_wt(hlc3, a, b, slot)
            elif name == "CCI":
                v = self.normalized_cci(closes, a, b, slot)
            else:
                raw = self.adx(highs, lows, closes, a)
                v = None if raw is None else max(0.0, min(1.0, raw / 100.0))
            if v is None:
                return None
            out.append(v)
        return out

    @staticmethod
    def lorentzian_distance(a, b):
        return sum(math.log(1.0 + abs(x - y)) for x, y in zip(a, b))

    def classify(self, current):
        # Pine DELPHI ANN loop, with neighbors_count=1.
        # History is limited by the source's Max Bars Back = 2000.
        if len(self.features) < 20:
            return 0

        last_distance = -1.0
        chosen_label = 0

        # Do not compare against the just-created current sample.
        hist_features = list(self.features)[:-1]
        hist_labels = list(self.labels)[:-1]

        for i, feat in enumerate(hist_features):
            # Original code excludes every fourth historical index.
            if i % 4 == 0:
                continue
            d = self.lorentzian_distance(current, feat)
            if d >= last_distance:
                last_distance = d
                chosen_label = hist_labels[i]

        return int(chosen_label)

    # ==================================================================
    # KERNEL REGRESSION
    # ==================================================================

    def rational_quadratic(self, closes, lookback, relative_weight, start_at):
        if len(closes) <= start_at:
            return None
        weighted = 0.0
        weights = 0.0
        limit = len(closes) - start_at
        for i in range(limit):
            src = closes[-1 - i]
            w = (1.0 + (i * i) /
                 (lookback * lookback * 2.0 * relative_weight)) ** (-relative_weight)
            weighted += src * w
            weights += w
        return None if weights == 0 else weighted / weights

    def gaussian(self, closes, lookback, start_at):
        if lookback <= 0 or len(closes) <= start_at:
            return None
        weighted = 0.0
        weights = 0.0
        limit = len(closes) - start_at
        for i in range(limit):
            src = closes[-1 - i]
            w = math.exp(-(i * i) / (2.0 * lookback * lookback))
            weighted += src * w
            weights += w
        return None if weights == 0 else weighted / weights

    def kernel_state(self):
        closes = [b.close for b in self.bars]
        if len(closes) < self.kernel_x + 20:
            return None, None, False, False

        yhat1 = self.rational_quadratic(
            closes, self.kernel_h, self.kernel_r, self.kernel_x
        )
        yhat2 = self.gaussian(
            closes, self.kernel_h - self.kernel_lag, self.kernel_x
        )
        if yhat1 is None or yhat2 is None:
            return yhat1, yhat2, False, False

        # Smoothing ON: bullish when Gaussian >= Rational Quadratic.
        bullish = yhat2 >= yhat1
        bearish = yhat2 <= yhat1
        return yhat1, yhat2, bullish, bearish

    # ==================================================================
    # 2-MINUTE STRATEGY
    # ==================================================================

    def on_two_minute_bar(self, sender, bar):
        self.bars.append(bar)
        self.bar_count += 1

        t = bar.end_time
        minute_of_day = t.hour * 60 + t.minute

        # Flatten on first 2-minute bar ending at/after 14:00 ET.
        if minute_of_day >= self.session_end:
            if self.portfolio[self.spy].invested:
                self.liquidate(self.spy, "DELPHI 14:00 SESSION CUTOFF")
            return

        feat = self.current_features()
        if feat is None:
            return

        # Pine training label: current source vs source four bars ago.
        closes = [b.close for b in self.bars]
        if len(closes) < 5:
            return
        label = -1 if closes[-5] < closes[-1] else (1 if closes[-5] > closes[-1] else 0)

        self.features.append(feat)
        self.labels.append(label)

        prediction = self.classify(feat)

        # Signal persists through neutral/filter-failed bars like Pine nz(signal[1]).
        self.previous_signal = self.signal
        if prediction > 0:
            self.signal = 1
        elif prediction < 0:
            self.signal = -1

        is_new_buy = self.signal == 1 and self.signal != self.previous_signal
        is_new_sell = self.signal == -1 and self.signal != self.previous_signal

        # Requested EMA200 / SMA200 filters.
        if len(closes) < 200:
            return
        ema200 = self.ema(closes[-600:], self.ema_period)
        sma200 = self.sma(closes, self.sma_period)
        price = closes[-1]

        ema_up = price > ema200
        ema_down = price < ema200
        sma_up = price > sma200
        sma_down = price < sma200

        _, _, kernel_bull, kernel_bear = self.kernel_state()

        in_session = self.session_start <= minute_of_day < self.session_end
        if self.is_warming_up or not in_session:
            return

        long_entry = is_new_buy and kernel_bull and ema_up and sma_up
        short_entry = is_new_sell and kernel_bear and ema_down and sma_down

        # No default exit and no dynamic exit:
        # only opposite valid entry reverses the position.
        holdings = self.portfolio[self.spy].quantity

        if long_entry and holdings <= 0:
            self.set_holdings(self.spy, 1.0, tag="DELPHI LONG")
            self.debug(
                f"{t} DELPHI LONG | px={price:.2f} pred={prediction} "
                f"EMA200={ema200:.2f} SMA200={sma200:.2f}"
            )

        elif short_entry and holdings >= 0:
            self.set_holdings(self.spy, -1.0, tag="DELPHI SHORT")
            self.debug(
                f"{t} DELPHI SHORT | px={price:.2f} pred={prediction} "
                f"EMA200={ema200:.2f} SMA200={sma200:.2f}"
            )

    def on_end_of_algorithm(self):
        self.debug("DELPHI QuantConnect backtest complete.")
