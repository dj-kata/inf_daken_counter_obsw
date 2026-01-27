import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# ログ保存ディレクトリの作成
LOG_DIR = "log"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def get_logger():
    '''呼び出し元のファイル名を取得してログファイル名にする'''
    # 実行メインスクリプト名を取得
    main_file = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    log_file = os.path.join(LOG_DIR, f"{main_file}.log")

    logger = logging.getLogger("app_logger")
    logger.setLevel(logging.DEBUG)

    # 既にハンドラがある場合は追加しない（二重出力を防ぐ）
    if not logger.handlers:
        # ログフォーマットの設定
        # 時刻, レベル, ファイル名:行数, 関数名, メッセージ
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(filename)s:%(lineno)d:%(funcName)s - %(message)s'
        )

        # ファイル出力設定 (2MB制限, 3世代までバックアップ)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)

        # コンソール出力設定（デバッグ中に便利）
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger

# インスタンスを作成しておく
logger = get_logger()
