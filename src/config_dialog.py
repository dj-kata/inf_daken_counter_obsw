"""
設定ダイアログ
基本設定を行うためのダイアログウィンドウ
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLineEdit, QSpinBox, QCheckBox, QPushButton,
                               QGroupBox, QFileDialog, QTabWidget, QWidget,
                               QListWidget, QLabel, QDialogButtonBox)
from PySide6.QtCore import Qt
import os

from src.config import Config
from src.logger import logger


class ConfigDialog(QDialog):
    """設定ダイアログクラス"""
    
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        
        self.config = config
        
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
        
        # 各タブを作成
        tab_widget.addTab(self.create_websocket_tab(), "OBS WebSocket")
        tab_widget.addTab(self.create_feature_tab(), "機能設定")
        
        # ボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def create_websocket_tab(self):
        """WebSocket設定タブ"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 接続設定グループ
        connection_group = QGroupBox("接続設定")
        connection_layout = QFormLayout()
        connection_group.setLayout(connection_layout)
        
        self.websocket_host_edit = QLineEdit()
        connection_layout.addRow("ホスト:", self.websocket_host_edit)
        
        self.websocket_port_spin = QSpinBox()
        self.websocket_port_spin.setRange(1, 65535)
        self.websocket_port_spin.setValue(4444)
        connection_layout.addRow("ポート:", self.websocket_port_spin)
        
        self.websocket_password_edit = QLineEdit()
        self.websocket_password_edit.setEchoMode(QLineEdit.Password)
        connection_layout.addRow("パスワード:", self.websocket_password_edit)
        
        layout.addWidget(connection_group)
        layout.addStretch()
        
        return widget
    
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
    
    def load_config_values(self):
        """設定値を読み込んでUIに反映"""
        # WebSocket設定
        self.websocket_host_edit.setText(self.config.websocket_host)
        self.websocket_port_spin.setValue(self.config.websocket_port)
        self.websocket_password_edit.setText(self.config.websocket_password)
        
        # 機能設定
        self.enable_autotweet_check.setChecked(self.config.enable_autotweet)
        self.enable_judge_check.setChecked(self.config.enable_judge)
        self.enable_folder_updates_check.setChecked(self.config.enable_folder_updates)
        self.autoload_offset_spin.setValue(self.config.autoload_offset)
        
        # 画像保存先 (Configクラスに image_save_path プロパティがある前提)
        if hasattr(self.config, 'image_save_path'):
            self.image_save_path_edit.setText(self.config.image_save_path)
        
    def accept(self):
        """OKボタン押下時の処理"""
        # UIから設定値を取得してConfigに保存
        
        # WebSocket設定
        self.config.websocket_host = self.websocket_host_edit.text()
        self.config.websocket_port = self.websocket_port_spin.value()
        self.config.websocket_password = self.websocket_password_edit.text()
        
        # 機能設定
        self.config.enable_autotweet = self.enable_autotweet_check.isChecked()
        self.config.enable_judge = self.enable_judge_check.isChecked()
        self.config.enable_folder_updates = self.enable_folder_updates_check.isChecked()
        self.config.autoload_offset = self.autoload_offset_spin.value()
        
        # 画像保存先
        self.config.image_save_path = self.image_save_path_edit.text()
        
        # 設定を保存
        self.config.save_config()
        
        logger.info("設定を保存しました")
        
        # ダイアログを閉じる
        super().accept()
