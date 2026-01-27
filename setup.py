"""
IIDX Helper - cx_Freeze ビルド設定（PySide6対応版）
"""

import sys
from cx_Freeze import setup, Executable
import os
from pathlib import Path

# PySide6のパスを取得
try:
    import PySide6
    pyside6_path = Path(PySide6.__file__).parent
    
    # PySide6のプラグインディレクトリを含める
    include_files = []
    
    # プラグインディレクトリ（platforms, stylesなど）
    plugins_dir = pyside6_path / "plugins"
    if plugins_dir.exists():
        include_files.append((str(plugins_dir), "lib/PySide6/plugins"))
    
    # Qt翻訳ファイル
    translations_dir = pyside6_path / "translations"
    if translations_dir.exists():
        include_files.append((str(translations_dir), "lib/PySide6/translations"))
    
    # Qt.conf（プラグインパスを指定）
    qt_conf_content = """[Paths]
Prefix = .
Binaries = .
Plugins = lib/PySide6/plugins
"""
    # Qt.confを一時的に作成
    with open("qt.conf", "w") as f:
        f.write(qt_conf_content)
    include_files.append(("qt.conf", "qt.conf"))

except ImportError:
    include_files = []
    print("Warning: PySide6 not found. Build may not work correctly.")

# infnotebook関連のファイルがあれば含める
if os.path.exists("infnotebook"):
    include_files.append(("infnotebook/", "infnotebook/"))

# データファイルがあれば含める
if os.path.exists("recognition_images"):
    include_files.append(("recognition_images/", "recognition_images/"))

# ビルドオプション
build_exe_options = {
    # 含めるパッケージ
    "packages": [
        "PySide6.QtCore",
        "PySide6.QtGui", 
        "PySide6.QtWidgets",
        "obsws_python",
        "PIL",
        "numpy",
        "imagehash",
        "pickle",
        "bz2",
        "json",
        "traceback",
        "logging",
        "logging.handlers",
        "hashlib",
        "math",
        "datetime",
        "time",
        "threading",
        "os",
        "sys",
        "enum",
        "typing",
    ],
    
    # 含めるモジュール
    "includes": [
        "src",
        "src.config",
        "src.classes",
        "src.funcs",
        "src.logger",
        "src.obs_control",
        "src.result",
        "src.screen_reader",
        "src.songinfo",
        "src.config_dialog",
        "src.obs_dialog",
    ],
    
    # 除外するパッケージ（サイズ削減のため）
    "excludes": [
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "test",
        "unittest",
        "email",
        "html",
        "http",
        "xml",
        "pydoc",
        "distutils",
        "setuptools",
        "pip",
        # PySide6の不要なモジュール
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
    ],
    
    # 含めるファイル
    "include_files": include_files,
    
    # MSVCランタイムを含める
    "include_msvcr": True,
    
    # zip圧縮の設定
    "zip_include_packages": ["*"],
    "zip_exclude_packages": ["PySide6"],
    
    # 最適化レベル（2が最大）
    "optimize": 2,
    
    # ビルドディレクトリ名
    "build_exe": "inf_daken_counter",
}

# ベースの設定
base = None
if sys.platform == "win32":
    # Windowsの場合、コンソールを非表示にする
    base = "Win32GUI"
elif sys.platform == "darwin":
    # macOSの場合
    base = None

# 実行ファイルの設定
executables = [
    Executable(
        script="notes_counter.pyw",
        base=base,
        target_name="notes_counter.exe" if sys.platform == "win32" else "notes_counter",
        icon=None,  # アイコンファイルがあれば指定: "resources/icon.ico"
        shortcut_name="IIDX Helper",
        shortcut_dir="DesktopFolder",
    )
]

# セットアップ
setup(
    name="IIDXHelper",
    version="3.0.0",
    description="INF打鍵カウンタ",
    author="dj-kata",
    url="",
    license="",
    options={
        "build_exe": build_exe_options,
    },
    executables=executables,
)