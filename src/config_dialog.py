"""
設定ダイアログ
基本設定を行うためのダイアログウィンドウ
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLineEdit, QSpinBox, QCheckBox, QPushButton,
                               QGroupBox, QFileDialog, QTabWidget, QWidget,
                               QLabel, QDialogButtonBox, QRadioButton,
                               QButtonGroup, QScrollArea, QGridLayout, QProgressBar,
                               QComboBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIntValidator
import os
import datetime

from src.image_save_settings import ImageSaveSettings
from src.config import Config
from src.voice_guidance import start_voice_preview
from src.voice_audio import audio_output_devices
from src.classes import music_pack
from src.logger import get_logger
from src.result import OneResult, PlayOption
from src.result_database import ResultDatabase
from src.screen_reader import ScreenReader
from src.network_info import get_local_ipv4_interfaces
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
        self.setMinimumHeight(700)
        
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
        feature_scroll = QScrollArea()
        feature_scroll.setWidgetResizable(True)
        feature_scroll.setWidget(self.create_feature_tab())
        tab_widget.addTab(feature_scroll, self.ui.tab.feature)
        additional_scroll = QScrollArea()
        additional_scroll.setWidgetResizable(True)
        additional_scroll.setWidget(self.create_additional_tab())
        tab_widget.addTab(additional_scroll, self.ui.tab.additional)
        random_lane_scroll = QScrollArea()
        random_lane_scroll.setWidgetResizable(True)
        random_lane_scroll.setWidget(self.create_random_lane_tab())
        tab_widget.addTab(random_lane_scroll, self.ui.tab.random_lane)
        tab_widget.addTab(self.create_voice_guidance_tab(), self.ui.tab.voice_guidance)
        tab_widget.addTab(self.create_overlay_tab(), self.ui.tab.overlay)
        tab_widget.addTab(self.create_difficulty_table_tab(), self.ui.tab.difficulty_table)
        # tab_widget.addTab(self.create_music_pack_tab(), self.ui.tab.music_pack)
        image_save_scroll = QScrollArea()
        image_save_scroll.setWidgetResizable(True)
        image_save_scroll.setWidget(self.create_image_save_tab())
        tab_widget.addTab(image_save_scroll, self.ui.tab.image_save)
        tab_widget.addTab(self.create_data_import_tab(), self.ui.tab.data_import)  # 追加
        tab_widget.addTab(self.create_rival_tab(), self.ui.tab.rival)

        # ボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def create_voice_guidance_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.voice_basic_group = QGroupBox(self.ui.voice.basic)
        basic_layout = QVBoxLayout(self.voice_basic_group)
        layout.addWidget(self.voice_basic_group)
        enable_row = QHBoxLayout()
        self.enable_voice_guidance_check = QCheckBox(self.ui.voice.enable)
        enable_row.addWidget(self.enable_voice_guidance_check)
        self.voice_test_button = QPushButton(self.ui.voice.test)
        self.voice_test_button.clicked.connect(self.on_voice_test)
        enable_row.addWidget(self.voice_test_button)
        enable_row.addStretch()
        basic_layout.addLayout(enable_row)
        self.voice_test_timer = QTimer(self)
        self.voice_test_timer.setInterval(100)
        self.voice_test_timer.timeout.connect(self._poll_voice_test)
        form = QFormLayout()
        self.voicevox_url_edit = QLineEdit()
        self.voicevox_speaker_spin = QSpinBox()
        self.voicevox_speaker_spin.setRange(0, 2147483647)
        self.voice_output_combo = QComboBox()
        self.voice_output_combo.addItem(self.ui.voice.system_default, '')
        for device_id, name in audio_output_devices():
            self.voice_output_combo.addItem(name, device_id)
        self.voice_volume_spin = QSpinBox()
        self.voice_volume_spin.setRange(0, 100)
        self.voice_volume_spin.setSuffix('%')
        self.voice_pan_spin = QSpinBox()
        self.voice_pan_spin.setRange(-100, 100)
        self.voice_pan_spin.setToolTip(self.ui.voice.pan_tip)
        form.addRow(self.ui.voice.url, self.voicevox_url_edit)
        form.addRow(self.ui.voice.speaker, self.voicevox_speaker_spin)
        form.addRow(self.ui.voice.output_device, self.voice_output_combo)
        form.addRow(self.ui.voice.volume, self.voice_volume_spin)
        form.addRow(self.ui.voice.pan, self.voice_pan_spin)
        basic_layout.addLayout(form)
        self.voice_options = QGroupBox(self.ui.voice.items)
        options_layout = QVBoxLayout(self.voice_options)
        self.voice_item_checks = {}
        for key in ('startup', 'lane_status', 'missing_chart', 'chart_info', 'personal_best', 'result_saved', 'errors', 'shutdown'):
            check = QCheckBox(getattr(self.ui.voice, key))
            self.voice_item_checks[key] = check
            options_layout.addWidget(check)
        layout.addWidget(self.voice_options)
        help_label = QLabel(self.ui.voice.help)
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        layout.addStretch()
        self.enable_voice_guidance_check.toggled.connect(self.voice_options.setEnabled)
        return widget

    def on_voice_test(self):
        if self.voice_test_timer.isActive():
            return
        url = self.voicevox_url_edit.text().strip().rstrip('/') or 'http://127.0.0.1:50021'
        self.voice_test_worker = start_voice_preview(
            url, self.voicevox_speaker_spin.value(), self.voice_output_combo.currentData(),
            self.voice_volume_spin.value(), self.voice_pan_spin.value(),
        )
        self.voice_test_button.setEnabled(False)
        self.voice_test_timer.start()

    def _poll_voice_test(self):
        if not self.voice_test_worker.is_alive():
            self.voice_test_timer.stop()
            self.voice_test_button.setEnabled(True)

    def create_feature_tab(self):
        """基本設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # ゲーム画面取得グループ
        game_capture_group = QGroupBox(self.ui.feature.game_capture_group)
        game_capture_layout = QVBoxLayout()
        game_capture_group.setLayout(game_capture_layout)

        self.capture_method_group = QButtonGroup()
        self.capture_method_direct_legacy_radio = QRadioButton(self.ui.feature.capture_method_direct_legacy)
        self.capture_method_direct_radio = QRadioButton(self.ui.feature.capture_method_direct)
        self.capture_method_obs_radio = QRadioButton(self.ui.feature.capture_method_obs)
        self.capture_method_spout_radio = QRadioButton(self.ui.feature.capture_method_spout)
        self.capture_method_group.addButton(self.capture_method_direct_legacy_radio, 1)
        self.capture_method_group.addButton(self.capture_method_direct_radio, 0)
        self.capture_method_group.addButton(self.capture_method_obs_radio, 2)
        self.capture_method_group.addButton(self.capture_method_spout_radio, 3)

        capture_method_layout = QGridLayout()
        capture_method_layout.addWidget(self.capture_method_direct_legacy_radio, 0, 0)
        capture_method_layout.addWidget(self.capture_method_direct_radio, 0, 1)
        capture_method_layout.addWidget(self.capture_method_obs_radio, 1, 0)
        capture_method_layout.addWidget(self.capture_method_spout_radio, 1, 1)
        game_capture_layout.addLayout(capture_method_layout)

        spout_capture_form = QFormLayout()
        self.spout_sender_edit = QLineEdit()
        self.spout_sender_edit.setPlaceholderText("Spout_OBS_Filter")
        spout_capture_form.addRow(self.ui.feature.spout_sender, self.spout_sender_edit)
        game_capture_layout.addLayout(spout_capture_form)

        self.direct_capture_all_monitors_check = QCheckBox(self.ui.feature.direct_capture_all_monitors)
        self.direct_capture_all_monitors_check.setToolTip(self.ui.feature.direct_capture_all_monitors_tip)
        self.direct_capture_all_monitors_check.setVisible(False)
        game_capture_layout.addWidget(self.direct_capture_all_monitors_check)
        self.capture_method_group.idClicked.connect(self._update_direct_capture_option_enabled)
        self.capture_method_group.idClicked.connect(self._update_spout_capture_option_enabled)

        self.enable_music_select_score_import_check = QCheckBox(self.ui.feature.enable_music_select_score_import)
        game_capture_layout.addWidget(self.enable_music_select_score_import_check)

        layout.addWidget(game_capture_group)
        
        # その他の設定
        other_group = QGroupBox(self.ui.feature.other_group)
        other_layout = QFormLayout()
        other_group.setLayout(other_layout)

        # 最前面表示
        self.keep_on_top_check = QCheckBox(self.ui.feature.keep_on_top)
        other_layout.addRow(self.keep_on_top_check)

        layout.addWidget(other_group)
        layout.addStretch()

        return widget

    def create_additional_tab(self):
        """ツイート機能とスマホ連携の設定。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
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
        
        data_display_group = QGroupBox(self.ui.feature.data_display_group)
        data_display_layout = QFormLayout(data_display_group)
        self.autoload_offset_spin = QSpinBox()
        self.autoload_offset_spin.setRange(0, 100000)
        self.autoload_offset_spin.setToolTip(self.ui.feature.autoload_offset_help)
        offset_layout = QHBoxLayout()
        offset_layout.addWidget(self.autoload_offset_spin)
        offset_layout.addWidget(QLabel(self.ui.feature.autoload_offset_unit))
        data_display_layout.addRow(self.ui.feature.autoload_offset, offset_layout)
        self.autoload_offset_help_label = QLabel(self.ui.feature.autoload_offset_help)
        self.autoload_offset_help_label.setWordWrap(True)
        data_display_layout.addRow(self.autoload_offset_help_label)

        self.websocket_data_port = QLineEdit()
        self.websocket_data_port.setValidator(QIntValidator(1000, 65535, self))
        data_display_layout.addRow(self.ui.feature.websocket_port, self.websocket_data_port)
        layout.addWidget(data_display_group)

        # スマホ連携設定
        mobile_group = QGroupBox(self.ui.feature.mobile_score_server_group)
        mobile_layout = QFormLayout()
        mobile_group.setLayout(mobile_layout)
        mobile_validator = QIntValidator(1000, 65535, self)
        self.mobile_score_server_enabled_check = QCheckBox(
            self.ui.feature.mobile_score_server_enabled
        )
        mobile_layout.addRow(self.mobile_score_server_enabled_check)

        self.mobile_score_server_port_edit = QLineEdit()
        self.mobile_score_server_port_edit.setValidator(mobile_validator)
        mobile_layout.addRow(
            self.ui.feature.mobile_score_server_port,
            self.mobile_score_server_port_edit,
        )

        self.mobile_score_server_interface_combo = QComboBox()
        mobile_layout.addRow(
            self.ui.feature.mobile_score_server_interface,
            self.mobile_score_server_interface_combo,
        )

        self.result_image_cache_enabled_check = QCheckBox(self.ui.feature.cache_enabled)
        mobile_layout.addRow(self.result_image_cache_enabled_check)
        self.result_image_cache_group = QButtonGroup(self)
        self.result_image_cache_all_radio = QRadioButton(self.ui.feature.cache_all)
        self.result_image_cache_100_radio = QRadioButton(self.ui.feature.cache_100)
        self.result_image_cache_custom_radio = QRadioButton(self.ui.feature.cache_custom)
        self.result_image_cache_group.addButton(self.result_image_cache_all_radio, 0)
        self.result_image_cache_group.addButton(self.result_image_cache_100_radio, 1)
        self.result_image_cache_group.addButton(self.result_image_cache_custom_radio, 2)
        cache_choices = QHBoxLayout()
        cache_choices.addWidget(self.result_image_cache_all_radio)
        cache_choices.addWidget(self.result_image_cache_100_radio)
        cache_choices.addWidget(self.result_image_cache_custom_radio)
        self.result_image_cache_limit_spin = QSpinBox()
        self.result_image_cache_limit_spin.setRange(1, 2147483647)
        cache_choices.addWidget(self.result_image_cache_limit_spin)
        mobile_layout.addRow(self.ui.feature.cache_limit, cache_choices)
        cache_help = QLabel(self.ui.feature.cache_help)
        cache_help.setWordWrap(True)
        mobile_layout.addRow(cache_help)
        self.result_image_cache_enabled_check.toggled.connect(self._update_result_image_cache_enabled)
        self.result_image_cache_custom_radio.toggled.connect(self._update_result_image_cache_enabled)

        layout.addWidget(mobile_group)

        layout.addStretch()
        return widget

    def _update_result_image_cache_enabled(self, *_args):
        enabled = self.result_image_cache_enabled_check.isChecked()
        for button in self.result_image_cache_group.buttons():
            button.setEnabled(enabled)
        self.result_image_cache_limit_spin.setEnabled(
            enabled and self.result_image_cache_custom_radio.isChecked()
        )

    def create_overlay_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.enable_game_overlay_check = QCheckBox(self.ui.overlay.enable)
        layout.addWidget(self.enable_game_overlay_check)
        self.overlay_items_group = QGroupBox(self.ui.overlay.items)
        items_layout = QVBoxLayout(self.overlay_items_group)
        self.overlay_item_checks = {}
        for key in ('random_lane', 'song_history', 'today_results'):
            check = QCheckBox(getattr(self.ui.overlay, key))
            self.overlay_item_checks[key] = check
            items_layout.addWidget(check)
        layout.addWidget(self.overlay_items_group)
        self.overlay_log_format_group = QGroupBox(self.ui.overlay.log_format)
        format_layout = QVBoxLayout(self.overlay_log_format_group)
        self.overlay_show_lane_numbers_check = QCheckBox(self.ui.overlay.show_lane_numbers)
        format_layout.addWidget(self.overlay_show_lane_numbers_check)
        layout.addWidget(self.overlay_log_format_group)
        help_label = QLabel(self.ui.overlay.help)
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.enable_game_overlay_check.toggled.connect(self.overlay_items_group.setEnabled)
        self.enable_game_overlay_check.toggled.connect(self.overlay_log_format_group.setEnabled)
        layout.addStretch()
        return widget

    def create_random_lane_tab(self):
        """RANDOMレーン認識の設定タブ。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.enable_random_lane_analysis_check = QCheckBox(
            self.ui.feature.enable_random_lane_analysis
        )
        self.enable_random_lane_analysis_check.setToolTip(
            self.ui.feature.enable_random_lane_analysis_tip
        )
        layout.addWidget(self.enable_random_lane_analysis_check)

        template_form = QFormLayout()
        template_row = QHBoxLayout()
        self.random_lane_template_folder_edit = QLineEdit()
        self.random_lane_template_browse_button = QPushButton(self.ui.dialog.browse)
        self.random_lane_template_browse_button.clicked.connect(self.on_random_lane_template_browse)
        template_row.addWidget(self.random_lane_template_folder_edit)
        template_row.addWidget(self.random_lane_template_browse_button)
        template_form.addRow(self.ui.feature.random_lane_template_folder, template_row)
        layout.addLayout(template_form)
        template_tip = QLabel(self.ui.feature.random_lane_template_tip)
        template_tip.setWordWrap(True)
        layout.addWidget(template_tip)

        self.random_lane_band_edit_check = QCheckBox(self.ui.feature.random_lane_band_edit)
        self.random_lane_band_edit_check.setToolTip(self.ui.feature.random_lane_band_edit_tip)
        self.random_lane_band_edit_check.toggled.connect(self._update_random_lane_band_enabled)
        layout.addWidget(self.random_lane_band_edit_check)

        band_form = QFormLayout()
        self.random_lane_band_controls = {}
        for side in ('1P', '2P'):
            row = QHBoxLayout()
            top_spin = QSpinBox()
            top_spin.setRange(0, 995)
            height_spin = QSpinBox()
            height_spin.setRange(1, 300)
            top_spin.setSuffix(' px')
            height_spin.setSuffix(' px')
            # ROI starts at Y=84 in a 1080px frame. Keep the band inside it.
            top_spin.valueChanged.connect(
                lambda top, height=height_spin: height.setMaximum(min(300, 996 - top))
            )
            row.addWidget(QLabel(self.ui.feature.random_lane_band_top))
            row.addWidget(top_spin)
            row.addWidget(QLabel(self.ui.feature.random_lane_band_height))
            row.addWidget(height_spin)
            band_form.addRow(f'{side}:', row)
            self.random_lane_band_controls[side] = (top_spin, height_spin)
        layout.addLayout(band_form)
        band_tip = QLabel(self.ui.feature.random_lane_band_tip)
        band_tip.setWordWrap(True)
        layout.addWidget(band_tip)
        self.enable_random_lane_analysis_check.toggled.connect(
            self._update_random_lane_band_enabled
        )

        layout.addStretch()
        return widget

    def create_difficulty_table_tab(self):
        """難易度表設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        katate_group = QGroupBox(self.ui.difficulty_table.katate_group)
        katate_layout = QVBoxLayout()
        katate_group.setLayout(katate_layout)

        self.enable_katate_difficulty_display_check = QCheckBox(
            self.ui.difficulty_table.enable_katate_difficulty_display
        )
        katate_layout.addWidget(self.enable_katate_difficulty_display_check)

        self.enable_katate_tweet_grouping_check = QCheckBox(
            self.ui.difficulty_table.enable_katate_tweet_grouping
        )
        katate_layout.addWidget(self.enable_katate_tweet_grouping_check)

        layout.addWidget(katate_group)
        layout.addStretch()
        return widget

    def _update_direct_capture_option_enabled(self, *_args):
        """旧方式の直接取得向け詳細設定を、旧方式選択時だけ操作可能にする。"""
        is_legacy_direct = self.capture_method_group.checkedId() == 1
        self.direct_capture_all_monitors_check.setVisible(is_legacy_direct)
        self.direct_capture_all_monitors_check.setEnabled(is_legacy_direct)

    def _update_spout_capture_option_enabled(self, *_args):
        spout_enabled = self.capture_method_group.checkedId() == 3
        self.spout_sender_edit.setEnabled(spout_enabled)
        if hasattr(self, 'enable_random_lane_analysis_check'):
            self.enable_random_lane_analysis_check.setEnabled(spout_enabled)
            if not spout_enabled:
                self.enable_random_lane_analysis_check.setChecked(False)
        self._update_random_lane_band_enabled()

    def _update_random_lane_band_enabled(self, *_args):
        spout_enabled = self.capture_method_group.checkedId() == 3
        if hasattr(self, "random_lane_template_folder_edit"):
            active = spout_enabled and self.enable_random_lane_analysis_check.isChecked()
            self.random_lane_template_folder_edit.setEnabled(active)
            self.random_lane_template_browse_button.setEnabled(active)
            self.random_lane_band_edit_check.setEnabled(active)
        if hasattr(self, 'random_lane_band_controls'):
            for controls in self.random_lane_band_controls.values():
                for control in controls:
                    control.setEnabled(
                        spout_enabled and self.enable_random_lane_analysis_check.isChecked()
                        and self.random_lane_band_edit_check.isChecked()
                    )

    def on_random_lane_template_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, self.ui.feature.random_lane_template_folder,
            self.random_lane_template_folder_edit.text(),
        )
        if folder:
            self.random_lane_template_folder_edit.setText(folder)

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
        self.image_save_tab = ImageSaveSettings(self.ui, self)
        self.image_save_path_edit = self.image_save_tab.image_save_path_edit
        self.browse_button = self.image_save_tab.browse_button
        return self.image_save_tab

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

        self.include_legacy_v2_logs_check = QCheckBox(self.ui.data_import.include_legacy_v2_logs)
        pkl_import_layout.addWidget(self.include_legacy_v2_logs_check)

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
        self.enable_voice_guidance_check.setChecked(self.config.enable_voice_guidance)
        self.voice_options.setEnabled(self.config.enable_voice_guidance)
        for key, check in self.voice_item_checks.items():
            check.setChecked(getattr(self.config, 'voice_' + key))
        self.voicevox_url_edit.setText(self.config.voicevox_url)
        self.voicevox_speaker_spin.setValue(self.config.voicevox_speaker_id)
        device_id = self.config.voice_output_device
        device_index = self.voice_output_combo.findData(device_id)
        if device_index < 0:
            self.voice_output_combo.addItem(self.ui.voice.output_unavailable, device_id)
            device_index = self.voice_output_combo.count() - 1
        self.voice_output_combo.setCurrentIndex(device_index)
        self.voice_volume_spin.setValue(self.config.voice_volume)
        self.voice_pan_spin.setValue(self.config.voice_pan)
        # 機能設定
        self.keep_on_top_check.setChecked(self.config.keep_on_top)
        self.enable_autotweet_check.setChecked(self.config.enable_autotweet)
        self.enable_judge_check.setChecked(self.config.enable_judge)
        self.enable_folder_updates_check.setChecked(self.config.enable_folder_updates)
        self.enable_music_select_score_import_check.setChecked(self.config.enable_music_select_score_import)
        self.enable_game_overlay_check.setChecked(self.config.enable_game_overlay)
        self.overlay_items_group.setEnabled(self.config.enable_game_overlay)
        self.overlay_log_format_group.setEnabled(self.config.enable_game_overlay)
        self.overlay_show_lane_numbers_check.setChecked(self.config.overlay_show_lane_numbers)
        for key, check in self.overlay_item_checks.items():
            check.setChecked(getattr(self.config, 'overlay_' + key))
        self.enable_random_lane_analysis_check.setChecked(
            bool(getattr(self.config, 'enable_random_lane_analysis', False))
        )
        for side, (top_spin, height_spin) in self.random_lane_band_controls.items():
            top, bottom = self.config.random_lane_detection_bands[side]
            top_spin.setValue(top)
            height_spin.setValue(bottom - top)
        self.random_lane_band_edit_check.setChecked(False)
        capture_method = getattr(self.config, 'capture_method', 'direct_window_legacy')
        if capture_method == 'obs_websocket':
            self.capture_method_obs_radio.setChecked(True)
        elif capture_method == 'spout':
            self.capture_method_spout_radio.setChecked(True)
        elif capture_method == 'direct_window_legacy':
            self.capture_method_direct_legacy_radio.setChecked(True)
        else:
            self.capture_method_direct_radio.setChecked(True)
        self.random_lane_template_folder_edit.setText(self.config.random_lane_template_folder)
        self.spout_sender_edit.setText(
            str(getattr(self.config, 'spout_sender_name', 'Spout_OBS_Filter'))
        )
        self._update_spout_capture_option_enabled()
        self.direct_capture_all_monitors_check.setChecked(
            bool(getattr(self.config, 'direct_capture_all_monitors', False))
        )
        self._update_direct_capture_option_enabled()
        self.autoload_offset_spin.setValue(self.config.autoload_offset)
        if hasattr(self, 'websocket_data_port') and hasattr(self.config, 'websocket_data_port'):
            self.websocket_data_port.setText(str(self.config.websocket_data_port))
        if hasattr(self, 'mobile_score_server_enabled_check'):
            self.mobile_score_server_enabled_check.setChecked(
                bool(getattr(self.config, 'mobile_score_server_enabled', False))
            )
        if hasattr(self, 'mobile_score_server_port_edit'):
            self.mobile_score_server_port_edit.setText(
                str(getattr(self.config, 'mobile_score_server_port', 8787))
            )
        if hasattr(self, 'mobile_score_server_interface_combo'):
            self._load_mobile_score_server_interfaces()
        
        
        # # 楽曲パック設定
        # if hasattr(self.config, 'target_music_packs'):
        #     for pack_name in self.config.target_music_packs:
        #         if pack_name in self.music_pack_checkboxes:
        #             self.music_pack_checkboxes[pack_name].setChecked(True)
        
        # 画像保存設定
        self.image_save_tab.load_config_values(self.config)
        self.result_image_cache_enabled_check.setChecked(self.config.result_image_cache_enabled)
        limit = self.config.result_image_cache_limit
        self.result_image_cache_limit_spin.setValue(limit if limit > 0 else 100)
        choice = 0 if limit == 0 else 1 if limit == 100 else 2
        self.result_image_cache_group.button(choice).setChecked(True)
        self._update_result_image_cache_enabled()

        if hasattr(self.config, 'include_legacy_v2_logs'):
            self.include_legacy_v2_logs_check.setChecked(self.config.include_legacy_v2_logs)

        if hasattr(self.config, 'enable_katate_difficulty_display'):
            self.enable_katate_difficulty_display_check.setChecked(
                self.config.enable_katate_difficulty_display
            )
        if hasattr(self.config, 'enable_katate_tweet_grouping'):
            self.enable_katate_tweet_grouping_check.setChecked(
                self.config.enable_katate_tweet_grouping
            )

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

    def _load_mobile_score_server_interfaces(self):
        """スマホ閲覧URL表示に使うNIC候補を読み込む。"""
        selected = getattr(self.config, 'mobile_score_server_interface', '')
        combo = self.mobile_score_server_interface_combo
        combo.clear()
        combo.addItem(self.ui.feature.mobile_score_server_interface_auto, "")

        found_selected = not selected
        for interface in get_local_ipv4_interfaces():
            combo.addItem(f"{interface.name} ({interface.address})", interface.name)
            if interface.name == selected:
                combo.setCurrentIndex(combo.count() - 1)
                found_selected = True

        if selected and not found_selected:
            combo.addItem(f"{selected} ({self.ui.feature.mobile_score_server_interface_missing})", selected)
            combo.setCurrentIndex(combo.count() - 1)

    def accept(self):
        """OKボタン押下時の処理"""
        # UIから設定値を取得してConfigに保存
        
        self.config.enable_voice_guidance = self.enable_voice_guidance_check.isChecked()
        for key, check in self.voice_item_checks.items():
            setattr(self.config, 'voice_' + key, check.isChecked())
        self.config.voicevox_url = self.voicevox_url_edit.text().strip().rstrip('/') or 'http://127.0.0.1:50021'
        self.config.voicevox_speaker_id = self.voicevox_speaker_spin.value()
        self.config.voice_output_device = self.voice_output_combo.currentData()
        self.config.voice_volume = self.voice_volume_spin.value()
        self.config.voice_pan = self.voice_pan_spin.value()
        # 機能設定
        self.config.keep_on_top = self.keep_on_top_check.isChecked()
        self.config.enable_autotweet = self.enable_autotweet_check.isChecked()
        self.config.enable_judge = self.enable_judge_check.isChecked()
        self.config.enable_folder_updates = self.enable_folder_updates_check.isChecked()
        self.config.enable_music_select_score_import = self.enable_music_select_score_import_check.isChecked()
        self.config.enable_game_overlay = self.enable_game_overlay_check.isChecked()
        self.config.overlay_show_lane_numbers = self.overlay_show_lane_numbers_check.isChecked()
        for key, check in self.overlay_item_checks.items():
            setattr(self.config, 'overlay_' + key, check.isChecked())
        self.config.enable_random_lane_analysis = self.enable_random_lane_analysis_check.isChecked()
        self.config.random_lane_detection_bands = {
            side: [top.value(), top.value() + height.value()]
            for side, (top, height) in self.random_lane_band_controls.items()
        }
        self.config.spout_sender_name = self.spout_sender_edit.text().strip() or 'Spout_OBS_Filter'
        self.config.random_lane_template_folder = self.random_lane_template_folder_edit.text().strip()
        capture_method_by_id = {
            0: 'direct_window',
            1: 'direct_window_legacy',
            2: 'obs_websocket',
            3: 'spout',
        }
        self.config.capture_method = capture_method_by_id.get(
            self.capture_method_group.checkedId(),
            'direct_window_legacy',
        )
        self.config.direct_capture_all_monitors = self.direct_capture_all_monitors_check.isChecked()
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
        self.config.mobile_score_server_enabled = self.mobile_score_server_enabled_check.isChecked()
        try:
            mobile_port = int(self.mobile_score_server_port_edit.text())
            if 1000 <= mobile_port <= 65535:
                self.config.mobile_score_server_port = mobile_port
            else:
                logger.warning(f"無効なスマホ用HTTPポート番号: {mobile_port}. デフォルト値を使用します")
        except ValueError:
            logger.warning("スマホ用HTTPポート番号の変換に失敗しました。デフォルト値を使用します")
        if hasattr(self, 'mobile_score_server_interface_combo'):
            self.config.mobile_score_server_interface = (
                self.mobile_score_server_interface_combo.currentData() or ""
            )
        
        
        # # 楽曲パック設定
        # self.config.target_music_packs = [
        #     pack_name for pack_name, checkbox in self.music_pack_checkboxes.items()
        #     if checkbox.isChecked()
        # ]
        
        # 画像保存設定
        self.image_save_tab.apply_to_config(self.config)
        self.config.result_image_cache_enabled = self.result_image_cache_enabled_check.isChecked()
        choice = self.result_image_cache_group.checkedId()
        self.config.result_image_cache_limit = (
            0 if choice == 0 else 100 if choice == 1 else self.result_image_cache_limit_spin.value()
        )
        if self.result_database:
            self.result_database.trim_result_image_cache()
        self.config.include_legacy_v2_logs = self.include_legacy_v2_logs_check.isChecked()
        self.config.enable_katate_difficulty_display = self.enable_katate_difficulty_display_check.isChecked()
        self.config.enable_katate_tweet_grouping = self.enable_katate_tweet_grouping_check.isChecked()
        
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
