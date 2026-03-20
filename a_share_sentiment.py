from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclasses.dataclass
class MarketSnapshot:
    trade_date: str
    total_turnover_billion: Optional[float] = None
    sh_index_pct: Optional[float] = None
    sz_index_pct: Optional[float] = None
    cyb_index_pct: Optional[float] = None
    up_count: Optional[int] = None
    down_count: Optional[int] = None
    flat_count: Optional[int] = None
    limit_up_count: Optional[int] = None
    limit_down_count: Optional[int] = None
    northbound_net_billion: Optional[float] = None
    margin_balance_billion: Optional[float] = None
    margin_balance_change_billion: Optional[float] = None
    defensive_leadership: Optional[bool] = None
    notes: Optional[str] = None


@dataclasses.dataclass
class DimensionScore:
    name: str
    score: float
    reason: str


@dataclasses.dataclass
class SentimentReport:
    snapshot: MarketSnapshot
    total_score: float
    label: str
    dimensions: List[DimensionScore]
    advice: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot": dataclasses.asdict(self.snapshot),
            "total_score": round(self.total_score, 2),
            "label": self.label,
            "dimensions": [dataclasses.asdict(x) for x in self.dimensions],
            "advice": self.advice,
        }


class SentimentEvaluator:
    def evaluate(self, snapshot: MarketSnapshot) -> SentimentReport:
        dimensions = [
            self._turnover_score(snapshot),
            self._index_score(snapshot),
            self._breadth_score(snapshot),
            self._limit_score(snapshot),
            self._leverage_score(snapshot),
            self._style_score(snapshot),
        ]
        total_score = round(sum(item.score for item in dimensions) / len(dimensions), 2)
        label = self._label(total_score)
        advice = self._advice(total_score, snapshot)
        return SentimentReport(
            snapshot=snapshot,
            total_score=total_score,
            label=label,
            dimensions=dimensions,
            advice=advice,
        )

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, value))

    def _turnover_score(self, snapshot: MarketSnapshot) -> DimensionScore:
        turnover = snapshot.total_turnover_billion
        if turnover is None:
            return DimensionScore("成交额", 50.0, "缺少成交额数据，按中性处理。")
        score = 20 + 80 * min(turnover / 30000.0, 1.0)
        if turnover >= 30000:
            reason = f"两市成交额约 {turnover:.0f} 亿元，处于高活跃区间。"
        elif turnover >= 18000:
            reason = f"两市成交额约 {turnover:.0f} 亿元，活跃度中等偏高。"
        else:
            reason = f"两市成交额约 {turnover:.0f} 亿元，显示风险偏好偏弱。"
        return DimensionScore("成交额", round(score, 2), reason)

    def _index_score(self, snapshot: MarketSnapshot) -> DimensionScore:
        values = [x for x in [snapshot.sh_index_pct, snapshot.sz_index_pct, snapshot.cyb_index_pct] if x is not None]
        if not values:
            return DimensionScore("指数强弱", 50.0, "缺少指数涨跌幅数据，按中性处理。")
        avg_change = statistics.mean(values)
        score = self._clamp(50 + avg_change * 15)
        reason = f"核心指数平均涨跌幅约 {avg_change:.2f}%，指数层面{'偏强' if avg_change > 0.5 else '偏弱' if avg_change < -0.5 else '中性震荡'}。"
        return DimensionScore("指数强弱", round(score, 2), reason)

    def _breadth_score(self, snapshot: MarketSnapshot) -> DimensionScore:
        if snapshot.up_count is None or snapshot.down_count is None:
            return DimensionScore("市场宽度", 50.0, "缺少上涨/下跌家数数据，按中性处理。")
        total = snapshot.up_count + snapshot.down_count + (snapshot.flat_count or 0)
        if total <= 0:
            return DimensionScore("市场宽度", 50.0, "市场家数总量无效，按中性处理。")
        breadth = (snapshot.up_count - snapshot.down_count) / total
        score = self._clamp(50 + breadth * 120)
        reason = (
            f"上涨 {snapshot.up_count} 家、下跌 {snapshot.down_count} 家，"
            f"市场宽度为 {breadth:.2%}，{'普涨扩散较好' if breadth > 0.1 else '亏钱效应偏强' if breadth < -0.1 else '分化明显'}。"
        )
        return DimensionScore("市场宽度", round(score, 2), reason)

    def _limit_score(self, snapshot: MarketSnapshot) -> DimensionScore:
        if snapshot.limit_up_count is None or snapshot.limit_down_count is None:
            return DimensionScore("赚钱效应", 50.0, "缺少涨停/跌停数据，按中性处理。")
        ratio = (snapshot.limit_up_count + 1) / (snapshot.limit_down_count + 1)
        score = self._clamp(50 + math.log(ratio, 2) * 15)
        reason = (
            f"涨停 {snapshot.limit_up_count} 家、跌停 {snapshot.limit_down_count} 家，"
            f"强弱比约 {ratio:.2f}，{'短线情绪偏暖' if ratio > 2 else '短线情绪承压' if ratio < 0.8 else '短线情绪一般'}。"
        )
        return DimensionScore("赚钱效应", round(score, 2), reason)

    def _leverage_score(self, snapshot: MarketSnapshot) -> DimensionScore:
        balance = snapshot.margin_balance_billion
        change = snapshot.margin_balance_change_billion
        if balance is None and change is None and snapshot.northbound_net_billion is None:
            return DimensionScore("杠杆/增量资金", 50.0, "缺少两融或北向资金数据，按中性处理。")

        base = 50.0
        reasons: List[str] = []
        if balance is not None:
            if balance >= 26000:
                base += 15
                reasons.append(f"两融余额约 {balance:.0f} 亿元，处于高位区间")
            elif balance >= 18000:
                base += 5
                reasons.append(f"两融余额约 {balance:.0f} 亿元，风险偏好仍在")
            else:
                base -= 10
                reasons.append(f"两融余额约 {balance:.0f} 亿元，杠杆情绪偏弱")
        if change is not None:
            base += max(-12, min(12, change * 4))
            reasons.append(f"两融余额日变动 {change:+.1f} 亿元")
        if snapshot.northbound_net_billion is not None:
            flow = snapshot.northbound_net_billion
            base += max(-10, min(10, flow / 5))
            reasons.append(f"北向资金净流入 {flow:+.1f} 亿元")
        return DimensionScore("杠杆/增量资金", round(self._clamp(base), 2), "，".join(reasons) + "。")

    def _style_score(self, snapshot: MarketSnapshot) -> DimensionScore:
        defensive = snapshot.defensive_leadership
        if defensive is None:
            return DimensionScore("风格方向", 50.0, "缺少防御/进攻风格数据，按中性处理。")
        score = 40.0 if defensive else 65.0
        reason = "防御类板块领涨，说明资金偏谨慎。" if defensive else "进攻型板块占优，说明风险偏好回升。"
        return DimensionScore("风格方向", score, reason)

    @staticmethod
    def _label(score: float) -> str:
        if score >= 80:
            return "亢奋"
        if score >= 65:
            return "偏暖"
        if score >= 45:
            return "中性偏谨慎"
        if score >= 30:
            return "偏冷"
        return "恐慌"

    @staticmethod
    def _advice(score: float, snapshot: MarketSnapshot) -> str:
        if score >= 65:
            return "情绪进入偏暖区，可优先观察主线持续性和放量进攻板块，但仍需警惕一致性过强后的回撤。"
        if score >= 45:
            return "当前更像分化博弈市，适合低吸、轮动和分歧回流，不宜无脑追高。"
        return "情绪偏弱，优先控制仓位，等待成交额、市场宽度和主线修复共振后再提升进攻性。"


