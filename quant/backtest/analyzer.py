from __future__ import annotations

from quant.common.utils import safe_mean

from .result import BacktestResult


class Analyzer:
    def analyze(self, result: BacktestResult) -> dict[str, float]:
        if not result.equity_curve:
            return {"total_return": 0.0, "num_trades": 0, "average_equity": 0.0}

        start_equity = result.equity_curve[0][1]
        end_equity = result.equity_curve[-1][1]
        total_return = (end_equity - start_equity) / start_equity if start_equity else 0.0
        average_equity = safe_mean(value for _, value in result.equity_curve)
        return {
            "total_return": total_return,
            "num_trades": float(len(result.fills)),
            "average_equity": average_equity,
        }
