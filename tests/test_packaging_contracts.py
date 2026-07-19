from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INNO_SCRIPT = PROJECT_ROOT / "installer" / "NanfengBatchRenamer-Windows.iss"


class PackagingContractTests(unittest.TestCase):
    def test_shortcuts_use_versioned_icon_path_to_avoid_explorer_cache(self) -> None:
        script = INNO_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            '#define MyShortcutIconName "app_icon-v" + MyAppVersion + ".ico"',
            script,
        )
        self.assertIn('DestName: "{#MyShortcutIconName}"', script)
        self.assertEqual(script.count('IconFilename: "{app}\\{#MyShortcutIconName}"'), 2)
        self.assertIn('UninstallDisplayIcon={app}\\{#MyShortcutIconName}', script)


if __name__ == "__main__":
    unittest.main()
