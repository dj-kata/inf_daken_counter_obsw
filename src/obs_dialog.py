"""
OBS制御設定ダイアログ（PySide6版・改良版）
既存のobs_websocket_manager.pyと完全互換
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QTableWidgetItem, QPushButton, QLabel, QComboBox,
                               QGroupBox, QHeaderView, QMessageBox, QFormLayout)
from PySide6.QtCore import Qt
from src.logger import get_logger

logger = get_logger(__name__)


class OBSControlDialog(QDialog):
    """OBS制御設定ダイアログ"""
    
    # 実行タイミングの定義（既存コードと同じ）
    TIMINGS = [
        ("app_start", "アプリ起動時"),
        ("app_end", "アプリ終了時"),
        ("select_start", "選曲画面開始時"),
        ("select_end", "選曲画面終了時"),
        ("play_start", "プレー画面開始時"),
        ("play_end", "プレー画面終了時"),
        ("result_start", "リザルト画面開始時"),
        ("result_end", "リザルト画面終了時"),
    ]
    
    # アクションの定義（既存コードと同じ）
    ACTIONS = [
        ("show_source", "ソースを表示"),
        ("hide_source", "ソースを非表示"),
        ("switch_scene", "シーンを切り替え"),
        ("set_monitor_source", "監視対象ソース指定"),
    ]
    
    def __init__(self, config, obs_manager, parent=None):
        super().__init__(parent)
        self.config = config
        self.obs_manager = obs_manager
        
        self.setWindowTitle("OBS制御設定")
        self.setMinimumSize(900, 600)
        
        self.init_ui()
        self.load_settings()
        
        # OBSのシーン一覧を取得
        self.update_scene_list()
    
    def init_ui(self):
        """UI初期化"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 監視対象ソース表示
        monitor_group = QGroupBox("監視対象ソース")
        monitor_layout = QHBoxLayout()
        monitor_group.setLayout(monitor_layout)
        
        self.monitor_label = QLabel("未設定")
        self.monitor_label.setStyleSheet("font-weight: bold; color: blue;")
        monitor_layout.addWidget(QLabel("現在の監視対象:"))
        monitor_layout.addWidget(self.monitor_label)
        monitor_layout.addStretch()
        
        # クリアボタンを追加
        clear_monitor_button = QPushButton("クリア")
        clear_monitor_button.clicked.connect(self.clear_monitor_source)
        monitor_layout.addWidget(clear_monitor_button)
        
        layout.addWidget(monitor_group)
        
        # 新しい制御設定を追加するグループ
        add_group = QGroupBox("新しい制御設定を追加")
        add_layout = QFormLayout()
        add_group.setLayout(add_layout)
        
        # 実行タイミング
        self.timing_combo = QComboBox()
        for timing_id, timing_name in self.TIMINGS:
            self.timing_combo.addItem(timing_name, timing_id)
        add_layout.addRow("実行タイミング:", self.timing_combo)
        
        # アクション
        self.action_combo = QComboBox()
        for action_id, action_name in self.ACTIONS:
            self.action_combo.addItem(action_name, action_id)
        self.action_combo.currentIndexChanged.connect(self.on_action_changed)
        add_layout.addRow("アクション:", self.action_combo)
        
        # 対象シーン
        self.target_scene_combo = QComboBox()
        self.target_scene_combo.currentIndexChanged.connect(self.on_target_scene_changed)
        add_layout.addRow("対象シーン:", self.target_scene_combo)
        
        # 対象ソース
        self.target_source_combo = QComboBox()
        add_layout.addRow("対象ソース:", self.target_source_combo)
        
        # 切り替え先シーン
        self.switch_scene_combo = QComboBox()
        add_layout.addRow("切り替え先シーン:", self.switch_scene_combo)
        
        # 設定追加ボタン
        add_button_layout = QHBoxLayout()
        self.add_button = QPushButton("設定を追加")
        self.add_button.clicked.connect(self.add_setting)
        add_button_layout.addStretch()
        add_button_layout.addWidget(self.add_button)
        add_layout.addRow("", add_button_layout)
        
        layout.addWidget(add_group)
        
        # 初期状態のコンボボックス有効/無効を設定
        self.on_action_changed()
        
        # 登録済み制御設定一覧
        list_group = QGroupBox("登録済み制御設定")
        list_layout = QVBoxLayout()
        list_group.setLayout(list_layout)
        
        self.settings_table = QTableWidget()
        self.settings_table.setColumnCount(4)
        self.settings_table.setHorizontalHeaderLabels([
            "実行タイミング", "アクション", "対象", ""
        ])
        
        # テーブルを編集不可に設定
        self.settings_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # 列幅を自動調整
        header = self.settings_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.settings_table.setColumnWidth(1, 150)
        self.settings_table.setColumnWidth(2, 150)
        self.settings_table.setColumnWidth(3, 100)
        
        list_layout.addWidget(self.settings_table)
        
        # 一括削除ボタン
        delete_layout = QHBoxLayout()
        delete_layout.addStretch()
        
        self.delete_selected_button = QPushButton("選択した設定を削除")
        self.delete_selected_button.clicked.connect(self.delete_selected)
        delete_layout.addWidget(self.delete_selected_button)
        
        self.delete_all_button = QPushButton("すべて削除")
        self.delete_all_button.clicked.connect(self.delete_all)
        delete_layout.addWidget(self.delete_all_button)
        
        list_layout.addLayout(delete_layout)
        
        layout.addWidget(list_group)
        
        # 更新・再接続・OK/キャンセルボタン
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("更新")
        self.refresh_button.clicked.connect(self.update_scene_list)
        button_layout.addWidget(self.refresh_button)
        
        self.reconnect_button = QPushButton("再接続")
        self.reconnect_button.clicked.connect(self.reconnect_obs)
        button_layout.addWidget(self.reconnect_button)
        
        button_layout.addStretch()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def update_scene_list(self):
        """OBSからシーン一覧を取得してコンボボックスを更新"""
        if not self.obs_manager.is_connected:
            logger.warning("OBSに接続されていません")
            return
        
        try:
            # OBSからシーン一覧を取得（List[Dict]）
            scenes_data = self.obs_manager.get_scene_list()
            
            self.target_scene_combo.clear()
            self.switch_scene_combo.clear()
            
            # scenesデータからシーン名を抽出
            for scene_dict in scenes_data:
                scene_name = scene_dict.get('sceneName', '')
                if scene_name:
                    self.target_scene_combo.addItem(scene_name)
                    self.switch_scene_combo.addItem(scene_name)
            
            logger.info(f"シーンリストを更新しました: {len(scenes_data)}件")
                
        except Exception as e:
            logger.error(f"シーン一覧取得エラー: {e}")
            QMessageBox.warning(self, "エラー", f"シーンリストの取得に失敗しました:\n{e}")
    
    def on_target_scene_changed(self):
        """対象シーンが変更されたときにソース一覧を更新"""
        scene_name = self.target_scene_combo.currentText()
        if not scene_name or not self.obs_manager.is_connected:
            return
        
        try:
            # OBSから指定シーンのソース一覧を取得（List[str]）
            sources = self.obs_manager.get_source_list(scene_name)
            
            self.target_source_combo.clear()
            for source in sources:
                self.target_source_combo.addItem(source)
            
            logger.debug(f"シーン '{scene_name}' のソースリストを更新: {len(sources)}件")
                
        except Exception as e:
            logger.error(f"ソース一覧取得エラー: {e}")
    
    def on_action_changed(self):
        """アクションが変更されたときにコンボボックスの有効/無効を切り替え"""
        action = self.action_combo.currentData()
        
        if action == "set_monitor_source":
            # 監視対象ソース設定: 実行タイミングも無効化
            self.timing_combo.setEnabled(False)
            self.target_scene_combo.setEnabled(True)
            self.target_source_combo.setEnabled(True)
            self.switch_scene_combo.setEnabled(False)
            
            # ソース一覧を更新
            self.on_target_scene_changed()
            
        elif action == "show_source" or action == "hide_source":
            # ソース表示・非表示
            self.timing_combo.setEnabled(True)
            self.target_scene_combo.setEnabled(True)
            self.target_source_combo.setEnabled(True)
            self.switch_scene_combo.setEnabled(False)
            
            # ソース一覧を更新
            self.on_target_scene_changed()
            
        elif action == "switch_scene":
            # シーン切り替え
            self.timing_combo.setEnabled(True)
            self.target_scene_combo.setEnabled(False)
            self.target_source_combo.setEnabled(False)
            self.switch_scene_combo.setEnabled(True)
    
    def add_setting(self):
        """設定を追加"""
        try:
            # 選択内容を取得
            timing_id = self.timing_combo.currentData()
            timing_name = self.timing_combo.currentText()
            action_id = self.action_combo.currentData()
            action_name = self.action_combo.currentText()
            
            # 設定データを作成（既存コードと同じ形式）
            setting = {
                "timing": timing_id,
                "action": action_id,
            }
            
            if action_id == "show_source" or action_id == "hide_source":
                # ソース表示・非表示
                target_scene = self.target_scene_combo.currentText()
                target_source = self.target_source_combo.currentText()
                
                if not target_scene or not target_source:
                    QMessageBox.warning(self, "エラー", "対象シーンと対象ソースを選択してください")
                    return
                
                setting["scene"] = target_scene
                setting["source"] = target_source
                
                target_text = f"{target_scene} / {target_source}"
                
            elif action_id == "switch_scene":
                # シーン切り替え
                switch_scene = self.switch_scene_combo.currentText()
                
                if not switch_scene:
                    QMessageBox.warning(self, "エラー", "切り替え先シーンを選択してください")
                    return
                
                setting["scene"] = switch_scene
                
                target_text = switch_scene
                
            elif action_id == "set_monitor_source":
                # 監視対象ソース設定
                target_scene = self.target_scene_combo.currentText()
                target_source = self.target_source_combo.currentText()
                
                if not target_scene or not target_source:
                    QMessageBox.warning(self, "エラー", "対象シーンと対象ソースを選択してください")
                    return
                
                # 既存の監視対象ソース設定を削除（1つのみ）
                self.config.obs_control_settings = [
                    s for s in self.config.obs_control_settings
                    if s.get("action") != "set_monitor_source"
                ]
                
                setting["scene"] = target_scene
                setting["source"] = target_source
                
                # 監視対象ソース名を更新
                self.config.monitor_source_name = target_source
                self.monitor_label.setText(target_source)
                
                # 設定を追加（ただしテーブルには追加しない）
                self.config.obs_control_settings.append(setting)
                
                logger.info(f"監視対象ソースを設定: {target_source} (シーン: {target_scene})")
                QMessageBox.information(self, "設定完了", f"監視対象ソースを '{target_source}' に設定しました")
                
                # 早期リターン（テーブルに追加しない）
                return
            
            # 設定を追加
            self.config.obs_control_settings.append(setting)
            
            # テーブルに追加（引数の順序: timing, action, target）
            self.add_table_row(timing_name, action_name, target_text, setting)
            
            logger.info(f"OBS制御設定を追加: {setting}")
            
        except Exception as e:
            logger.error(f"設定追加エラー: {e}")
            import traceback
            logger.error(traceback.format_exc())
            QMessageBox.warning(self, "エラー", f"設定の追加に失敗しました:\n{e}")
    
    def add_table_row(self, timing, action, target, setting=None):
        """テーブルに行を追加"""
        row = self.settings_table.rowCount()
        self.settings_table.insertRow(row)
        
        self.settings_table.setItem(row, 0, QTableWidgetItem(timing))
        self.settings_table.setItem(row, 1, QTableWidgetItem(action))
        self.settings_table.setItem(row, 2, QTableWidgetItem(target))
        
        # 設定データを行に関連付け
        if setting:
            self.settings_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, setting)
        
        # 削除ボタン
        delete_button = QPushButton("削除")
        delete_button.clicked.connect(lambda checked, r=row: self.delete_row(r))
        self.settings_table.setCellWidget(row, 3, delete_button)
    
    def delete_row(self, row):
        """指定行を削除"""
        # テーブルの行から設定データを取得
        item = self.settings_table.item(row, 0)
        if not item:
            return
        
        setting = item.data(Qt.ItemDataRole.UserRole)
        if not setting:
            return
        
        # config.obs_control_settingsから同じ設定を削除
        try:
            self.config.obs_control_settings.remove(setting)
            logger.info(f"OBS制御設定を削除: {setting}")
        except ValueError:
            logger.warning(f"設定が見つかりません: {setting}")
        
        # テーブルから行を削除
        self.settings_table.removeRow(row)
    
    def delete_selected(self):
        """選択された行を削除"""
        selected_rows = set()
        for item in self.settings_table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QMessageBox.information(self, "情報", "削除する設定を選択してください")
            return
        
        # 後ろから削除
        for row in sorted(selected_rows, reverse=True):
            self.delete_row(row)
    
    def delete_all(self):
        """すべての設定を削除"""
        reply = QMessageBox.question(
            self, "確認",
            "すべての設定を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config.obs_control_settings.clear()
            self.config.monitor_source_name = ""
            self.monitor_label.setText("未設定")
            self.settings_table.setRowCount(0)
            logger.info("すべてのOBS制御設定を削除しました")
    
    def load_settings(self):
        """設定を読み込んでテーブルに表示"""
        self.settings_table.setRowCount(0)
        
        # 監視対象ソースを表示
        if self.config.monitor_source_name:
            self.monitor_label.setText(self.config.monitor_source_name)
        else:
            self.monitor_label.setText("未設定")
        
        # トリガーとアクションの逆引き辞書を作成
        timing_dict = {timing_id: name for timing_id, name in self.TIMINGS}
        action_dict = {action_id: name for action_id, name in self.ACTIONS}
        
        # 各設定をテーブルに追加（監視対象ソース設定は除外）
        for setting in self.config.obs_control_settings:
            timing_id = setting.get("timing", "")
            action_id = setting.get("action", "")
            
            # 監視対象ソース設定はスキップ（画面上部のラベルのみに表示）
            if action_id == "set_monitor_source":
                continue
            
            timing_name = timing_dict.get(timing_id, timing_id)
            action_name = action_dict.get(action_id, action_id)
            
            if action_id == "switch_scene":
                target_text = setting.get("scene", "")
            else:  # show_source or hide_source
                scene = setting.get("scene", "")
                source = setting.get("source", "")
                target_text = f"{scene} / {source}"
            
            # 引数の順序: timing, action, target
            self.add_table_row(timing_name, action_name, target_text, setting)
    
    def reconnect_obs(self):
        """OBSに再接続"""
        try:
            self.obs_manager.disconnect()
            success = self.obs_manager.connect()
            if success:
                self.update_scene_list()
                QMessageBox.information(self, "成功", "OBSに再接続しました")
            else:
                QMessageBox.warning(self, "エラー", "OBSへの再接続に失敗しました")
        except Exception as e:
            logger.error(f"OBS再接続エラー: {e}")
            QMessageBox.warning(self, "エラー", f"OBSへの再接続に失敗しました:\n{e}")
    
    def clear_monitor_source(self):
        """監視対象ソースをクリア"""
        reply = QMessageBox.question(
            self, "確認",
            "監視対象ソースをクリアしますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 設定から監視対象ソース設定を削除
            self.config.obs_control_settings = [
                s for s in self.config.obs_control_settings
                if s.get("action") != "set_monitor_source"
            ]
            
            # 監視対象ソース名をクリア
            self.config.monitor_source_name = ""
            self.monitor_label.setText("未設定")
            
            logger.info("監視対象ソースをクリアしました")
            QMessageBox.information(self, "完了", "監視対象ソースをクリアしました")
    
    def accept(self):
        """OKボタン"""
        self.config.save_config()
        logger.info("OBS制御設定を保存しました")
        super().accept()
