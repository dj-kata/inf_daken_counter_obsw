#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import requests
import shutil
import subprocess
import threading
import time
from pathlib import Path
from packaging import version
import tkinter as tk
from tkinter import ttk, messagebox

import traceback
from bs4 import BeautifulSoup
from src.logger import get_logger
logger = get_logger(__name__)

class GitHubUpdater:
    def __init__(self, github_author='', github_repo='', zipfile_basename='', current_version='', main_exe_name=None, updator_exe_name=None):
        """
        GitHub自動アップデータの初期化
        
        Args:
            github_repo (str): GitHubリポジトリ（例: "username/repository"）
            current_version (str): 現在のバージョン（例: "1.0.0"）
            main_exe_name (str): メインプログラムのexe名（例: "main.exe"）
            updator_exe_name (str): アップデート用プログラムのexe名 (例: "update.exe"）
        """
        self.github_author = github_author
        self.github_repo = github_repo
        self.zipfile_basename = zipfile_basename
        self.current_version = current_version
        self.main_exe_name = main_exe_name or "main.exe"
        self.updator_exe_name = updator_exe_name or "update.exe"
        self.base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path.cwd()
        self.temp_dir = self.base_dir / "tmp"
        self.backup_dir = self.base_dir / "backup"
        logger.debug(f"base_dir:{self.base_dir}")
        
        # GUI関連
        self.root = None
        self.progress_var = None
        self.status_var = None
        self.progress_bar = None
        self.update_pending = False

    def ico_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def get_latest_version(self):
        # self.ico=self.ico_path('icon.ico')
        ret = None
        url = f'https://github.com/{self.github_author}/{self.github_repo}/tags'
        r = requests.get(url)
        soup = BeautifulSoup(r.text,features="html.parser")
        for tag in soup.find_all('a'):
            if 'releases/tag/' in tag['href']:
                logger.debug(f"tag = {tag}")
                ret = tag['href'].split('/')[-1]
                break # 1番上が最新なので即break
        return ret

    def check_for_updates(self):
        """
        GitHubで最新版をチェック
        
        Returns:
            tuple: (is_update_available, latest_version, download_url)
        """
        logger.debug(f"github_repo:{self.github_author}/{self.github_repo}")
        try:
            latest_version = self.get_latest_version()
            download_url = f"https://github.com/{self.github_author}/{self.github_repo}/releases/download/{latest_version}/{self.zipfile_basename}.zip"
            logger.debug(f"latest_version:{latest_version}, current:{self.current_version}")
            
            # バージョン比較
            if version.parse(latest_version.split('v.')[-1]) > version.parse(self.current_version.split('v.')[-1]):
                return True, latest_version, download_url
            else:
                return False, latest_version, None
                
        except Exception as e:
            print(f"アップデートチェックエラー: {e}")
            return False, None, None
    
    def create_gui(self):
        """アップデート用GUIの作成"""
        self.root = tk.Tk()
        # self.icon = tk.PhotoImage(data=icon.icon_data)
        # self.root.iconphoto(False, self.icon)
        self.root.title("プログラム更新中...")
        self.root.geometry("500x200")
        self.root.resizable(False, False)
        
        # 中央に配置
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() / 2 - 250),
            (self.root.winfo_screenheight() / 2 - 100)
        ))
        
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # タイトル
        title_label = ttk.Label(main_frame, text="プログラムを最新版に更新しています...", 
                               font=("Arial", 12, "bold"))
        title_label.pack(pady=(0, 20))
        
        # ステータステキスト
        self.status_var = tk.StringVar(value="更新確認中...")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.pack(pady=(0, 10))
        
        # プログレスバー
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, 
                                          maximum=100, length=400)
        self.progress_bar.pack(pady=(0, 20))
        
        # キャンセルボタン
        cancel_button = ttk.Button(main_frame, text="キャンセル", 
                                 command=self.cancel_update)
        cancel_button.pack()
        
        self.root.protocol("WM_DELETE_WINDOW", self.cancel_update)
        
    def update_status(self, message, progress=None):
        """ステータス更新"""
        if self.status_var:
            self.status_var.set(message)
        if progress is not None and self.progress_var:
            self.progress_var.set(progress)
        if self.root:
            self.root.update()
    
    def download_file(self, url, filepath):
        """
        ファイルをダウンロード（進行状況表示付き）
        
        Args:
            url (str): ダウンロードURL
            filepath (Path): 保存先パス
        """
        self.update_status("最新版をダウンロード中...", 0)
        
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded_size = 0
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 50  # 50%まで
                        self.update_status(f"ダウンロード中... {downloaded_size // 1024}KB / {total_size // 1024}KB", 
                                         progress)
    
    def create_backup(self):
        """現在のファイルをバックアップ"""
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        
        self.backup_dir.mkdir()
        
        # 重要なファイルをバックアップ
        for item in self.base_dir.iterdir():
            if item.name not in ['temp_update', 'backup'] and item.is_file():
                shutil.copy2(item, self.backup_dir)

    def create_restart_script(self):
        """終了後に全ファイルを更新する。失敗時は再起動せず展開元を残す。"""
        if not sys.platform.startswith('win'):
            raise RuntimeError('自動更新はWindowsでのみ利用できます')
        source = self.temp_dir / self.zipfile_basename
        for required in (self.main_exe_name, 'version.txt', 'lib'):
            if not (source / required).exists():
                raise RuntimeError(f'更新用ZIPに必要なファイルがありません: {required}')

        def batch_value(value):
            value = str(value)
            if any(char in value for char in ('"', '\r', '\n')):
                raise ValueError('更新先のパスに使用できない文字があります')
            return value.replace('%', '%%')

        script_path = self.base_dir / "restart_update.bat"
        script_content = f"""@echo off
chcp 65001 >nul
setlocal DisableDelayedExpansion
set "UPDATE_SOURCE={batch_value(source)}"
set "UPDATE_DEST={batch_value(self.base_dir)}"
set "UPDATE_EXE={batch_value(self.main_exe_name)}"
set "UPDATE_LOG=%UPDATE_DEST%\\update_install.log"
set /a WAIT_COUNT=0
:wait_exit
tasklist /FI "PID eq {os.getpid()}" /NH | findstr /R /C:" {os.getpid()} " >nul
if errorlevel 1 goto install
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 60 goto wait_failed
ping -n 2 127.0.0.1 >nul
goto wait_exit

:install
robocopy "%UPDATE_SOURCE%" "%UPDATE_DEST%" /E /COPY:DAT /IS /IT /R:5 /W:2 /XF version.txt /LOG:"%UPDATE_LOG%"
if errorlevel 8 goto failed
copy /Y "%UPDATE_SOURCE%\\version.txt" "%UPDATE_DEST%\\version.txt" >>"%UPDATE_LOG%" 2>&1
if errorlevel 1 goto failed
start "" /D "%UPDATE_DEST%" "%UPDATE_DEST%\\%UPDATE_EXE%"
if errorlevel 1 goto failed
endlocal
del "%~f0"
exit /b 0

:wait_failed
echo アプリの終了待ちがタイムアウトしました。>"%UPDATE_LOG%"
:failed
echo 更新に失敗しました。アプリは再起動しません。
echo "%UPDATE_LOG%" を確認してください。
echo アプリをすべて終了して、最新版ZIPを手動で展開してください。
pause
exit /b 1
"""
        with open(script_path, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(script_content)
        logger.info(f"path:{script_path}")
        return script_path
    
    def cleanup(self):
        """一時ファイルの清掃"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"清掃エラー: {e}")
    
    def cancel_update(self):
        """アップデートキャンセル"""
        self.cleanup()
        if self.root:
            self.root.destroy()
        sys.exit(0)
    
    def extract_zip_file(self, zip_path):
        """zipファイルを解凍する。tmp直下にそのまま解凍する。

        Args:
            zip_path (str): path of zipfile
        """
        shutil.unpack_archive(zip_path, self.temp_dir)

    def check_and_update(self):
        """
        メインプログラムから呼び出す関数
        アップデートが必要な場合のみGUIを表示して更新実行
        
        Returns:
            bool: アップデートが実行された場合True
        """
        logger.info('check and update')
        try:
            # アップデート確認（GUIなし）
            is_update_available, latest_version, download_url = self.check_for_updates()
            logger.info(f"available:{is_update_available}, latest:{latest_version}, url:{download_url}")
            
            if is_update_available:
                self.create_gui()
                # 確認ダイアログ
                result = messagebox.askyesno(
                    "アップデート確認",
                    f"新しいバージョン（{latest_version}）が利用可能です。\n"
                    f"現在のバージョン: {self.current_version}\n\n"
                    "今すぐ更新しますか？"
                )
                
                if result:
                    self.cleanup()
                    
                    # 別スレッドで更新実行
                    def update_thread():
                        try:
                            # ダウンロード
                            zip_path = self.temp_dir / f"update_{latest_version}.zip"
                            logger.info(f'zip_path: {zip_path}')
                            self.temp_dir.mkdir(exist_ok=True)
                            
                            logger.info('download')
                            self.download_file(download_url, zip_path)
                            self.extract_zip_file(zip_path)
                            self.create_restart_script()
                            self.update_status("更新準備完了。アプリを終了して更新します...", 100)
                            self.restart_program()
                            
                        except Exception as e:
                            logger.error(traceback.format_exc())
                            error_msg = f"更新エラー: {e}"
                            self.root.after(0, lambda msg=error_msg: messagebox.showerror("エラー", msg))
                            self.root.after(0, self.cancel_update)
                    
                    thread = threading.Thread(target=update_thread, daemon=True)
                    thread.start()
                    
                    self.root.mainloop()
                    return self.update_pending
                else:
                    # 更新しない場合はGUIを閉じる
                    if self.root:
                        self.root.destroy()
                        self.root = None
                    return False
            else:
                logger.info('no update')
            return False
            
        except Exception as e:
            logger.debug(traceback.format_exc())
            print(f"アップデート確認エラー: {e}")
            return False
    
    def restart_program(self):
        """更新を外部プロセスに引き継ぎ、メインスレッドに終了を依頼する。"""
        script_path = self.base_dir / "restart_update.bat"
        if not script_path.is_file():
            raise RuntimeError('更新用スクリプトが見つかりません')
        subprocess.Popen(
            ["cmd.exe", "/d", "/c", str(script_path)],
            cwd=self.base_dir,
            close_fds=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        self.update_pending = True
        # sys.exit() in the download worker only exits that thread, leaving DLLs loaded.
        self.root.after(0, self.root.destroy)


def main():
    try:
        with open('version.txt', 'r') as f:
            tmp = f.readline()
            print(tmp)
            SWVER = tmp.strip()[2:] if tmp.startswith('v') else tmp.strip()
    except Exception:
        logger.debug(traceback.format_exc())
        SWVER = "0.0.0"
    #SWVER='1.0.0' # for test

    updater = GitHubUpdater(
        github_author='dj-kata',
        github_repo='inf_daken_counter_obsw',
        zipfile_basename='inf_daken_counter',
        current_version=SWVER,           # 現在のバージョン
        main_exe_name="notes_counter.exe",  # メインプログラムのexe名
        updator_exe_name="notes_counter.exe",           # アップデート用プログラムのexe名
    )
    
    # メインプログラムから呼び出す場合
    updater.check_and_update()


if __name__ == "__main__":
    main()