class JsonFileProvider:
    def __init__(self, path: Path):
        self.path = path

    def fetch(self) -> MarketSnapshot:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return MarketSnapshot(**payload)


class CsvFileProvider:
    def __init__(self, path: Path):
        self.path = path

    def fetch(self) -> MarketSnapshot:
        with self.path.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise ValueError(f"CSV 文件为空: {self.path}")
        row = rows[-1]
        int_fields = {"up_count", "down_count", "flat_count", "limit_up_count", "limit_down_count"}
        float_fields = {
            "total_turnover_billion",
            "sh_index_pct",
            "sz_index_pct",
            "cyb_index_pct",
            "northbound_net_billion",
            "margin_balance_billion",
            "margin_balance_change_billion",
        }
        bool_fields = {"defensive_leadership"}

        normalized: Dict[str, Any] = {}
        for field in dataclasses.fields(MarketSnapshot):
            value = row.get(field.name)
            if value in (None, ""):
                normalized[field.name] = None
                continue
            if field.name in int_fields:
                normalized[field.name] = int(float(value))
            elif field.name in float_fields:
                normalized[field.name] = float(value)
            elif field.name in bool_fields:
                normalized[field.name] = value.lower() in {"1", "true", "yes", "y"}
            else:
                normalized[field.name] = value
        if not normalized.get("trade_date"):
            normalized["trade_date"] = dt.date.today().isoformat()
        return MarketSnapshot(**normalized)


class DemoProvider:
    def fetch(self) -> MarketSnapshot:
        return MarketSnapshot(
            trade_date=dt.date.today().isoformat(),
            total_turnover_billion=24680,
            sh_index_pct=0.38,
            sz_index_pct=-0.12,
            cyb_index_pct=-0.45,
            up_count=1980,
            down_count=3080,
            flat_count=120,
            limit_up_count=62,
            limit_down_count=9,
            northbound_net_billion=18.6,
            margin_balance_billion=25880,
            margin_balance_change_billion=-12.4,
            defensive_leadership=True,
            notes="演示数据：高成交、宽度偏弱、防御风格占优。",
        )


