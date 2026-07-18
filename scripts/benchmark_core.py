from __future__ import annotations

import argparse
import gc
import json
import platform
import sys
import tracemalloc
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batch_renamer.core.models import FileItem, RuleSettings
from batch_renamer.core.preview import build_preview
from batch_renamer.core.rules import apply_rules
from batch_renamer.core.sorting import natural_sort_key


def _measure(name: str, item_count: int, operation: Callable[[], None]) -> dict[str, object]:
    gc.collect()
    tracemalloc.start()
    started = perf_counter()
    operation()
    elapsed = perf_counter() - started
    _current, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "name": name,
        "items": item_count,
        "seconds": round(elapsed, 6),
        "items_per_second": round(item_count / elapsed, 2) if elapsed else None,
        "peak_traced_bytes": peak_bytes,
    }


def run_benchmark(sizes: list[int]) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    settings = RuleSettings(
        find_enabled=True,
        find_text="plate",
        replace_text="shot",
        prefix_enabled=True,
        prefix_text="render_",
        number_enabled=True,
        number_digits=6,
        number_separator="_",
    )

    for size in sizes:
        stems = [f"plate_{index}" for index in range(size)]
        cases.append(
            _measure(
                "rules",
                size,
                lambda stems=stems: [apply_rules(stem, ".EXR", settings, index) for index, stem in enumerate(stems)],
            )
        )

        items = [FileItem(Path("benchmark-input") / f"plate_{index}.EXR") for index in range(size)]
        cases.append(
            _measure(
                "preview",
                size,
                lambda items=items: build_preview(items, settings),
            )
        )

        names = [f"shot_{index}.exr" for index in range(size, 0, -1)]
        cases.append(
            _measure(
                "natural_sort",
                size,
                lambda names=names: sorted(names, key=natural_sort_key),
            )
        )

    return {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "sizes": sizes,
        "cases": cases,
        "notes": [
            "使用纯内存文件项和不存在的基准路径，不读取或改名用户文件。",
            "peak_traced_bytes 是 Python tracemalloc 峰值，不代表进程总内存。",
            "单次结果是基线证据，不等同于完整性能优化结论。",
        ],
    }


def compare_reports(current: dict[str, object], baseline: dict[str, object], max_ratio: float) -> list[str]:
    baseline_cases = {
        (case["name"], case["items"]): case
        for case in baseline.get("cases", [])
        if isinstance(case, dict)
    }
    failures: list[str] = []
    for case in current.get("cases", []):
        if not isinstance(case, dict):
            continue
        previous = baseline_cases.get((case.get("name"), case.get("items")))
        if not previous:
            continue
        current_seconds = float(case["seconds"])
        baseline_seconds = float(previous["seconds"])
        if current_seconds > baseline_seconds * max_ratio and current_seconds - baseline_seconds > 0.05:
            failures.append(
                f"{case['name']} {case['items']} 条：{current_seconds:.3f}s，"
                f"基线 {baseline_seconds:.3f}s，超过 {max_ratio:.2f} 倍"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="南枫批量改名核心性能基线")
    parser.add_argument("--sizes", nargs="+", type=int, default=[1000, 10000, 50000])
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "docs" / "performance-baseline.json")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--max-slowdown-ratio", type=float, default=1.75)
    args = parser.parse_args()

    report = run_benchmark(args.sizes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.compare:
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))
        failures = compare_reports(report, baseline, args.max_slowdown_ratio)
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}")
            return 1

    for case in report["cases"]:
        print(
            f"{case['name']:12s} {case['items']:>6} 条  "
            f"{case['seconds']:>8.3f}s  {case['items_per_second']:>10.0f} 条/秒"
        )
    print(f"报告：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
