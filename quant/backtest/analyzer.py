from __future__ import annotations

from quant.common.utils import safe_mean

from .result import BacktestResult


class Analyzer:
    def analyze(self, result: BacktestResult) -> dict[str, float]:
        if not result.equity_curve:
            return {
                "total_return": 0.0,
                "num_trades": 0.0,
                "average_equity": 0.0,
                "ending_equity": 0.0,
                "max_drawdown": 0.0,
            }

        average_equity = safe_mean(value for _, value in result.equity_curve)
        peak = result.equity_curve[0][1]
        max_drawdown = 0.0
        for _, equity in result.equity_curve:
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak if peak else 0.0
            max_drawdown = max(max_drawdown, drawdown)
        return {
            "total_return": result.total_return,
            "num_trades": float(len(result.fills)),
            "average_equity": average_equity,
            "ending_equity": result.end_equity,
            "max_drawdown": max_drawdown,
        }
