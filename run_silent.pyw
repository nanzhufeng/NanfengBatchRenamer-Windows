from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

ERROR_LOG = LOG_DIR / "app_error.txt"
RUN_LOG = LOG_DIR / "app_stdout.txt"

sys.path.insert(0, str(SRC))
os.chdir(ROOT)

# pythonw 没有命令行窗口，显式写日志，避免闪退时没有任何线索。
sys.stdout = RUN_LOG.open("a", encoding="utf-8", buffering=1)
sys.stderr = ERROR_LOG.open("a", encoding="utf-8", buffering=1)

try:
    from batch_renamer.app import run

    exit_code = run()
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
    raise SystemExit(1)
else:
    raise SystemExit(exit_code)
