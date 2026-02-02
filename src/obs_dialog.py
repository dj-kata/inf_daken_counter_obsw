"""
OBS制御設定ダイアログ
OBS連携の詳細設定を行うためのダイアログウィンドウ
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QPushButton, QGroupBox, QComboBox, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QDialogButtonBox, QSpinBox, QWidget, QTabWidget,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QAbstractItemView)
from PySide6.QtCore import Qt, Signal
import traceback

from src.config import Config
from src.obs_websocket_manager import OBSWebSocketManager
from src.logger import get_logger
logger = get_logger(__name__)


class OBSControlDialog(QDialog):
    """OBS制御設定ダイアログクラス"""
    
    # トリガー定義
    TRIGGERS = {
        "app_start": "アプリ起動時",
        "app_end": "アプリ終了時", 
        "select_start": "選曲画面開始時",
        "select_end": "選曲画面終了時",
        "play_start": "プレー画面開始時",
        "play_end": "プレー画面終了時",
        "result_start": "リザルト画面開始時",
        "result_end": "リザルト画面終了時"
    }
    
    # アクション定義
    ACTIONS = {
        "show_source": "ソースを表示",
        "hide_source": "ソースを非表示",
        "switch_scene": "シーンを切り替え",
    }
    
    def __init__(self, config: Config, obs_manager: OBSWebSocketManager, parent=None):
        super().__init__(parent)
        
        self.config = config
        self.obs_manager = obs_manager

        # 接続状態変化を監視
        self.obs_manager.connection_changed.connect(self.on_connection_changed)
        
        # OBSデータ
        self.scenes_list = []
        self.sources_dict = {}  # {scene_name: [source_list]}
        self.all_sources_list = []
        
        # ダイアログ設定
        self.setWindowTitle("OBS制御設定")
        self.setMinimumWidth(900)
        self.setMinimumHeight(700)
        
        # UI初期化
        self.init_ui()
        
        # OBSデータを取得
        self.refresh_obs_data()
        
        # 現在の設定を読み込み
        self.load_current_settings()
    
    def init_ui(self):
        """UI初期化"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # OBS接続状態表示
        status_group = QGroupBox("OBS接続状態")
        status_layout = QHBoxLayout()
        status_group.setLayout(status_layout)
        
        self.status_label = QLabel("接続確認中...")
        status_layout.addWidget(self.status_label)
        
        reconnect_btn = QPushButton("再接続")
        reconnect_btn.clicked.connect(self.reconnect_obs)
        status_layout.addWidget(reconnect_btn)
        status_layout.addStretch()
        
        layout.addWidget(status_group)
        
        # タブウィジェット
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # 各タブを作成
        tab_widget.addTab(self.create_control_settings_tab(), "制御設定")
        tab_widget.addTab(self.create_monitor_source_tab(), "監視対象ソース")
        
        # ボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # 接続状態を更新
        self.update_connection_status()
    
    def create_control_settings_tab(self):
        """制御設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 説明ラベル
        info_label = QLabel(
            "ゲーム画面の状態変化に応じてOBSを自動制御する設定を行います。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 制御設定リスト
        list_group = QGroupBox("登録済み制御設定")
        list_layout = QVBoxLayout()
        list_group.setLayout(list_layout)
        
        self.settings_table = QTableWidget()
        self.settings_table.setColumnCount(4)
        self.settings_table.setHorizontalHeaderLabels(
            ["トリガー", "アクション", "対象", "備考"]
        )
        self.settings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.settings_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.settings_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        list_layout.addWidget(self.settings_table)
        
        # ボタン
        button_layout = QHBoxLayout()
        add_btn = QPushButton("追加")
        add_btn.clicked.connect(self.add_control_setting)
        button_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("編集")
        edit_btn.clicked.connect(self.edit_control_setting)
        button_layout.addWidget(edit_btn)
        
        remove_btn = QPushButton("削除")
        remove_btn.clicked.connect(self.remove_control_setting)
        button_layout.addWidget(remove_btn)
        
        button_layout.addStretch()
        list_layout.addLayout(button_layout)
        
        layout.addWidget(list_group)
        
        return widget
    
    def create_monitor_source_tab(self):
        """監視対象ソースタブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 説明
        info_label = QLabel(
            "ゲーム画面をキャプチャするOBSソースを指定してください。\n"
            "このソースからゲーム画面を取得して状態判定を行います。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # ソース選択
        source_group = QGroupBox("監視対象ソース")
        source_layout = QFormLayout()
        source_group.setLayout(source_layout)
        
        self.monitor_source_combo = QComboBox()
        source_layout.addRow("ソース名:", self.monitor_source_combo)
        
        # 現在の設定
        current_label = QLabel()
        if self.config.monitor_source_name:
            current_label.setText(f"現在の設定: {self.config.monitor_source_name}")
        else:
            current_label.setText("現在の設定: (未設定)")
        source_layout.addRow("", current_label)
        
        layout.addWidget(source_group)
        
        # 更新ボタン
        refresh_btn = QPushButton("ソースリストを更新")
        refresh_btn.clicked.connect(self.refresh_source_list)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
        
        return widget
    
    def refresh_obs_data(self):
        """OBSデータを取得"""
        if not self.obs_manager.is_connected:
            logger.warning("OBS未接続のため、データを取得できません")
            return
        
        try:
            # シーン一覧を取得
            self.scenes_list = self.obs_manager.get_scenes()
            
            # 各シーンのソースを取得
            self.sources_dict.clear()
            self.all_sources_list.clear()
            
            for scene_data in self.scenes_list:
                scene_name = scene_data.get('sceneName', '')
                if scene_name:
                    sources = self.obs_manager.get_sources(scene_name)
                    self.sources_dict[scene_name] = sources
                    self.all_sources_list.extend(sources)
            
            # 重複を除去
            self.all_sources_list = list(set(self.all_sources_list))
            
            logger.info(f"OBSデータ取得完了: {len(self.scenes_list)}シーン, "
                       f"{len(self.all_sources_list)}ソース")
            
        except Exception as e:
            logger.error(f"OBSデータ取得エラー: {traceback.format_exc()}")
    
    def refresh_source_list(self):
        """ソースリストを更新"""
        self.refresh_obs_data()
        
        # コンボボックスを更新
        self.monitor_source_combo.clear()
        self.monitor_source_combo.addItems(sorted(self.all_sources_list))
        
        # 現在の設定値を選択
        if self.config.monitor_source_name:
            index = self.monitor_source_combo.findText(self.config.monitor_source_name)
            if index >= 0:
                self.monitor_source_combo.setCurrentIndex(index)
        
        QMessageBox.information(self, "更新完了", "ソースリストを更新しました。")
    
    def reconnect_obs(self):
        """OBS再接続"""
        # 自動再接続を一時的に停止
        self.obs_manager.auto_reconnect = False
        
        # 再接続を試みる
        self.obs_manager.disconnect()
        success = self.obs_manager.connect()
        
        # 自動再接続を再有効化
        self.obs_manager.auto_reconnect = True
        
        if success:
            QMessageBox.information(self, "再接続", "OBSへの再接続に成功しました。")
        else:
            QMessageBox.warning(self, "再接続失敗", "OBSへの再接続に失敗しました。")
    
    def closeEvent(self, event):
        """ダイアログクローズ時の処理"""
        # シグナル接続を解除（メモリリーク防止）
        try:
            self.obs_manager.connection_changed.disconnect(self.on_connection_changed)
        except:
            pass
        
        event.accept()

    def update_connection_status(self):
        """接続状態表示を更新"""
        status_msg, is_connected = self.obs_manager.get_status()
        self.status_label.setText(status_msg)
        
        if is_connected:
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def on_connection_changed(self, is_connected: bool, message: str):
        """接続状態変化時のハンドラ"""
        # ステータスラベルを更新
        self.status_label.setText(message)
        
        if is_connected:
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            # 接続成功時にOBSデータを再取得
            self.refresh_obs_data()
        else:
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
 
    def load_current_settings(self):
        """現在の設定を読み込み"""
        # 制御設定テーブルを更新
        self.settings_table.setRowCount(0)
        for setting in self.config.obs_control_settings:
            self.add_setting_to_table(setting)
        
        # 監視対象ソースを更新
        self.monitor_source_combo.clear()
        self.monitor_source_combo.addItems(sorted(self.all_sources_list))
        if self.config.monitor_source_name:
            index = self.monitor_source_combo.findText(self.config.monitor_source_name)
            if index >= 0:
                self.monitor_source_combo.setCurrentIndex(index)
        
    def add_setting_to_table(self, setting: dict):
        """制御設定をテーブルに追加"""
        row = self.settings_table.rowCount()
        self.settings_table.insertRow(row)
        
        trigger_text = self.TRIGGERS.get(setting.get("trigger", ""), "不明")
        action_text = self.ACTIONS.get(setting.get("action", ""), "不明")
        target_text = setting.get("target", "")
        note_text = setting.get("note", "")
        
        self.settings_table.setItem(row, 0, QTableWidgetItem(trigger_text))
        self.settings_table.setItem(row, 1, QTableWidgetItem(action_text))
        self.settings_table.setItem(row, 2, QTableWidgetItem(target_text))
        self.settings_table.setItem(row, 3, QTableWidgetItem(note_text))
    
    def add_control_setting(self):
        """制御設定を追加"""
        # 簡易的な追加ダイアログ（実際にはより詳細なダイアログが必要）
        from PySide6.QtWidgets import QInputDialog
        
        # トリガー選択
        trigger_items = list(self.TRIGGERS.values())
        trigger_text, ok = QInputDialog.getItem(
            self, "トリガー選択", "トリガーを選択:", trigger_items, 0, False
        )
        if not ok:
            return
        
        trigger_key = [k for k, v in self.TRIGGERS.items() if v == trigger_text][0]
        
        # アクション選択
        action_items = list(self.ACTIONS.values())
        action_text, ok = QInputDialog.getItem(
            self, "アクション選択", "アクションを選択:", action_items, 0, False
        )
        if not ok:
            return
        
        action_key = [k for k, v in self.ACTIONS.items() if v == action_text][0]
        
        # 対象入力
        target, ok = QInputDialog.getText(
            self, "対象入力", "対象（ソース名またはシーン名）:"
        )
        if not ok:
            return
        
        # 設定を追加
        new_setting = {
            "trigger": trigger_key,
            "action": action_key,
            "target": target,
            "note": ""
        }
        
        self.config.obs_control_settings.append(new_setting)
        self.add_setting_to_table(new_setting)
    
    def edit_control_setting(self):
        """制御設定を編集"""
        current_row = self.settings_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "編集する設定を選択してください。")
            return
        
        # 実装は add_control_setting と同様のダイアログを使用
        QMessageBox.information(self, "未実装", "編集機能は今後実装予定です。")
    
    def remove_control_setting(self):
        """制御設定を削除"""
        current_row = self.settings_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "警告", "削除する設定を選択してください。")
            return
        
        reply = QMessageBox.question(
            self, "確認", "選択した設定を削除しますか?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.config.obs_control_settings[current_row]
            self.settings_table.removeRow(current_row)
    
    def accept(self):
        """OKボタン押下時の処理"""
        # 監視対象ソースを保存
        monitor_source = self.monitor_source_combo.currentText()
        if monitor_source:
            self.config.monitor_source_name = monitor_source
        
        # 設定を保存
        self.config.save_config()
        
        logger.info("OBS制御設定を保存しました")
        
        # ダイアログを閉じる
        super().accept()
