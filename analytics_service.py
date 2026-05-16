import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.db.models import Trade, TradeStatus


class TradeMetrics:
    def __init__(self, trades: list[Trade]):
        self.trades = trades
        self.n = len(trades)
        self._compute()

    def _compute(self):
        closed = [t for t in self.trades if t.exit_price is not None]
        self.total_pnl = 0.0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.wins = 0
        self.losses = 0
        self.returns: list[float] = []
        self.pnls: list[float] = []

        durations: list[float] = []
        self.max_drawdown = 0.0
        peak = 0.0
        running_pnl = 0.0

        for t in closed:
            cs = t.contract_size or 1
            entry_val = t.qty * cs * t.price
            exit_val = t.qty * cs * t.exit_price
            pnl = exit_val - entry_val if t.side.lower() == "buy" else entry_val - exit_val
            pnl -= t.fee

            self.pnls.append(pnl)
            self.total_pnl += pnl

            if pnl > 0:
                self.wins += 1
                self.gross_profit += pnl
            else:
                self.losses += 1
                self.gross_loss += abs(pnl)

            running_pnl += pnl
            if running_pnl > peak:
                peak = running_pnl
            dd = peak - running_pnl
            if dd > self.max_drawdown:
                self.max_drawdown = dd

            if t.exit_at and t.executed_at:
                dur = (t.exit_at - t.executed_at).total_seconds() / 3600
                durations.append(dur)

            ret = (t.exit_price - t.price) / t.price * (1 if t.side.lower() == "buy" else -1)
            self.returns.append(ret)

        self.win_rate = self.wins / len(closed) * 100 if closed else 0.0
        self.profit_factor = self.gross_profit / self.gross_loss if self.gross_loss > 0 else float("inf")
        self.avg_win = self.gross_profit / self.wins if self.wins > 0 else 0.0
        self.avg_loss = self.gross_loss / self.losses if self.losses > 0 else 0.0
        self.risk_reward = self.avg_win / self.avg_loss if self.avg_loss > 0 else 0.0

        win_rate_dec = self.win_rate / 100
        loss_rate_dec = 1 - win_rate_dec if closed else 0
        self.expectancy = (win_rate_dec * self.avg_win) - (loss_rate_dec * self.avg_loss)

        self.avg_duration = sum(durations) / len(durations) if durations else 0.0
        self.total_closed = len(closed)

        if len(self.returns) > 1:
            avg_ret = sum(self.returns) / len(self.returns)
            variance = sum((r - avg_ret) ** 2 for r in self.returns) / (len(self.returns) - 1)
            std = math.sqrt(variance)
            self.sharpe_ratio = (avg_ret / std * math.sqrt(252)) if std > 0 else 0.0
        else:
            self.sharpe_ratio = 0.0

        total_return_pct = (
            (self.total_pnl / abs(sum(t.qty * (t.contract_size or 1) * t.price for t in closed) / len(closed))) * 100
            if closed
            else 0.0
        )
        self.calmar_ratio = total_return_pct / self.max_drawdown if self.max_drawdown > 0 else 0.0


