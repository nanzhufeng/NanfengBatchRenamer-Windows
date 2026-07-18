from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import RenamePlan, RenameResult


class RenameExecutor:
    """负责真实改名、日志和最近一次撤销。"""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.logs_dir = project_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.undo_file = self.logs_dir / "last_undo.json"

    def execute(self, plans: list[RenamePlan]) -> list[RenameResult]:
        results: list[RenameResult] = []
        undo_entries: list[dict[str, str]] = []

        for plan in plans:
            try:
                if not plan.source_path.exists():
                    raise FileNotFoundError("源文件不存在")
                if plan.target_path.exists() and plan.source_path.resolve() != plan.target_path.resolve():
                    raise FileExistsError("目标文件已存在")

                plan.source_path.rename(plan.target_path)
                results.append(RenameResult(plan.source_path, plan.target_path, True, "已完成"))
                undo_entries.append({"source": str(plan.source_path), "target": str(plan.target_path)})
            except OSError as exc:
                results.append(RenameResult(plan.source_path, plan.target_path, False, str(exc)))

        self._write_run_log(results)
        if undo_entries:
            self.undo_file.write_text(
                json.dumps(
                    {
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "items": undo_entries,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return results

    def undo_last(self) -> list[RenameResult]:
        if not self.undo_file.exists():
            return [RenameResult(Path(), Path(), False, "没有可撤销的记录")]

        data = json.loads(self.undo_file.read_text(encoding="utf-8"))
        entries = list(reversed(data.get("items", [])))
        if not entries:
            return [RenameResult(Path(), Path(), False, "没有可撤销的记录")]

        results: list[RenameResult] = []

        for entry in entries:
            original = Path(entry["source"])
            current = Path(entry["target"])
            try:
                if not current.exists():
                    raise FileNotFoundError("当前文件不存在，可能已被移动或再次改名")
                if original.exists():
                    raise FileExistsError("原路径已有文件，无法安全撤销")
                current.rename(original)
                results.append(RenameResult(current, original, True, "已撤销"))
            except OSError as exc:
                results.append(RenameResult(current, original, False, str(exc)))

        self._write_undo_log(results)
        if results and all(result.ok for result in results):
            self.undo_file.write_text(
                json.dumps(
                    {
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "items": [],
                        "note": "最近一次撤销已完成，不能重复撤销。",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return results

    def _write_run_log(self, results: list[RenameResult]) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.logs_dir / f"rename_{stamp}.json"
        log_file.write_text(
            json.dumps(
                [
                    {
                        "source": str(result.source_path),
                        "target": str(result.target_path),
                        "ok": result.ok,
                        "message": result.message,
                    }
                    for result in results
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_undo_log(self, results: list[RenameResult]) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.logs_dir / f"undo_{stamp}.json"
        log_file.write_text(
            json.dumps(
                [
                    {
                        "from": str(result.source_path),
                        "to": str(result.target_path),
                        "ok": result.ok,
                        "message": result.message,
                    }
                    for result in results
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
