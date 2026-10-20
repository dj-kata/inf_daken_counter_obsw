"""説明書用の画像保存タブを撮影する。アプリ本体は起動しない。"""

import argparse
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def capture_image_save(output_dir, language="ja"):
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from src.config import Config
    from src.image_save_settings import ImageSaveSettings

    if language == "en":
        from src.ui_en import UIText
    else:
        from src.ui_jp import UIText

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setPalette(app.style().standardPalette())
    families = QFontDatabase.families()
    for family in ("Noto Sans CJK JP", "Yu Gothic", "Meiryo"):
        if family in families:
            app.setFont(QFont(family, 10))
            break

    # Configは構築時に読み込みと保存を行うため、一時ファイルを指定する。
    # 利用者のconfig.json、プレー履歴、OBS接続は使用しない。
    with tempfile.TemporaryDirectory(prefix="infdc-manual-") as temp_dir:
        config = Config(str(Path(temp_dir) / "config.json"))
        widget = ImageSaveSettings(UIText)
        widget.load_config_values(config)
        widget.setWindowTitle(UIText.tab.image_save)
        widget.resize(max(640, widget.sizeHint().width()),
                      max(480, widget.sizeHint().height()))
        widget.show()
        app.processEvents()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"image-save-{language}.png"
        try:
            if not widget.grab().save(str(output)):
                raise RuntimeError(f"画像を保存できませんでした: {output}")
        finally:
            widget.close()
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("ja", "en"), default="ja")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "images")
    parser.add_argument("--offscreen", action="store_true",
                        help="画面を表示せず撮影する（Linux等での検証用）")
    args = parser.parse_args()
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    print(capture_image_save(args.output_dir, args.language))


if __name__ == "__main__":
    main()
