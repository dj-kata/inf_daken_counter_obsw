"""Resolve Qt WebEngine's runtime files in a Windows cx_Freeze bundle."""

import os
from pathlib import Path


def validate_webengine_version(version):
    if not isinstance(version, str):
        version = bytes(version).decode('ascii')
    # Qt 6.10.1's ContentClientQt::SetGpuInfo dereferences a GPU-thread object
    # from the browser thread (QTBUG-142497 / QTBUG-142720). It can terminate
    # the entire counter during the first page load; a Python try/except cannot
    # catch this. Qt 6.10.2 moves this work to the GPU thread.
    if tuple(int(part) for part in version.split('.')[:3]) < (6, 10, 2):
        raise RuntimeError(
            f'Qt {version} is not supported for the game log overlay. '
            'Update PySide6 to 6.10.2 or later and rebuild the application '
            '(QTBUG-142497 / QTBUG-142720).'
        )


def configure_frozen_webengine(bundle_dir):
    qt_dir = Path(bundle_dir).resolve() / 'lib' / 'PySide6'
    resources = qt_dir / 'resources'
    locales = qt_dir / 'translations' / 'qtwebengine_locales'
    process = qt_dir / 'QtWebEngineProcess.exe'
    required = [process, locales / 'en-US.pak'] + [
        resources / filename for filename in (
            'icudtl.dat', 'qtwebengine_resources.pak',
            'qtwebengine_resources_100p.pak', 'qtwebengine_resources_200p.pak',
            'v8_context_snapshot.bin',
        )
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        # Qt aborts the whole process for some missing files. Check before its
        # first WebEngine page is constructed so the caller can disable the log.
        raise FileNotFoundError('Missing Qt WebEngine runtime files: ' + ', '.join(missing))
    paths = {
        'QTWEBENGINEPROCESS_PATH': str(process),
        'QTWEBENGINE_RESOURCES_PATH': str(resources),
        'QTWEBENGINE_LOCALES_PATH': str(locales),
    }
    os.environ.update(paths)
    return paths
