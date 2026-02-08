"""
設定ダイアログ
基本設定を行うためのダイアログウィンドウ
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLineEdit, QSpinBox, QCheckBox, QPushButton,
                               QGroupBox, QFileDialog, QTabWidget, QWidget,
                               QListWidget, QLabel, QDialogButtonBox, QRadioButton,
                               QButtonGroup, QScrollArea, QGridLayout)
from PySide6.QtCore import Qt
import os

from src.config import Config
from src.classes import music_pack, config_autosave_image, config_modify_rivalarea
from src.logger import get_logger
from src.result import ResultDatabase
from src.screen_reader import ScreenReader
logger = get_logger(__name__)

class ConfigDialog(QDialog):
    """設定ダイアログクラス"""
    
    def __init__(self, config: Config, result_database:ResultDatabase=None, screen_reader:ScreenReader=None, parent=None):
        super().__init__(parent)
        
        self.config = config
        self.result_database = result_database
        self.screen_reader = screen_reader
        
        # ダイアログ設定
        self.setWindowTitle("基本設定")
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
        tab_widget.addTab(self.create_feature_tab(), "機能設定")
        tab_widget.addTab(self.create_music_pack_tab(), "楽曲パック")
        tab_widget.addTab(self.create_image_save_tab(), "画像保存")
        tab_widget.addTab(self.create_data_import_tab(), "データ登録")  # 追加
        
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
        tweet_group = QGroupBox("ツイート機能")
        tweet_layout = QVBoxLayout()
        tweet_group.setLayout(tweet_layout)
        
        self.enable_autotweet_check = QCheckBox("終了時の自動ツイートを有効にする")
        tweet_layout.addWidget(self.enable_autotweet_check)
        
        self.enable_judge_check = QCheckBox("判定部分を含める")
        tweet_layout.addWidget(self.enable_judge_check)
        
        self.enable_folder_updates_check = QCheckBox("フォルダごとの更新数を表示")
        tweet_layout.addWidget(self.enable_folder_updates_check)
        
        layout.addWidget(tweet_group)
        
        # その他の設定
        other_group = QGroupBox("その他")
        other_layout = QFormLayout()
        other_group.setLayout(other_layout)
        
        # 画像保存先設定の追加
        self.image_save_path_edit = QLineEdit()
        self.browse_button = QPushButton("参照...")
        self.browse_button.clicked.connect(self.on_browse_clicked)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.image_save_path_edit)
        path_layout.addWidget(self.browse_button)
        
        other_layout.addRow("画像保存先:", path_layout)
        
        self.autoload_offset_spin = QSpinBox()
        self.autoload_offset_spin.setRange(0, 100)
        other_layout.addRow("自動読み込みオフセット:", self.autoload_offset_spin)
        
        layout.addWidget(other_group)
        layout.addStretch()
        
        return widget

    def on_browse_clicked(self):
        """フォルダ参照ボタン押下時の処理"""
        current_dir = self.image_save_path_edit.text()
        if not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~")
            
        dir_path = QFileDialog.getExistingDirectory(
            self, "画像保存先フォルダを選択", current_dir
        )
        
        if dir_path:
            self.image_save_path_edit.setText(dir_path)
    
    def create_music_pack_tab(self):
        """楽曲パック設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 説明ラベル
        label = QLabel("集計対象とする楽曲パックを選択してください")
        layout.addWidget(label)
        
        # 全選択/全解除ボタン
        button_layout = QHBoxLayout()
        select_all_button = QPushButton("全て選択")
        deselect_all_button = QPushButton("全て解除")
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
        save_condition_group = QGroupBox("画像保存条件")
        save_condition_layout = QVBoxLayout()
        save_condition_group.setLayout(save_condition_layout)
        
        self.autosave_button_group = QButtonGroup()
        self.autosave_invalid_radio = QRadioButton("保存しない")
        self.autosave_all_radio = QRadioButton("全て保存")
        self.autosave_updates_radio = QRadioButton("更新時のみ保存")
        
        self.autosave_button_group.addButton(self.autosave_invalid_radio, config_autosave_image.invalid.value)
        self.autosave_button_group.addButton(self.autosave_all_radio, config_autosave_image.all.value)
        self.autosave_button_group.addButton(self.autosave_updates_radio, config_autosave_image.only_updates.value)
        
        save_condition_layout.addWidget(self.autosave_invalid_radio)
        save_condition_layout.addWidget(self.autosave_all_radio)
        save_condition_layout.addWidget(self.autosave_updates_radio)
        
        layout.addWidget(save_condition_group)
        
        # ライバル欄編集グループ
        rival_edit_group = QGroupBox("ライバル欄の編集")
        rival_edit_layout = QVBoxLayout()
        rival_edit_group.setLayout(rival_edit_layout)
        
        self.rivalarea_button_group = QButtonGroup()
        self.rivalarea_invalid_radio = QRadioButton("そのまま")
        self.rivalarea_mosaic_radio = QRadioButton("モザイク")
        self.rivalarea_cut_radio = QRadioButton("カット")
        
        self.rivalarea_button_group.addButton(self.rivalarea_invalid_radio, config_modify_rivalarea.invalid.value)
        self.rivalarea_button_group.addButton(self.rivalarea_mosaic_radio, config_modify_rivalarea.mosaic.value)
        self.rivalarea_button_group.addButton(self.rivalarea_cut_radio, config_modify_rivalarea.cut.value)
        
        rival_edit_layout.addWidget(self.rivalarea_invalid_radio)
        rival_edit_layout.addWidget(self.rivalarea_mosaic_radio)
        rival_edit_layout.addWidget(self.rivalarea_cut_radio)
        
        layout.addWidget(rival_edit_group)
        
        # その他の設定
        other_group = QGroupBox("その他")
        other_layout = QVBoxLayout()
        other_group.setLayout(other_layout)
        
        self.write_statistics_check = QCheckBox("統計情報を書き込む")
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
        import_group = QGroupBox("画像からリザルトを登録")
        import_layout = QVBoxLayout()
        import_group.setLayout(import_layout)

        # 説明ラベル
        desc_label = QLabel("保存済みのリザルト画像からプレーログを登録します")
        import_layout.addWidget(desc_label)

        # 登録ボタン
        self.import_button = QPushButton("フォルダから画像を読み込んで登録")
        self.import_button.clicked.connect(self.on_import_from_images)
        import_layout.addWidget(self.import_button)

        # 進捗表示用ラベル
        self.import_status_label = QLabel("")
        import_layout.addWidget(self.import_status_label)

        layout.addWidget(import_group)
        layout.addStretch()

        return widget

    def on_import_from_images(self):
        """画像からリザルトを登録"""
        if not self.result_database or not self.screen_reader:
            self.import_status_label.setText("エラー: 登録機能が利用できません")
            return

        # フォルダ選択
        folder_path = QFileDialog.getExistingDirectory(
            self, "リザルト画像のフォルダを選択"
        )

        if not folder_path:
            return

        self.import_status_label.setText("読み込み中...")
        self.import_button.setEnabled(False)

        try:
            import glob
            from pathlib import Path

            # pngファイルを取得
            png_files = glob.glob(str(Path(folder_path) / "*.png"))

            registered_count = 0
            total_count = len(png_files)

            for i, png_file in enumerate(png_files):
                # 進捗表示
                self.import_status_label.setText(f"処理中... {i+1}/{total_count}")

                self.screen_reader.update_screen_from_file(png_file)
                if self.screen_reader.is_result():
                    r = self.screen_reader.read_result_screen()
                    if r:
                        # logger.info(f'[RESULT] {r}')
                        registered_count += 1
                        r.result.timestamp = os.path.getmtime(png_file)
                        self.result_database.add(r.result)

            # 完了メッセージ
            self.import_status_label.setText(
                f"完了: {total_count}件中{registered_count}件を登録しました"
            )

            self.result_database.save()
            self.result_database.results.sort()

        except Exception as e:
            self.import_status_label.setText(f"エラー: {str(e)}")
            logger.error(f"画像読み込みエラー: {e}")
        finally:
            self.import_button.setEnabled(True)

    def load_config_values(self):
        """設定値を読み込んでUIに反映"""
        # 機能設定
        self.enable_autotweet_check.setChecked(self.config.enable_autotweet)
        self.enable_judge_check.setChecked(self.config.enable_judge)
        self.enable_folder_updates_check.setChecked(self.config.enable_folder_updates)
        self.autoload_offset_spin.setValue(self.config.autoload_offset)
        
        # 画像保存先 (Configクラスに image_save_path プロパティがある前提)
        if hasattr(self.config, 'image_save_path'):
            self.image_save_path_edit.setText(self.config.image_save_path)
        
        # 楽曲パック設定
        if hasattr(self.config, 'target_music_packs'):
            for pack_name in self.config.target_music_packs:
                if pack_name in self.music_pack_checkboxes:
                    self.music_pack_checkboxes[pack_name].setChecked(True)
        
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
        
    def accept(self):
        """OKボタン押下時の処理"""
        # UIから設定値を取得してConfigに保存
        
        # 機能設定
        self.config.enable_autotweet = self.enable_autotweet_check.isChecked()
        self.config.enable_judge = self.enable_judge_check.isChecked()
        self.config.enable_folder_updates = self.enable_folder_updates_check.isChecked()
        self.config.autoload_offset = self.autoload_offset_spin.value()
        
        # 画像保存先
        self.config.image_save_path = self.image_save_path_edit.text()
        
        # 楽曲パック設定
        self.config.target_music_packs = [
            pack_name for pack_name, checkbox in self.music_pack_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        # 画像保存設定
        self.config.autosave_image_mode = config_autosave_image(self.autosave_button_group.checkedId())
        self.config.modify_rivalarea_mode = config_modify_rivalarea(self.rivalarea_button_group.checkedId())
        self.config.write_statistics = self.write_statistics_check.isChecked()
        
        # 設定を保存
        self.config.save_config()
        
        logger.info("設定を保存しました")
        
        # ダイアログを閉じる
        super().accept()
