from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.benchmark_core import compare_reports, run_benchmark


class PerformanceContractTests(unittest.TestCase):
    def test_small_benchmark_report_has_all_core_scenarios(self) -> None:
        report = run_benchmark([100])

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["sizes"], [100])
        self.assertEqual(
            {case["name"] for case in report["cases"]},
            {"rules", "preview", "natural_sort"},
        )
        self.assertTrue(all(case["seconds"] >= 0 for case in report["cases"]))
        self.assertTrue(all(case["peak_traced_bytes"] >= 0 for case in report["cases"]))

    def test_comparison_flags_only_material_slowdowns(self) -> None:
        baseline = {"cases": [{"name": "preview", "items": 1000, "seconds": 1.0}]}
        current = {"cases": [{"name": "preview", "items": 1000, "seconds": 2.0}]}

        self.assertEqual(len(compare_reports(current, baseline, 1.75)), 1)
        self.assertEqual(compare_reports(current, baseline, 2.5), [])


if __name__ == "__main__":
    unittest.main()