class PatternAnalysis:
    def __init__(self, trades: list[Trade]):
        self.trades = trades
        self._compute()

    def _compute(self):
        hour_data: dict[int, dict] = {}
        day_data: dict[int, dict] = {}
        symbol_data: dict[str, dict] = {}
        side_data: dict[str, dict] = {"buy": {"wins": 0, "total": 0, "pnl": 0.0}, "sell": {"wins": 0, "total": 0, "pnl": 0.0}}

        for t in self.trades:
            if not t.exit_price:
                continue
            cs = t.contract_size or 1
            entry_val = t.qty * cs * t.price
            exit_val = t.qty * cs * t.exit_price
            pnl = exit_val - entry_val if t.side.lower() == "buy" else entry_val - exit_val
            pnl -= t.fee

            dt = t.executed_at
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            hour = dt.hour
            day = dt.weekday()

            hour_data.setdefault(hour, {"wins": 0, "total": 0, "pnl": 0.0})
            hour_data[hour]["total"] += 1
            hour_data[hour]["pnl"] += pnl
            if pnl > 0:
                hour_data[hour]["wins"] += 1

            day_data.setdefault(day, {"wins": 0, "total": 0, "pnl": 0.0})
            day_data[day]["total"] += 1
            day_data[day]["pnl"] += pnl
            if pnl > 0:
                day_data[day]["wins"] += 1

            symbol_data.setdefault(t.symbol, {"wins": 0, "total": 0, "pnl": 0.0})
            symbol_data[t.symbol]["total"] += 1
            symbol_data[t.symbol]["pnl"] += pnl
            if pnl > 0:
                symbol_data[t.symbol]["wins"] += 1

            side_data[t.side.lower()]["total"] += 1
            side_data[t.side.lower()]["pnl"] += pnl
            if pnl > 0:
                side_data[t.side.lower()]["wins"] += 1

        def best_key(data, key_fn):
            items = [(k, key_fn(v)) for k, v in data.items() if v["total"] >= 2]
            return max(items, key=lambda x: x[1]) if items else ("N/A", 0)

        def worst_key(data, key_fn):
            items = [(k, key_fn(v)) for k, v in data.items() if v["total"] >= 2]
            return min(items, key=lambda x: x[1]) if items else ("N/A", 0)

        hour_names = [
            "00:00", "01:00", "02:00", "03:00", "04:00", "05:00",
            "06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
            "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
            "18:00", "19:00", "20:00", "21:00", "22:00", "23:00",
        ]
        day_names = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

        bh = best_key(hour_data, lambda v: v["wins"] / v["total"] * 100)
        wh = worst_key(hour_data, lambda v: v["wins"] / v["total"] * 100)
        self.best_hour = hour_names[bh[0]] if isinstance(bh[0], int) and bh[0] < 24 else "N/A"
        self.best_hour_winrate = round(bh[1], 1)
        self.worst_hour = hour_names[wh[0]] if isinstance(wh[0], int) and wh[0] < 24 else "N/A"
        self.worst_hour_winrate = round(wh[1], 1)

        bd = best_key(day_data, lambda v: v["wins"] / v["total"] * 100)
        wd_item = worst_key(day_data, lambda v: v["wins"] / v["total"] * 100)
        self.best_day = day_names[bd[0]] if isinstance(bd[0], int) and bd[0] < 7 else "N/A"
        self.best_day_winrate = round(bd[1], 1)
        self.worst_day = day_names[wd_item[0]] if isinstance(wd_item[0], int) and wd_item[0] < 7 else "N/A"
        self.worst_day_winrate = round(wd_item[1], 1)

        bs = best_key(symbol_data, lambda v: v["wins"] / v["total"] * 100)
        ws_item = worst_key(symbol_data, lambda v: v["wins"] / v["total"] * 100)
        self.best_symbol = bs[0]
        self.best_symbol_winrate = round(bs[1], 1)
        self.worst_symbol = ws_item[0]
        self.worst_symbol_winrate = round(ws_item[1], 1)

        def side_wr(s):
            return (s["wins"] / s["total"] * 100) if s["total"] > 0 else 0

        self.buy_winrate = round(side_wr(side_data["buy"]), 1)
        self.sell_winrate = round(side_data["sell"]["wins"] / side_data["sell"]["total"] * 100, 1) if side_data["sell"]["total"] > 0 else 0
        self.buy_count = side_data["buy"]["total"]
        self.sell_count = side_data["sell"]["total"]
        self.buy_pnl = round(side_data["buy"]["pnl"], 2)
        self.sell_pnl = round(side_data["sell"]["pnl"], 2)


