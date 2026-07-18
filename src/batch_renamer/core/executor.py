from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .models import RenamePlan, RenameResult


RenameOperation = Callable[[Path, Path], None]


@dataclass
class _TransactionItem:
    plan: RenamePlan
    temporary_path: Path
    current_path: Path
    moved: bool = False


class RenameExecutor:
    """负责事务式真实改名、日志、恢复清单和最近一次撤销。"""

    def __init__(self, project_dir: Path, rename_operation: RenameOperation | None = None) -> None:
        self.project_dir = project_dir
        self.logs_dir = project_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.undo_file = self.logs_dir / "last_undo.json"
        self._rename_operation = rename_operation or self._rename
        self.last_recovery_file: Path | None = None

    def execute(self, plans: list[RenamePlan]) -> list[RenameResult]:
        results = self._run_transaction(plans, "已完成")
        self._write_run_log(results)

        if plans and results and all(result.ok for result in results):
            self.undo_file.write_text(
                json.dumps(
                    {
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                        "items": [
                            {"source": str(plan.source_path), "target": str(plan.target_path)} for plan in plans
                        ],
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
        entries = data.get("items", [])
        if not entries:
            return [RenameResult(Path(), Path(), False, "没有可撤销的记录")]

        plans = [RenamePlan(Path(entry["target"]), Path(entry["source"])) for entry in entries]
        results = self._run_transaction(plans, "已撤销")
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

    def _run_transaction(self, plans: list[RenamePlan], success_message: str) -> list[RenameResult]:
        self.last_recovery_file = None
        if not plans:
            return []

        validation_error = self._validate_plans(plans)
        if validation_error:
            return [RenameResult(plan.source_path, plan.target_path, False, validation_error) for plan in plans]

        transaction_id = uuid4().hex
        states = [
            _TransactionItem(
                plan=plan,
                temporary_path=self._unique_sidecar_path(plan.source_path.parent, "nfbatch", transaction_id, index),
                current_path=plan.source_path,
            )
            for index, plan in enumerate(plans)
        ]

        try:
            for state in states:
                self._move(state.current_path, state.temporary_path)
                state.current_path = state.temporary_path
                state.moved = True

            for state in states:
                self._move(state.current_path, state.plan.target_path)
                state.current_path = state.plan.target_path
        except OSError as exc:
            rollback_errors = self._rollback(states, transaction_id)
            if rollback_errors:
                self.last_recovery_file = self._write_recovery_manifest(states, transaction_id, str(exc), rollback_errors)
                message = f"批次失败且回滚不完整，请按恢复清单处理：{self.last_recovery_file}"
            else:
                message = f"批次失败，已恢复全部原文件：{exc}"
            return [RenameResult(plan.source_path, plan.target_path, False, message) for plan in plans]

        return [RenameResult(plan.source_path, plan.target_path, True, success_message) for plan in plans]

    def _validate_plans(self, plans: list[RenamePlan]) -> str | None:
        source_keys = [self._path_key(plan.source_path) for plan in plans]
        target_keys = [self._path_key(plan.target_path) for plan in plans]

        if len(source_keys) != len(set(source_keys)):
            return "批次内存在重复源文件"
        if len(target_keys) != len(set(target_keys)):
            return "批次内存在重复目标文件"

        source_key_set = set(source_keys)
        for plan in plans:
            if not plan.source_path.exists():
                return f"源文件不存在：{plan.source_path}"
            if not plan.source_path.is_file():
                return f"源路径不是文件：{plan.source_path}"
            if self._path_key(plan.source_path.parent) != self._path_key(plan.target_path.parent):
                return "事务改名只允许在原文件所在目录内执行"
            if not plan.target_path.parent.exists():
                return f"目标目录不存在：{plan.target_path.parent}"
            if plan.target_path.exists() and self._path_key(plan.target_path) not in source_key_set:
                return f"目标文件已存在：{plan.target_path}"
        return None

    def _rollback(self, states: list[_TransactionItem], transaction_id: str) -> list[str]:
        rollback_errors: list[str] = []
        moved_states = [state for state in states if state.moved and state.current_path != state.plan.source_path]
        recovery_paths: dict[int, Path] = {}

        for index, state in enumerate(moved_states):
            recovery_path = self._unique_sidecar_path(
                state.plan.source_path.parent,
                "nfrollback",
                transaction_id,
                index,
            )
            try:
                self._move(state.current_path, recovery_path)
                state.current_path = recovery_path
                recovery_paths[id(state)] = recovery_path
            except OSError as exc:
                rollback_errors.append(f"暂存回滚失败 {state.current_path}: {exc}")

        for state in reversed(moved_states):
            if id(state) not in recovery_paths:
                continue
            try:
                self._move(state.current_path, state.plan.source_path)
                state.current_path = state.plan.source_path
            except OSError as exc:
                rollback_errors.append(f"恢复原路径失败 {state.plan.source_path}: {exc}")

        return rollback_errors

    def _write_recovery_manifest(
        self,
        states: list[_TransactionItem],
        transaction_id: str,
        transaction_error: str,
        rollback_errors: list[str],
    ) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        recovery_file = self.logs_dir / f"recovery_{stamp}_{transaction_id[:8]}.json"
        recovery_file.write_text(
            json.dumps(
                {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "transaction_id": transaction_id,
                    "transaction_error": transaction_error,
                    "rollback_errors": rollback_errors,
                    "items": [
                        {
                            "source": str(state.plan.source_path),
                            "current": str(state.current_path),
                            "target": str(state.plan.target_path),
                            "restored": state.current_path == state.plan.source_path,
                        }
                        for state in states
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return recovery_file

    def _unique_sidecar_path(self, folder: Path, prefix: str, transaction_id: str, index: int) -> Path:
        candidate = folder / f".{prefix}-{transaction_id}-{index:06d}.tmp"
        suffix = 0
        while candidate.exists():
            suffix += 1
            candidate = folder / f".{prefix}-{transaction_id}-{index:06d}-{suffix}.tmp"
        return candidate

    def _move(self, source: Path, target: Path) -> None:
        self._rename_operation(source, target)

    @staticmethod
    def _rename(source: Path, target: Path) -> None:
        source.rename(target)

    @staticmethod
    def _path_key(path: Path) -> str:
        return str(path.absolute()).replace("/", "\\").casefold()

    def _write_run_log(self, results: list[RenameResult]) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
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
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
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
