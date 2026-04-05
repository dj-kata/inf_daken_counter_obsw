"""
設定ダイアログ
基本設定を行うためのダイアログウィンドウ
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLineEdit, QSpinBox, QCheckBox, QPushButton,
                               QGroupBox, QFileDialog, QTabWidget, QWidget,
                               QLabel, QDialogButtonBox, QRadioButton,
                               QButtonGroup, QScrollArea, QGridLayout, QProgressBar)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIntValidator
import os
import datetime

from src.config import Config
from src.classes import music_pack, config_autosave_image, config_modify_rivalarea
from src.logger import get_logger
from src.result import OneResult, PlayOption
from src.result_database import ResultDatabase
from src.screen_reader import ScreenReader
from src.funcs import *
logger = get_logger(__name__)

# UIの型チェック用
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.ui_jp import UIText

class ImageImportWorker(QThread):
    """画像読み込み処理を行うワーカースレッド"""
    # シグナル定義
    progress = Signal(int, int)  # (現在の処理数, 総数)
    finished = Signal(int, int)  # (登録数, 総数)
    error = Signal(str)
    
    def __init__(self, folder_path, screen_reader, result_database):
        super().__init__()
        self.folder_path = folder_path
        self.screen_reader = screen_reader
        self.result_database = result_database
        self._is_cancelled = False
    
    def cancel(self):
        """処理をキャンセル"""
        self._is_cancelled = True
    
    def run(self):
        """スレッドで実行される処理"""
        try:
            import glob
            from pathlib import Path
            
            # pngファイルを取得
            png_files = glob.glob(str(Path(self.folder_path) / "*.png"))
            
            registered_count = 0
            total_count = len(png_files)
            
            for i, png_file in enumerate(png_files):
                if self._is_cancelled:
                    break
                
                # 進捗通知
                self.progress.emit(i + 1, total_count)
                
                self.screen_reader.update_screen_from_file(png_file)
                if self.screen_reader.is_result():
                    r = self.screen_reader.read_result_screen()
                    if r:
                        # logger.info(f'[RESULT] {r}')
                        registered_count += 1
                        r.result.timestamp = os.path.getmtime(png_file)
            
            # 完了通知
            self.finished.emit(registered_count, total_count)
            
            self.result_database.save()
            self.result_database.results.sort()
                
        except Exception as e:
            self.error.emit(str(e))

class PklImportWorker(QThread):
    """pklファイル読み込み処理を行うワーカースレッド"""
    # シグナル定義
    progress = Signal(int, int)  # (現在の処理数, 総数)
    finished = Signal(int, int)  # (登録数, 総数)
    error = Signal(str)
    
    def __init__(self, pkl_path, result_database):
        super().__init__()
        self.pkl_path = pkl_path
        self.result_database = result_database
        self._is_cancelled = False
    
    def cancel(self):
        """処理をキャンセル"""
        self._is_cancelled = True
    
    def run(self):
        """スレッドで実行される処理"""
        try:
            import pickle
            
            with open(self.pkl_path, 'rb') as f:
                data = pickle.load(f)
            
            # v2はBPIの有無で2通り(長さ14,15)。option, 日付を-2,-1で取得すればよい。長さがこれ以外のものは落とす。
            registered_count = 0
            total_count = len(data)
            for i, item in enumerate(data):
                if self._is_cancelled:
                    break
                # 進捗通知
                self.progress.emit(i + 1, total_count)

                if len(item) not in (14, 15):
                    continue

                style = convert_play_style(item[2][:2]) # sp/dp
                if item[11]:
                    bp = item[11]
                else:
                    bp = 99999999
                timestamp = datetime.datetime(year=int(item[-1][0:4]),
                                              month=int(item[-1][5:7]),
                                              day=int(item[-1][8:10]),
                                              hour=int(item[-1][11:13]),
                                              minute=int(item[-1][14:16]),
                                              ).timestamp()
                option = PlayOption(None)
                option.convert_from_v2(item[-2])
                notes = item[3]
                mode = detect_mode.select # result / selectどっちにすべきか?
                try:
                    result = OneResult(title=item[1],
                                       play_style=style,
                                       difficulty=convert_difficulty(item[2][-1]),
                                       lamp=convert_lamp(item[7]),
                                       timestamp=int(timestamp),
                                       playspeed=None,
                                       option=option,
                                       detect_mode=mode,
                                       is_arcade = False,
                                       judge=None,
                                       score=item[9],
                                       bp=bp,
                                       notes=notes,
                    )
                    
                    # リザルト登録処理
                    if 'True Blue' == item[1]:
                        print(result)
                    if self.result_database.add(result):
                        registered_count += 1
                except:
                    continue
            # 完了通知
            self.finished.emit(registered_count, total_count)
            
            if registered_count > 0:
                self.result_database.save()
                
        except Exception as e:
            self.error.emit(str(e))

class ConfigDialog(QDialog):
    """設定ダイアログクラス"""
    
    def __init__(self, config: Config, result_database:ResultDatabase=None, screen_reader:ScreenReader=None, parent=None):
        super().__init__(parent)
        
        self.config = config
        self.ui:UIText = load_ui_text(config)
        self.result_database = result_database
        self.screen_reader = screen_reader
        
        # ダイアログ設定
        self.setWindowTitle(self.ui.window.settings_title)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        # UI初期化
        self.init_ui()
        
        # 現在の設定値を読み込み
        self.load_config_values()
    
    def init_ui(self):
        """UI初期化"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # タブウィジェット
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # 各タブを作成(OBS WebSocketタブを削除)
        tab_widget.addTab(self.create_feature_tab(), self.ui.tab.feature)
        # tab_widget.addTab(self.create_music_pack_tab(), self.ui.tab.music_pack)
        tab_widget.addTab(self.create_image_save_tab(), self.ui.tab.image_save)
        tab_widget.addTab(self.create_data_import_tab(), self.ui.tab.data_import)  # 追加
        tab_widget.addTab(self.create_rival_tab(), self.ui.tab.rival)

        # ボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def create_feature_tab(self):
        """機能設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # ツイート機能グループ
        tweet_group = QGroupBox(self.ui.feature.tweet_group)
        tweet_layout = QVBoxLayout()
        tweet_group.setLayout(tweet_layout)
        
        self.enable_autotweet_check = QCheckBox(self.ui.feature.enable_autotweet)
        tweet_layout.addWidget(self.enable_autotweet_check)
        
        self.enable_judge_check = QCheckBox(self.ui.feature.enable_judge)
        tweet_layout.addWidget(self.enable_judge_check)
        
        self.enable_folder_updates_check = QCheckBox(self.ui.feature.enable_folder_updates)
        tweet_layout.addWidget(self.enable_folder_updates_check)
        
        layout.addWidget(tweet_group)
        
        # その他の設定
        other_group = QGroupBox(self.ui.feature.other_group)
        other_layout = QFormLayout()
        other_group.setLayout(other_layout)
        
        # 画像保存先設定の追加
        self.image_save_path_edit = QLineEdit()
        self.browse_button = QPushButton(self.ui.dialog.browse)
        self.browse_button.clicked.connect(self.on_browse_clicked)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.image_save_path_edit)
        path_layout.addWidget(self.browse_button)
        
        other_layout.addRow(self.ui.feature.image_save_path, path_layout)
        
        self.autoload_offset_spin = QSpinBox()
        self.autoload_offset_spin.setRange(0, 100000)
        other_layout.addRow(self.ui.feature.autoload_offset, self.autoload_offset_spin)
        
        self.websocket_data_port = QLineEdit()
        validator = QIntValidator(1000,65535)
        self.websocket_data_port.setValidator(validator)
        other_layout.addRow(self.ui.feature.websocket_port, self.websocket_data_port)

        # 最前面表示 
        self.keep_on_top_check = QCheckBox(self.ui.feature.keep_on_top)
        other_layout.addRow(self.keep_on_top_check)

        layout.addWidget(other_group)
        layout.addStretch()
        
        return widget

    def on_browse_clicked(self):
        """フォルダ参照ボタン押下時の処理"""
        current_dir = self.image_save_path_edit.text()
        if not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~")
            
        dir_path = QFileDialog.getExistingDirectory(
            self, self.ui.dialog.select_image_path, current_dir
        )
        
        if dir_path:
            self.image_save_path_edit.setText(dir_path)
    
    def create_music_pack_tab(self):
        """楽曲パック設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 説明ラベル
        label = QLabel(self.ui.music_pack.description)
        layout.addWidget(label)
        
        # 全選択/全解除ボタン
        button_layout = QHBoxLayout()
        select_all_button = QPushButton(self.ui.music_pack.select_all)
        deselect_all_button = QPushButton(self.ui.music_pack.deselect_all)
        select_all_button.clicked.connect(self.on_select_all_music_packs)
        deselect_all_button.clicked.connect(self.on_deselect_all_music_packs)
        button_layout.addWidget(select_all_button)
        button_layout.addWidget(deselect_all_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # スクロール可能なチェックボックスエリア
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QGridLayout()
        scroll_widget.setLayout(scroll_layout)
        
        # music_packの各項目に対してチェックボックスを作成
        self.music_pack_checkboxes = {}
        row = 0
        col = 0
        max_cols = 3  # 3列表示
        
        for pack in music_pack:
            # unknownは除外
            if pack == music_pack.unknown:
                continue
            
            checkbox = QCheckBox(pack.name)
            self.music_pack_checkboxes[pack.name] = checkbox
            scroll_layout.addWidget(checkbox, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def on_select_all_music_packs(self):
        """全ての楽曲パックを選択"""
        for checkbox in self.music_pack_checkboxes.values():
            checkbox.setChecked(True)
    
    def on_deselect_all_music_packs(self):
        """全ての楽曲パックを解除"""
        for checkbox in self.music_pack_checkboxes.values():
            checkbox.setChecked(False)
    
    def create_image_save_tab(self):
        """画像保存設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 画像保存条件グループ
        save_condition_group = QGroupBox(self.ui.image_save.condition_group)
        save_condition_layout = QVBoxLayout()
        save_condition_group.setLayout(save_condition_layout)
        
        self.autosave_button_group = QButtonGroup()
        self.autosave_invalid_radio = QRadioButton(self.ui.image_save.never)
        self.autosave_all_radio = QRadioButton(self.ui.image_save.always)
        self.autosave_updates_radio = QRadioButton(self.ui.image_save.only_updates)
        
        self.autosave_button_group.addButton(self.autosave_invalid_radio, config_autosave_image.invalid.value)
        self.autosave_button_group.addButton(self.autosave_all_radio, config_autosave_image.all.value)
        self.autosave_button_group.addButton(self.autosave_updates_radio, config_autosave_image.only_updates.value)
        
        save_condition_layout.addWidget(self.autosave_invalid_radio)
        save_condition_layout.addWidget(self.autosave_all_radio)
        save_condition_layout.addWidget(self.autosave_updates_radio)
        
        layout.addWidget(save_condition_group)
        
        # ライバル欄編集グループ
        rival_edit_group = QGroupBox(self.ui.image_save.rivalarea_group)
        rival_edit_layout = QVBoxLayout()
        rival_edit_group.setLayout(rival_edit_layout)
        
        self.rivalarea_button_group = QButtonGroup()
        self.rivalarea_invalid_radio = QRadioButton(self.ui.image_save.rivalarea_invalid)
        self.rivalarea_mosaic_radio = QRadioButton(self.ui.image_save.rivalarea_mosaic)
        self.rivalarea_cut_radio = QRadioButton(self.ui.image_save.rivalarea_cut)
        
        self.rivalarea_button_group.addButton(self.rivalarea_invalid_radio, config_modify_rivalarea.invalid.value)
        self.rivalarea_button_group.addButton(self.rivalarea_mosaic_radio, config_modify_rivalarea.mosaic.value)
        self.rivalarea_button_group.addButton(self.rivalarea_cut_radio, config_modify_rivalarea.cut.value)
        
        rival_edit_layout.addWidget(self.rivalarea_invalid_radio)
        rival_edit_layout.addWidget(self.rivalarea_mosaic_radio)
        rival_edit_layout.addWidget(self.rivalarea_cut_radio)
        
        layout.addWidget(rival_edit_group)
        
        # その他の設定
        other_group = QGroupBox(self.ui.image_save.other_group)
        other_layout = QVBoxLayout()
        other_group.setLayout(other_layout)
        
        self.write_statistics_check = QCheckBox(self.ui.image_save.write_statistics)
        other_layout.addWidget(self.write_statistics_check)
        
        layout.addWidget(other_group)
        layout.addStretch()
        
        return widget

    def create_data_import_tab(self):
        """データ登録タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # 画像からの登録グループ
        import_group = QGroupBox(self.ui.data_import.from_images_group)
        import_layout = QVBoxLayout()
        import_group.setLayout(import_layout)

        # 説明ラベル
        desc_label = QLabel(self.ui.data_import.from_images_description)
        import_layout.addWidget(desc_label)

        # 登録ボタン
        self.import_button = QPushButton(self.ui.data_import.from_images_button)
        self.import_button.clicked.connect(self.on_import_from_images)
        import_layout.addWidget(self.import_button)

        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        import_layout.addWidget(self.import_progress)

        # キャンセルボタン追加
        self.import_cancel_button = QPushButton(self.ui.dialog.cancel)
        self.import_cancel_button.setVisible(False)
        self.import_cancel_button.clicked.connect(self.on_cancel_import)
        import_layout.addWidget(self.import_cancel_button)

        # 進捗表示用ラベル
        self.import_status_label = QLabel("")
        import_layout.addWidget(self.import_status_label)

        layout.addWidget(import_group)

        self.import_worker = None

        # v2プレーログからの登録グループ
        pkl_import_group = QGroupBox(self.ui.data_import.from_pkl_group)
        pkl_import_layout = QVBoxLayout()
        pkl_import_group.setLayout(pkl_import_layout)

        # 説明ラベル
        pkl_desc_label = QLabel(self.ui.data_import.from_pkl_description)
        pkl_import_layout.addWidget(pkl_desc_label)

        # 登録ボタン
        self.pkl_import_button = QPushButton(self.ui.data_import.from_pkl_button)
        self.pkl_import_button.clicked.connect(self.on_import_from_pkl)
        pkl_import_layout.addWidget(self.pkl_import_button)

        # プログレスバー
        self.pkl_import_progress = QProgressBar()
        self.pkl_import_progress.setVisible(False)
        pkl_import_layout.addWidget(self.pkl_import_progress)

        # キャンセルボタン
        self.pkl_import_cancel_button = QPushButton(self.ui.dialog.cancel)
        self.pkl_import_cancel_button.setVisible(False)
        self.pkl_import_cancel_button.clicked.connect(self.on_cancel_pkl_import)
        pkl_import_layout.addWidget(self.pkl_import_cancel_button)

        # 進捗表示用ラベル
        self.pkl_import_status_label = QLabel("")
        pkl_import_layout.addWidget(self.pkl_import_status_label)

        layout.addWidget(pkl_import_group)

        # ワーカースレッドの参照
        self.pkl_import_worker = None

        layout.addStretch()
        return widget

    def create_rival_tab(self):
        """ライバル設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # ライバル登録グループ
        rival_group = QGroupBox(self.ui.rival.rival_group)
        rival_layout = QVBoxLayout()
        rival_group.setLayout(rival_layout)

        desc_label = QLabel(self.ui.rival.rival_description)
        rival_layout.addWidget(desc_label)

        # ライバルリスト表示用テーブル
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self.rival_list_table = QTableWidget()
        self.rival_list_table.setColumnCount(2)
        self.rival_list_table.setHorizontalHeaderLabels(
            [self.ui.rival.name_label, self.ui.rival.url_label]
        )
        self.rival_list_table.horizontalHeader().setStretchLastSection(True)
        self.rival_list_table.setColumnWidth(0, 120)
        self.rival_list_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rival_list_table.setSelectionMode(QTableWidget.SingleSelection)
        self.rival_list_table.setEditTriggers(QTableWidget.NoEditTriggers)
        rival_layout.addWidget(self.rival_list_table)

        # 名前+URL入力行
        input_layout = QHBoxLayout()
        self.rival_name_edit = QLineEdit()
        self.rival_name_edit.setPlaceholderText(self.ui.rival.name_label)
        self.rival_name_edit.setMaximumWidth(120)
        input_layout.addWidget(self.rival_name_edit)

        self.rival_url_edit = QLineEdit()
        self.rival_url_edit.setPlaceholderText(self.ui.rival.url_label)
        input_layout.addWidget(self.rival_url_edit)

        add_button = QPushButton(self.ui.rival.add_button)
        add_button.clicked.connect(self.on_add_rival)
        input_layout.addWidget(add_button)

        remove_button = QPushButton(self.ui.rival.remove_button)
        remove_button.clicked.connect(self.on_remove_rival)
        input_layout.addWidget(remove_button)

        rival_layout.addLayout(input_layout)
        layout.addWidget(rival_group)

        # CSV出力先グループ
        csv_group = QGroupBox(self.ui.rival.csv_export_group)
        csv_layout = QVBoxLayout()
        csv_group.setLayout(csv_layout)

        csv_desc_label = QLabel(self.ui.rival.csv_export_description)
        csv_layout.addWidget(csv_desc_label)

        csv_path_layout = QHBoxLayout()
        self.csv_export_path_edit = QLineEdit()
        csv_path_layout.addWidget(self.csv_export_path_edit)

        csv_browse_button = QPushButton(self.ui.dialog.browse)
        csv_browse_button.clicked.connect(self.on_csv_browse_clicked)
        csv_path_layout.addWidget(csv_browse_button)

        csv_layout.addLayout(csv_path_layout)
        layout.addWidget(csv_group)

        layout.addStretch()
        return widget

    def on_add_rival(self):
        """ライバルをリストに追加"""
        name = self.rival_name_edit.text().strip()
        url = self.rival_url_edit.text().strip()
        if not name or not url:
            return
        from PySide6.QtWidgets import QTableWidgetItem
        row = self.rival_list_table.rowCount()
        self.rival_list_table.insertRow(row)
        self.rival_list_table.setItem(row, 0, QTableWidgetItem(name))
        self.rival_list_table.setItem(row, 1, QTableWidgetItem(url))
        self.rival_name_edit.clear()
        self.rival_url_edit.clear()

    def on_remove_rival(self):
        """選択中のライバルをリストから削除"""
        selected = self.rival_list_table.selectedItems()
        if selected:
            self.rival_list_table.removeRow(selected[0].row())

    def on_csv_browse_clicked(self):
        """CSV出力先フォルダ参照"""
        current_dir = self.csv_export_path_edit.text()
        if not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~")
        dir_path = QFileDialog.getExistingDirectory(
            self, self.ui.rival.select_csv_export_path, current_dir
        )
        if dir_path:
            self.csv_export_path_edit.setText(dir_path)

    def on_import_from_images(self):
        """画像からリザルトを登録"""
        if not self.result_database or not self.screen_reader:
            self.import_status_label.setText("エラー: 登録機能が利用できません")
            return

        # フォルダ選択
        folder_path = QFileDialog.getExistingDirectory(
            self, self.ui.data_import.from_images_dialog_description
        )

        if not folder_path:
            return
        
        # UIの状態変更
        self.import_button.setEnabled(False)
        self.import_progress.setVisible(True)
        self.import_cancel_button.setVisible(True)
        self.import_status_label.setText(self.ui.status.loading)
    
        # ワーカースレッドの作成と開始
        self.import_worker = ImageImportWorker(
            folder_path, self.screen_reader, self.result_database
        )
        self.import_worker.progress.connect(self.on_import_progress)
        self.import_worker.finished.connect(self.on_import_finished)
        self.import_worker.error.connect(self.on_import_error)
        self.import_worker.start()

    def on_cancel_import(self):
        """インポート処理をキャンセル"""
        if self.import_worker and self.import_worker.isRunning():
            self.import_worker.cancel()
            self.import_status_label.setText(self.ui.status.canceling)
            self.import_cancel_button.setEnabled(False)

    def on_import_progress(self, current, total):
        """進捗更新"""
        self.import_progress.setMaximum(total)
        self.import_progress.setValue(current)
        self.import_status_label.setText(f"{self.ui.status.processing} {current}/{total}")

    def on_import_finished(self, registered_count, total_count):
        """処理完了"""
        self.import_progress.setVisible(False)
        self.import_cancel_button.setVisible(False)
        self.import_button.setEnabled(True)
        self.import_status_label.setText(self.ui.data_import.completed_format.format(total=total_count, registered=registered_count))
        logger.info(f"画像インポート完了: {registered_count}/{total_count}")

    def on_import_error(self, error_message):
        """エラー発生"""
        self.import_progress.setVisible(False)
        self.import_cancel_button.setVisible(False)
        self.import_button.setEnabled(True)
        self.import_status_label.setText(f"{self.ui.message.error_title}: {error_message}")
        logger.error(f"画像読み込みエラー: {error_message}")

    def on_import_from_pkl(self):
        """pklファイルからリザルトを登録"""
        if not self.result_database:
            self.pkl_import_status_label.setText("エラー: 登録機能が利用できません")
            return

        # ファイル選択
        pkl_path, _ = QFileDialog.getOpenFileName(
            self, self.ui.data_import.from_pkl_dialog_description, "", "Pickle Files (alllog.pkl);;All Files (*)"
        )

        if not pkl_path:
            return

        # ファイルの存在確認
        if not os.path.exists(pkl_path):
            self.pkl_import_status_label.setText("エラー: ファイルが存在しません")
            return

        # UIの状態変更
        self.pkl_import_button.setEnabled(False)
        self.pkl_import_progress.setVisible(True)
        self.pkl_import_cancel_button.setVisible(True)
        self.pkl_import_status_label.setText(self.ui.status.loading)

        # ワーカースレッドの作成と開始
        self.pkl_import_worker = PklImportWorker(pkl_path, self.result_database)
        self.pkl_import_worker.progress.connect(self.on_pkl_import_progress)
        self.pkl_import_worker.finished.connect(self.on_pkl_import_finished)
        self.pkl_import_worker.error.connect(self.on_pkl_import_error)
        self.pkl_import_worker.start()

    def on_cancel_pkl_import(self):
        """pklインポート処理をキャンセル"""
        if self.pkl_import_worker and self.pkl_import_worker.isRunning():
            self.pkl_import_worker.cancel()
            self.pkl_import_status_label.setText(self.ui.status.canceling)
            self.pkl_import_cancel_button.setEnabled(False)

    def on_pkl_import_progress(self, current, total):
        """pkl進捗更新"""
        self.pkl_import_progress.setMaximum(total)
        self.pkl_import_progress.setValue(current)
        self.pkl_import_status_label.setText(f"{self.ui.status.processing} {current}/{total}")

    def on_pkl_import_finished(self, registered_count, total_count):
        """pkl処理完了"""
        self.pkl_import_progress.setVisible(False)
        self.pkl_import_cancel_button.setVisible(False)
        self.pkl_import_button.setEnabled(True)
        self.pkl_import_status_label.setText(self.ui.data_import.completed_format.format(total=total_count, registered=registered_count))
        logger.info(f"pklインポート完了: {registered_count}/{total_count}")

    def on_pkl_import_error(self, error_message):
        """pklエラー発生"""
        self.pkl_import_progress.setVisible(False)
        self.pkl_import_cancel_button.setVisible(False)
        self.pkl_import_button.setEnabled(True)
        self.pkl_import_status_label.setText(f"{self.ui.message.error_title}: {error_message}")
        logger.error(f"pkl読み込みエラー: {error_message}")

    def load_config_values(self):
        """設定値を読み込んでUIに反映"""
        # 機能設定
        self.keep_on_top_check.setChecked(self.config.keep_on_top)
        self.enable_autotweet_check.setChecked(self.config.enable_autotweet)
        self.enable_judge_check.setChecked(self.config.enable_judge)
        self.enable_folder_updates_check.setChecked(self.config.enable_folder_updates)
        self.autoload_offset_spin.setValue(self.config.autoload_offset)
        if hasattr(self, 'websocket_data_port') and hasattr(self.config, 'websocket_data_port'):
            self.websocket_data_port.setText(str(self.config.websocket_data_port))
        
        # 画像保存先 (Configクラスに image_save_path プロパティがある前提)
        if hasattr(self.config, 'image_save_path'):
            self.image_save_path_edit.setText(self.config.image_save_path)
        
        # # 楽曲パック設定
        # if hasattr(self.config, 'target_music_packs'):
        #     for pack_name in self.config.target_music_packs:
        #         if pack_name in self.music_pack_checkboxes:
        #             self.music_pack_checkboxes[pack_name].setChecked(True)
        
        # 画像保存設定
        if hasattr(self.config, 'autosave_image_mode'):
            button = self.autosave_button_group.button(self.config.autosave_image_mode.value)
            if button:
                button.setChecked(True)
        
        if hasattr(self.config, 'modify_rivalarea_mode'):
            button = self.rivalarea_button_group.button(self.config.modify_rivalarea_mode.value)
            if button:
                button.setChecked(True)

        if hasattr(self.config, 'write_statistics'):
            self.write_statistics_check.setChecked(self.config.write_statistics)

        # ライバル設定
        if hasattr(self, 'rival_list_table'):
            from PySide6.QtWidgets import QTableWidgetItem
            self.rival_list_table.setRowCount(0)
            for rival in self.config.rivals:
                row = self.rival_list_table.rowCount()
                self.rival_list_table.insertRow(row)
                self.rival_list_table.setItem(row, 0, QTableWidgetItem(rival.get('name', '')))
                self.rival_list_table.setItem(row, 1, QTableWidgetItem(rival.get('url', '')))

        # CSV出力先
        if hasattr(self, 'csv_export_path_edit'):
            self.csv_export_path_edit.setText(self.config.csv_export_path)

    def accept(self):
        """OKボタン押下時の処理"""
        # UIから設定値を取得してConfigに保存
        
        # 機能設定
        self.config.keep_on_top = self.keep_on_top_check.isChecked()
        self.config.enable_autotweet = self.enable_autotweet_check.isChecked()
        self.config.enable_judge = self.enable_judge_check.isChecked()
        self.config.enable_folder_updates = self.enable_folder_updates_check.isChecked()
        self.config.autoload_offset = self.autoload_offset_spin.value()
        # WebSocketデータポート設定
        try:
            port = int(self.websocket_data_port.text())
            if 1000 <= port <= 65535:
                self.config.websocket_data_port = port
            else:
                logger.warning(f"無効なポート番号: {port}. デフォルト値を使用します")
        except ValueError:
            logger.warning("ポート番号の変換に失敗しました。デフォルト値を使用します")
        
        # 画像保存先
        self.config.image_save_path = self.image_save_path_edit.text()
        
        # # 楽曲パック設定
        # self.config.target_music_packs = [
        #     pack_name for pack_name, checkbox in self.music_pack_checkboxes.items()
        #     if checkbox.isChecked()
        # ]
        
        # 画像保存設定
        self.config.autosave_image_mode = config_autosave_image(self.autosave_button_group.checkedId())
        self.config.modify_rivalarea_mode = config_modify_rivalarea(self.rivalarea_button_group.checkedId())
        self.config.write_statistics = self.write_statistics_check.isChecked()
        
        # ライバル設定
        if hasattr(self, 'rival_list_table'):
            rivals = []
            for row in range(self.rival_list_table.rowCount()):
                name_item = self.rival_list_table.item(row, 0)
                url_item = self.rival_list_table.item(row, 1)
                if name_item and url_item:
                    rivals.append({
                        'name': name_item.text(),
                        'url': url_item.text()
                    })
            self.config.rivals = rivals

        # CSV出力先
        if hasattr(self, 'csv_export_path_edit'):
            self.config.csv_export_path = self.csv_export_path_edit.text()

        # 設定を保存
        self.config.save_config()
        
        logger.info("設定を保存しました")
        
        # ダイアログを閉じる
        super().accept()