class SequenceAnalysis:
    def __init__(self, trades: list[Trade]):
        self.trades = trades
        self._compute()

    def _compute(self):
        pnls: list[tuple[datetime, float, Trade]] = []
        for t in self.trades:
            if not t.exit_price:
                continue
            cs = t.contract_size or 1
            entry_val = t.qty * cs * t.price
            exit_val = t.qty * cs * t.exit_price
            pnl = exit_val - entry_val if t.side.lower() == "buy" else entry_val - exit_val
            pnl -= t.fee
            dt = t.executed_at
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            pnls.append((dt, pnl, t))

        pnls.sort(key=lambda x: x[0])

        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
        current_streak = 0
        current_streak_type = None
        streak_pnls: list[float] = []

        self.all_streaks: list[dict] = []
        for _, pnl, t in pnls:
            is_win = pnl > 0
            if current_streak_type == is_win:
                current_streak += 1
                streak_pnls.append(pnl)
            else:
                if current_streak > 0:
                    self.all_streaks.append({
                        "type": "win" if current_streak_type else "loss",
                        "count": current_streak,
                        "total_pnl": round(sum(streak_pnls), 2),
                    })
                current_streak = 1
                current_streak_type = is_win
                streak_pnls = [pnl]

            if is_win:
                self.max_consecutive_wins = max(self.max_consecutive_wins, current_streak)
            else:
                self.max_consecutive_losses = max(self.max_consecutive_losses, current_streak)

        if current_streak > 0:
            self.all_streaks.append({
                "type": "win" if current_streak_type else "loss",
                "count": current_streak,
                "total_pnl": round(sum(streak_pnls), 2),
            })

        win_streaks = [s for s in self.all_streaks if s["type"] == "win"]
        loss_streaks = [s for s in self.all_streaks if s["type"] == "loss"]
        self.avg_win_streak = round(
            sum(s["count"] for s in win_streaks) / len(win_streaks), 1
        ) if win_streaks else 0
        self.avg_loss_streak = round(
            sum(s["count"] for s in loss_streaks) / len(loss_streaks), 1
        ) if loss_streaks else 0

        total_gains = sum(s["total_pnl"] for s in win_streaks if s["total_pnl"] > 0)
        total_losses = sum(abs(s["total_pnl"]) for s in loss_streaks if s["total_pnl"] < 0)
        self.recovery_factor = round(total_gains / total_losses, 2) if total_losses > 0 else 0

        post_loss_sizes: list[float] = []
        for i, (_, pnl, t) in enumerate(pnls):
            if pnl < 0 and i + 1 < len(pnls):
                next_size = pnls[i + 1][2].qty * (pnls[i + 1][2].contract_size or 1)
                post_loss_sizes.append(next_size)

        avg_size = sum(t.qty * (t.contract_size or 1) for t in self.trades) / len(self.trades) if self.trades else 1
        self.post_loss_size_ratio = round(
            (sum(post_loss_sizes) / len(post_loss_sizes) / avg_size) if post_loss_sizes and avg_size else 0, 2
        )


