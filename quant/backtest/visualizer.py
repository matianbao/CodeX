from __future__ import annotations

import html
from pathlib import Path

from quant.common.logging_utils import get_logger
from quant.common.types import OrderSide

from .result import BacktestResult

logger = get_logger("backtest.visualizer")


class BacktestVisualizer:
    def render_equity_svg(self, result: BacktestResult, width: int = 900, height: int = 320) -> str:
        if not result.equity_curve:
            return '<svg width="900" height="320" xmlns="http://www.w3.org/2000/svg"></svg>'

        values = [equity for _, equity in result.equity_curve]
        min_value = min(values)
        max_value = max(values)
        span = max(max_value - min_value, 1e-9)
        chart_width = width - 80
        chart_height = height - 80

        def scale_x(index: int) -> float:
            if len(values) == 1:
                return 40.0
            return 40 + chart_width * index / (len(values) - 1)

        def scale_y(value: float) -> float:
            return 40 + chart_height * (1 - (value - min_value) / span)

        points = " ".join(f"{scale_x(index):.2f},{scale_y(value):.2f}" for index, value in enumerate(values))
        labels = "".join(
            f'<text x="{scale_x(index):.2f}" y="{height - 20}" font-size="11" text-anchor="middle">{dt.strftime("%m-%d")}</text>'
            for index, (dt, _) in enumerate(result.equity_curve)
        )
        markers: list[str] = []
        for fill in result.fills:
            matching_index = next((idx for idx, (dt, _) in enumerate(result.equity_curve) if dt == fill.dt), None)
            if matching_index is None:
                continue
            color = "#0f9d58" if fill.side == OrderSide.BUY else "#db4437"
            x = scale_x(matching_index)
            y = scale_y(next(equity for dt, equity in result.equity_curve if dt == fill.dt))
            markers.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"><title>{fill.side.value} {fill.symbol} x {fill.qty} @ {fill.price:.2f}</title></circle>'
            )

        return (
            f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Equity curve">'
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" stroke="#d0d7de"/>'
            f'<line x1="40" y1="40" x2="40" y2="{height - 40}" stroke="#9aa4b2"/>'
            f'<line x1="40" y1="{height - 40}" x2="{width - 40}" y2="{height - 40}" stroke="#9aa4b2"/>'
            f'<polyline fill="none" stroke="#1a73e8" stroke-width="3" points="{points}"/>'
            f'<text x="40" y="24" font-size="12">max: {max_value:.2f}</text>'
            f'<text x="40" y="{height - 48}" font-size="12">min: {min_value:.2f}</text>'
            f'{labels}{"".join(markers)}</svg>'
        )

    def render_metrics_html(self, analysis: dict[str, float]) -> str:
        items = "".join(
            f'<div class="metric"><span class="label">{html.escape(key)}</span><span class="value">{value:.4f}</span></div>'
            for key, value in analysis.items()
        )
        return f'<section class="metrics">{items}</section>'

    def render_fills_table(self, result: BacktestResult) -> str:
        if not result.fills:
            return '<p>No fills generated.</p>'
        rows = "".join(
            '<tr>'
            f'<td>{fill.dt.strftime("%Y-%m-%d")}</td>'
            f'<td>{html.escape(fill.symbol)}</td>'
            f'<td>{fill.side.value}</td>'
            f'<td>{fill.qty}</td>'
            f'<td>{fill.price:.2f}</td>'
            f'<td>{fill.commission:.2f}</td>'
            '</tr>'
            for fill in result.fills
        )
        return (
            '<table><thead><tr><th>Date</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Commission</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )

    def build_html_report(self, result: BacktestResult, analysis: dict[str, float], title: str = 'Backtest Report') -> str:
        svg = self.render_equity_svg(result)
        metrics = self.render_metrics_html(analysis)
        fills_table = self.render_fills_table(result)
        safe_title = html.escape(title)
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{safe_title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2328; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 16px 0 24px; }}
    .metric {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 12px; background: #f6f8fa; }}
    .label {{ display: block; color: #57606a; font-size: 12px; margin-bottom: 4px; }}
    .value {{ font-size: 18px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
    th, td {{ border: 1px solid #d0d7de; padding: 8px 10px; text-align: left; }}
    th {{ background: #f6f8fa; }}
    details {{ margin-top: 20px; }}
  </style>
</head>
<body>
  <h1>{safe_title}</h1>
  {metrics}
  <section>
    <h2>Equity Curve</h2>
    {svg}
  </section>
  <details open>
    <summary>Trade Fills</summary>
    {fills_table}
  </details>
</body>
</html>'''

    def save_report(self, result: BacktestResult, analysis: dict[str, float], output_dir: str | Path, report_name: str = 'backtest_report') -> tuple[Path, Path]:
        logger.info("save_report report_name=%s output_dir=%s", report_name, output_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        svg_path = output_path / f'{report_name}_equity.svg'
        html_path = output_path / f'{report_name}.html'
        svg_path.write_text(self.render_equity_svg(result), encoding='utf-8')
        html_path.write_text(self.build_html_report(result, analysis, title=report_name.replace('_', ' ').title()), encoding='utf-8')
        logger.info("report_saved html=%s svg=%s", html_path, svg_path)
        return html_path, svg_path
