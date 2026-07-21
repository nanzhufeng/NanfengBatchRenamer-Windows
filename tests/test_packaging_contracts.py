from __future__ import annotations

import unittest
from pathlib import Path

from PySide6.QtGui import QImageReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INNO_SCRIPT = PROJECT_ROOT / "installer" / "NanfengBatchRenamer-Windows.iss"
README = PROJECT_ROOT / "README.md"
PREVIEW_IMAGE = PROJECT_ROOT / "docs" / "images" / "app-preview.png"


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

    def test_github_preview_is_present_and_referenced(self) -> None:
        self.assertTrue(PREVIEW_IMAGE.is_file())
        self.assertIn("docs/images/app-preview.png", README.read_text(encoding="utf-8"))
        size = QImageReader(str(PREVIEW_IMAGE)).size()
        self.assertTrue(size.isValid())
        self.assertEqual(size.width(), 1920)
        self.assertLessEqual(size.height(), 1080)


if __name__ == "__main__":
    unittest.main()