class SizingAnalysis:
    def __init__(self, trades: list[Trade]):
        self.trades = trades
        self._compute()

    def _compute(self):
        trade_data: list[dict] = []
        for t in self.trades:
            if not t.exit_price:
                continue
            cs = t.contract_size or 1
            size = t.qty * cs
            entry_val = size * t.price
            exit_val = size * t.exit_price
            pnl = exit_val - entry_val if t.side.lower() == "buy" else entry_val - exit_val
            pnl -= t.fee
            trade_data.append({"size": size, "pnl": pnl, "pct": pnl / entry_val * 100 if entry_val else 0})

        self.avg_size = round(
            sum(d["size"] for d in trade_data) / len(trade_data), 4
        ) if trade_data else 0

        profitable = [d for d in trade_data if d["pnl"] > 0]
        unprofitable = [d for d in trade_data if d["pnl"] <= 0]
        self.avg_profitable_size = round(
            sum(d["size"] for d in profitable) / len(profitable), 4
        ) if profitable else 0
        self.avg_unprofitable_size = round(
            sum(d["size"] for d in unprofitable) / len(unprofitable), 4
        ) if unprofitable else 0

        n = len(trade_data)
        if n > 1:
            mean_size = sum(d["size"] for d in trade_data) / n
            mean_pnl = sum(d["pnl"] for d in trade_data) / n
            num = sum((d["size"] - mean_size) * (d["pnl"] - mean_pnl) for d in trade_data)
            den = math.sqrt(sum((d["size"] - mean_size) ** 2 for d in trade_data) * sum((d["pnl"] - mean_pnl) ** 2 for d in trade_data))
            self.size_pnl_correlation = round(num / den, 4) if den > 0 else 0
        else:
            self.size_pnl_correlation = 0

        if trade_data:
            sorted_by_pnl = sorted(trade_data, key=lambda d: d["pnl"] / d["size"] if d["size"] else 0, reverse=True)
            best_pct = sorted_by_pnl[:max(1, len(sorted_by_pnl) // 3)]
            self.optimal_size = round(
                sum(d["size"] for d in best_pct) / len(best_pct), 4
            ) if best_pct else 0

            self.avg_risk_pct = round(
                sum(abs(d["pct"]) for d in trade_data) / len(trade_data), 2
            )
        else:
            self.optimal_size = 0
            self.avg_risk_pct = 0


class NotesAnalysis:
    def __init__(self, trades: list[Trade]):
        self.trades = trades
        self._compute()

    def _compute(self):
        self.total = 0
        self.with_notes = 0
        self.without_notes = 0
        word_counts: dict[str, int] = {}
        positive_notes: list[str] = []
        negative_notes: list[str] = []

        strategy_keywords = {
            "trend": "Trend", "breakout": "Breakout", "scalp": "Scalp",
            "swing": "Swing", "reversal": "Reversal", "pattern": "Pattern",
            "support": "Support/Resistance", "resistance": "Support/Resistance",
            "fibonacci": "Fibonacci", "moving average": "Moving Average",
            "rsi": "RSI", "macd": "MACD", "bollinger": "Bollinger",
            "news": "News", "fundamental": "Fundamental", "momentum": "Momentum",
            "grid": "Grid", "martingale": "Martingale", "hedge": "Hedge",
        }
        emotion_keywords = {
            "frustrated": "Frustrated", "anxious": "Anxious", "nervous": "Nervous",
            "patient": "Patient", "confident": "Confident", "greedy": "Greedy",
            "fear": "Fear", "calm": "Calm", "discipline": "Disciplined",
            "impulsive": "Impulsive", "regret": "Regret", "lucky": "Lucky",
        }

        self.strategies: dict[str, int] = {}
        self.emotions: dict[str, int] = {}
        self.common_words: list[tuple[str, int]] = []
        self.positive_ratio = 0.0

        for t in self.trades:
            self.total += 1
            note = (t.notes or "").strip()
            if not note:
                self.without_notes += 1
                continue
            self.with_notes += 1

            cs = t.contract_size or 1
            entry_val = t.qty * cs * t.price
            exit_val = t.qty * cs * t.exit_price if t.exit_price else entry_val
            pnl = exit_val - entry_val if t.side.lower() == "buy" else entry_val - exit_val
            pnl -= t.fee

            if pnl > 0:
                positive_notes.append(note)
            else:
                negative_notes.append(note)

            lower = note.lower()
            words = lower.split()
            for w in words:
                cleaned = w.strip(".,!?;:\"'()[]{}")
                if len(cleaned) > 3:
                    word_counts[cleaned] = word_counts.get(cleaned, 0) + 1

            for kw, label in strategy_keywords.items():
                if kw in lower:
                    self.strategies[label] = self.strategies.get(label, 0) + 1

            for kw, label in emotion_keywords.items():
                if kw in lower:
                    self.emotions[label] = self.emotions.get(label, 0) + 1

        self.common_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        total_notes = self.with_notes
        self.positive_ratio = round(len(positive_notes) / total_notes * 100, 1) if total_notes > 0 else 0
        self.negative_ratio = round(len(negative_notes) / total_notes * 100, 1) if total_notes > 0 else 0
        self.no_notes_ratio = round(self.without_notes / self.total * 100, 1) if self.total > 0 else 0


def _build_summary(m: TradeMetrics, p: PatternAnalysis, seq: SequenceAnalysis, sz: SizingAnalysis, notes: NotesAnalysis) -> str:
    lines: list[str] = []

    total = m.total_closed
    if total == 0:
        return "Tahlil qilish uchun yopiq tradelar mavjud emas."

    lines.append(f"**1. Umumiy ko'rinish:** {total} ta trade, {round(m.win_rate, 1)}% g'alaba. Jami PnL: ${round(m.total_pnl, 2)}.")

    if m.sharpe_ratio >= 1:
        lines.append(f"**2. Risk boshqaruvi:** Sharpe {round(m.sharpe_ratio, 2)} — yaxshi. Drawdown ${round(m.max_drawdown, 2)}.")
    elif m.sharpe_ratio < 0:
        lines.append(f"**2. Risk boshqaruvi:** Sharpe {round(m.sharpe_ratio, 2)} — risk juda yuqori. Drawdown ${round(m.max_drawdown, 2)}.")

    if m.profit_factor is not None and m.profit_factor != float("inf"):
        if m.profit_factor >= 1.5:
            lines.append(f"**3. Samaradorlik:** Profit Factor {round(m.profit_factor, 2)} — foydali.")
        elif m.profit_factor < 1:
            lines.append(f"**3. Samaradorlik:** Profit Factor {round(m.profit_factor, 2)} — yo'qotish foydadan ko'p.")

    if m.expectancy > 0:
        lines.append(f"**4. Expectansiya:** +${round(m.expectancy, 2)}/trade — ijobiy.")
    elif m.expectancy < 0:
        lines.append(f"**4. Expectansiya:** ${round(m.expectancy, 2)}/trade — salbiy, strategiyani qayta ko'rib chiqing.")

    if m.avg_win > 0 and m.avg_loss > 0:
        rr = m.avg_win / m.avg_loss
        lines.append(f"**5. Risk/Reward:** 1:{round(rr, 2)}. {'Yaxshi' if rr >= 1.5 else 'Yaxshilash kerak'}.")

    if p.best_hour and p.best_hour != "N/A":
        lines.append(f"**6. Vaqt tahlili:** Eng yaxshi soat — {p.best_hour} ({p.best_hour_winrate}%). Eng yomon soat — {p.worst_hour if p.worst_hour else 'N/A'} ({p.worst_hour_winrate if p.worst_hour else 0}%).")

    if p.best_day and p.best_day != "N/A":
        lines.append(f"**7. Kun tahlili:** Eng yaxshi kun — {p.best_day} ({p.best_day_winrate}%).")

    if p.best_symbol and p.best_symbol != "N/A":
        lines.append(f"**8. Symbol tahlili:** Eng yaxshi — {p.best_symbol} ({p.best_symbol_winrate}%). Eng yomon — {p.worst_symbol if p.worst_symbol else 'N/A'} ({p.worst_symbol_winrate if p.worst_symbol else 0}%).")

    if seq.max_consecutive_wins > 0:
        lines.append(f"**9. Ketma-ketliklar:** {seq.max_consecutive_wins} ta ketma-ket yutuq, {seq.max_consecutive_losses} ta ketma-ket mag'lubiyat. Recovery factor: {round(seq.recovery_factor, 2)}.")

    if seq.post_loss_size_ratio > 1.2:
        lines.append(f"**10. Xatti-harakat:** Mag'lubiyatdan keyin pozitsiya hajmi {round(seq.post_loss_size_ratio * 100)}% ga oshadi — ehtiyot bo'ling.")

    if notes.no_notes_ratio > 30:
        lines.append(f"**11. Izohlar:** {notes.no_notes_ratio}% tradeda izoh yo'q. Har bir trade uchun izoh yozish tavsiya etiladi.")
    else:
        lines.append(f"**11. Izohlar:** {notes.with_notes} ta tradeda izoh mavjud. {notes.positive_ratio}% ijobiy, {notes.negative_ratio}% salbiy kontekst.")

    if notes.strategies:
        top_strat = sorted(notes.strategies.items(), key=lambda x: x[1], reverse=True)[:3]
        strat_str = ", ".join(f"{s} ({c} marta)" for s, c in top_strat)
        lines.append(f"**12. Strategiyalar:** {strat_str}")

    if notes.emotions:
        top_em = sorted(notes.emotions.items(), key=lambda x: x[1], reverse=True)[:3]
        em_str = ", ".join(f"{e}" for e, c in top_em)
        lines.append(f"**13. Psixologiya:** {em_str}")

    if sz.optimal_size > 0:
        lines.append(f"**14. Hajm tahlili:** Optimal pozitsiya hajmi ≈ {round(sz.optimal_size, 2)}. Foydali trades ({round(sz.avg_profitable_size, 2)}) vs zararl ({round(sz.avg_unprofitable_size, 2)}).")

    return "\n\n".join(lines)


class AnalyticsResult:
    def __init__(self, trades: list[Trade]):
        self.trades = trades
        self.trade_count = len(trades)
        self.metrics = TradeMetrics(trades)
        self.patterns = PatternAnalysis(trades)
        self.sequence = SequenceAnalysis(trades)
        self.sizing = SizingAnalysis(trades)
        self.notes = NotesAnalysis(trades)

    def to_dict(self) -> dict[str, Any]:
        symbol_map: dict[str, dict] = {}
        for t in self.trades:
            if not t.exit_price:
                continue
            cs = t.contract_size or 1
            entry_val = t.qty * cs * t.price
            exit_val = t.qty * cs * t.exit_price
            pnl = exit_val - entry_val if t.side.lower() == "buy" else entry_val - exit_val
            pnl -= t.fee
            symbol_map.setdefault(t.symbol, {"count": 0, "wins": 0, "pnl": 0})
            symbol_map[t.symbol]["count"] += 1
            symbol_map[t.symbol]["pnl"] += pnl
            if pnl > 0:
                symbol_map[t.symbol]["wins"] += 1

        symbols_list = [
            {"symbol": s, "count": d["count"], "wins": d["wins"], "pnl": round(d["pnl"], 2)}
            for s, d in sorted(symbol_map.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

        return {
            "trade_count": self.trade_count,
            "symbols": symbols_list,
            "metrics": {
                "total_closed": self.metrics.total_closed,
                "total_pnl": round(self.metrics.total_pnl, 2),
                "win_rate": round(self.metrics.win_rate, 1),
                "profit_factor": round(self.metrics.profit_factor, 2) if self.metrics.profit_factor != float("inf") else None,
                "sharpe_ratio": round(self.metrics.sharpe_ratio, 3),
                "max_drawdown": round(self.metrics.max_drawdown, 2),
                "calmar_ratio": round(self.metrics.calmar_ratio, 3),
                "avg_win": round(self.metrics.avg_win, 2),
                "avg_loss": round(self.metrics.avg_loss, 2),
                "risk_reward_ratio": round(self.metrics.risk_reward, 2),
                "expectancy": round(self.metrics.expectancy, 2),
                "avg_duration_hours": round(self.metrics.avg_duration, 1),
                "gross_profit": round(self.metrics.gross_profit, 2),
                "gross_loss": round(self.metrics.gross_loss, 2),
            },
            "patterns": {
                "best_hour": {"hour": self.patterns.best_hour, "win_rate": self.patterns.best_hour_winrate},
                "worst_hour": {"hour": self.patterns.worst_hour, "win_rate": self.patterns.worst_hour_winrate},
                "best_day": {"day": self.patterns.best_day, "win_rate": self.patterns.best_day_winrate},
                "worst_day": {"day": self.patterns.worst_day, "win_rate": self.patterns.worst_day_winrate},
                "best_symbol": {"symbol": self.patterns.best_symbol, "win_rate": self.patterns.best_symbol_winrate},
                "worst_symbol": {"symbol": self.patterns.worst_symbol, "win_rate": self.patterns.worst_symbol_winrate},
                "buy": {"count": self.patterns.buy_count, "win_rate": self.patterns.buy_winrate, "pnl": self.patterns.buy_pnl},
                "sell": {"count": self.patterns.sell_count, "win_rate": self.patterns.sell_winrate, "pnl": self.patterns.sell_pnl},
            },
            "sequence": {
                "max_consecutive_wins": self.sequence.max_consecutive_wins,
                "max_consecutive_losses": self.sequence.max_consecutive_losses,
                "avg_win_streak": self.sequence.avg_win_streak,
                "avg_loss_streak": self.sequence.avg_loss_streak,
                "recovery_factor": self.sequence.recovery_factor,
                "post_loss_size_ratio": self.sequence.post_loss_size_ratio,
                "streaks": self.sequence.all_streaks[-10:],
            },
            "sizing": {
                "avg_size": self.sizing.avg_size,
                "avg_profitable_size": self.sizing.avg_profitable_size,
                "avg_unprofitable_size": self.sizing.avg_unprofitable_size,
                "size_pnl_correlation": self.sizing.size_pnl_correlation,
                "optimal_size": self.sizing.optimal_size,
                "avg_risk_percent": self.sizing.avg_risk_pct,
            },
            "notes_analysis": {
                "total": self.notes.total,
                "with_notes": self.notes.with_notes,
                "without_notes": self.notes.without_notes,
                "no_notes_ratio": self.notes.no_notes_ratio,
                "positive_ratio": self.notes.positive_ratio,
                "negative_ratio": self.notes.negative_ratio,
                "common_words": self.notes.common_words[:10],
                "strategies": dict(sorted(self.notes.strategies.items(), key=lambda x: x[1], reverse=True)),
                "emotions": dict(sorted(self.notes.emotions.items(), key=lambda x: x[1], reverse=True)),
            },
            "summary": _build_summary(self.metrics, self.patterns, self.sequence, self.sizing, self.notes),
            "recent_trades": self._recent_trades(),
        }

    def _recent_trades(self) -> list[dict]:
        sorted_trades = sorted(self.trades, key=lambda t: t.executed_at, reverse=True)
        result: list[dict] = []
        for t in sorted_trades[:10]:
            cs = t.contract_size or 1
            entry_val = t.qty * cs * t.price
            if t.exit_price:
                exit_val = t.qty * cs * t.exit_price
                pnl = exit_val - entry_val if t.side.lower() == "buy" else entry_val - exit_val
                pnl -= t.fee
            else:
                pnl = 0.0
            dt = t.executed_at
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            result.append({
                "symbol": t.symbol,
                "side": t.side,
                "qty": t.qty,
                "price": t.price,
                "exit_price": t.exit_price,
                "pnl": round(pnl, 2),
                "executed_at": dt.strftime("%Y-%m-%d %H:%M"),
            })
        return result


def compute_analytics(trades: list[Trade]) -> AnalyticsResult:
    return AnalyticsResult(trades)