class AkshareProvider:
    def fetch(self) -> MarketSnapshot:
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:
            raise RuntimeError("未安装 akshare，无法自动抓取A股数据。请先 `pip install akshare pandas`。") from exc

        trade_date = dt.date.today().isoformat()
        spot = ak.stock_zh_a_spot_em()
        index_spot = ak.stock_zh_index_spot_em()

        turnover_billion = float(spot["成交额"].sum() / 100000000)
        up_count = int((spot["涨跌幅"] > 0).sum())
        down_count = int((spot["涨跌幅"] < 0).sum())
        flat_count = int((spot["涨跌幅"] == 0).sum())

        def index_pct(name: str) -> Optional[float]:
            matched = index_spot[index_spot["名称"] == name]
            if matched.empty:
                return None
            return float(matched.iloc[0]["涨跌幅"])

        limit_up_count: Optional[int] = None
        limit_down_count: Optional[int] = None
        today_text = dt.date.today().strftime("%Y%m%d")
        try:
            limit_up_count = len(ak.stock_zt_pool_em(date=today_text))
        except Exception:
            pass
        try:
            limit_down_count = len(ak.stock_zt_pool_dtgc_em(date=today_text))
        except Exception:
            pass

        northbound: Optional[float] = None
        try:
            north_df = ak.stock_hsgt_north_net_flow_in_em()
            latest = north_df.tail(1).iloc[0]
            northbound = float(latest.iloc[-1])
        except Exception:
            pass

        return MarketSnapshot(
            trade_date=trade_date,
            total_turnover_billion=round(turnover_billion, 2),
            sh_index_pct=index_pct("上证系列指数") or index_pct("上证指数"),
            sz_index_pct=index_pct("深证成指"),
            cyb_index_pct=index_pct("创业板指"),
            up_count=up_count,
            down_count=down_count,
            flat_count=flat_count,
            limit_up_count=limit_up_count,
            limit_down_count=limit_down_count,
            northbound_net_billion=northbound,
            margin_balance_billion=None,
            margin_balance_change_billion=None,
            defensive_leadership=None,
            notes="自动抓取数据。若需更准确的两融或风格判断，可接入券商/交易所数据源补充。",
        )


def write_report(report: SentimentReport, output_path: Optional[Path]) -> None:
    text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(render_report(report))
    if output_path:
        print(f"\n结果已写入: {output_path}")


def render_report(report: SentimentReport) -> str:
    lines = [
        f"交易日期: {report.snapshot.trade_date}",
        f"情绪得分: {report.total_score:.2f}/100",
        f"情绪标签: {report.label}",
        "",
        "维度打分:",
    ]
    for item in report.dimensions:
        lines.append(f"- {item.name}: {item.score:.2f} | {item.reason}")
    if report.snapshot.notes:
        lines.extend(["", f"备注: {report.snapshot.notes}"])
    lines.extend(["", f"策略建议: {report.advice}"])
    return "\n".join(lines)


def next_run_time(run_at: str, now: Optional[dt.datetime] = None) -> dt.datetime:
    now = now or dt.datetime.now()
    hour, minute = map(int, run_at.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return target


def build_provider(args: argparse.Namespace):
    if args.demo:
        return DemoProvider()
    if args.input_json:
        return JsonFileProvider(Path(args.input_json))
    if args.input_csv:
        return CsvFileProvider(Path(args.input_csv))
    if args.auto_fetch:
        return AkshareProvider()
    raise SystemExit("请至少指定 --demo、--input-json、--input-csv 或 --auto-fetch 之一。")


def run_once(args: argparse.Namespace) -> SentimentReport:
    provider = build_provider(args)
    snapshot = provider.fetch()
    report = SentimentEvaluator().evaluate(snapshot)
    output_path = Path(args.output) if args.output else None
    write_report(report, output_path)
    return report


def run_schedule(args: argparse.Namespace) -> None:
    while True:
        target = next_run_time(args.schedule_at)
        print(f"下一次执行时间: {target.isoformat(sep=' ', timespec='seconds')}")
        sleep_seconds = max(1, int((target - dt.datetime.now()).total_seconds()))
        time.sleep(sleep_seconds)
        try:
            run_once(args)
        except Exception as exc:  # noqa: BLE001
            print(f"定时任务执行失败: {exc}", file=sys.stderr)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A股日度交易情绪评估器")
    parser.add_argument("--demo", action="store_true", help="使用内置演示数据运行")
    parser.add_argument("--input-json", help="从 JSON 文件读取 MarketSnapshot 数据")
    parser.add_argument("--input-csv", help="从 CSV 文件读取 MarketSnapshot 数据，默认取最后一行")
    parser.add_argument("--auto-fetch", action="store_true", help="使用 akshare 自动抓取当日A股数据")
    parser.add_argument("--output", help="将评估结果输出为 JSON 文件")
    parser.add_argument("--schedule-at", help="以 HH:MM 形式指定每日定时执行时间")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    if args.schedule_at:
        run_schedule(args)
        return 0
    run_once(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
