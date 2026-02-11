"""
スコアビューワ（修正版）
全プレーログを集計して自己ベスト情報をテーブル表示
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QRadioButton, QButtonGroup, QLineEdit, QLabel, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QBrush
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
import traceback

from src.result import ResultDatabase, OneResult, DetailedResult
from src.classes import play_style, difficulty, clear_lamp, detect_mode
from src.config import Config
from src.logger import get_logger
from src.funcs import *

logger = get_logger(__name__)


class ScoreData:
    """1譜面の自己ベスト情報"""
    def __init__(self):
        self.title: str = ""
        self.style: play_style = play_style.sp
        self.difficulty: difficulty = difficulty.hyper
        self.songinfo = None  # SongInfoオブジェクト
        self.best_score_result: OneResult = None  # ベストスコア時のOneResult
        self.min_bp_result: OneResult = None  # 最小BP時のOneResult
        self.best_lamp_result: OneResult = None  # 最良ランプのOneResult
        self.last_result: OneResult = None  # 最終プレー
    
    @property
    def chart(self) -> str:
        """譜面名 (SPA, SPH, DPA, etc.)"""
        return get_chart_name(self.style, self.difficulty)
    
    @property
    def level(self) -> str:
        """レベル"""
        if self.songinfo and hasattr(self.songinfo, 'level'):
            return str(self.songinfo.level)
        return ""
    
    @property
    def dp_unofficial(self) -> str:
        """非公式難易度"""
        if self.songinfo and hasattr(self.songinfo, 'dp_unofficial'):
            return str(self.songinfo.dp_unofficial)
        return ""
    
    @property
    def lamp(self) -> clear_lamp:
        """最良ランプ"""
        if self.best_lamp_result:
            return self.best_lamp_result.lamp
        return clear_lamp.noplay
    
    @property
    def best_score(self) -> int:
        """ベストスコア"""
        if self.best_score_result:
            return self.best_score_result.score if self.best_score_result.score else 0
        return 0
    
    @property
    def score_rate(self) -> float:
        """スコアレート"""
        if self.best_score_result and self.best_score_result.notes:
            return self.best_score / (self.best_score_result.notes * 2)
        return 0.0
    
    @property
    def min_bp(self) -> int:
        """最小BP"""
        if self.min_bp_result:
            return self.min_bp_result.bp if self.min_bp_result.bp is not None else 99999
        return 99999
    
    @property
    def best_score_option(self) -> str:
        """ベストスコア時のオプション"""
        if self.best_score_result and self.best_score_result.option:
            return str(self.best_score_result.option)
        return ""
    
    @property
    def min_bp_option(self) -> str:
        """最小BP時のオプション"""
        if self.min_bp_result and self.min_bp_result.option:
            return str(self.min_bp_result.option)
        return ""
    
    @property
    def last_play_date(self) -> str:
        """最終プレー日"""
        if self.last_result:
            return datetime.fromtimestamp(self.last_result.timestamp).strftime('%Y-%m-%d %H:%M')
        return ""
    
    @property
    def notes(self) -> int:
        """ノーツ数"""
        # ベストスコア時のノーツ数を優先
        if self.best_score_result and self.best_score_result.notes:
            return self.best_score_result.notes
        if self.min_bp_result and self.min_bp_result.notes:
            return self.min_bp_result.notes
        if self.best_lamp_result and self.best_lamp_result.notes:
            return self.best_lamp_result.notes
        return 0
    
    @property
    def is_battle(self):
        """battleオプションありかどうか"""
        if self.best_score_result and self.best_score_result.option:
            return self.best_score_result.option.battle
        return None

class SortableItem(QTableWidgetItem):
    '''UserRoleに渡された数値でソートするための表アイテム。表示とソートを分ける時に使う。'''
    def __lt__(self, other):
        data1 = self.data(Qt.UserRole)
        data2 = other.data(Qt.UserRole)
        if data1 is not None and data2 is not None:
            return data1 < data2
            
        # データがない場合はデフォルトの比較（文字列比較）を行う
        return super().__lt__(other)

class ScoreViewer(QMainWindow):
    """スコアビューワウィンドウ"""
    
    # データ更新シグナル
    data_updated = Signal()
    
    def __init__(self, config: Config, result_database: ResultDatabase, parent=None):
        super().__init__(parent)
        
        self.config = config
        self.result_database = result_database
        self.scores: Dict[str, ScoreData] = {}  # key: (title, style, difficulty)
        self.current_selected_score: Optional[ScoreData] = None  # 現在選択中の譜面
        
        # ウィンドウ設定
        self.setWindowTitle("スコアビューワ")
        self.setGeometry(100, 100, 1600, 800)
        
        # UI初期化
        self.init_ui()
        
        # データ読み込み
        self.load_scores()
        
        # 設定から選択状態を復元
        self.restore_filter_state()
        
        # テーブル更新
        self.update_table()
        
        logger.info("スコアビューワを起動しました")
    
    def init_ui(self):
        """UI初期化"""
        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # メインレイアウト
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)  # 最小限のマージン
        main_layout.setSpacing(5)  # 要素間のスペースを小さく
        central_widget.setLayout(main_layout)
        
        # 上部エリア（左右分割）
        top_widget = self.create_top_widget()
        main_layout.addWidget(top_widget)
        
        # メインテーブル
        self.table = QTableWidget()
        self.setup_table()
        main_layout.addWidget(self.table)
        
        # テーブル選択イベント
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
        # ステータスバー
        self.statusBar().showMessage("準備完了")
    
    def create_top_widget(self) -> QWidget:
        """上部ウィジェットを作成（左:フィルタ、中央:プレーログ、右:ライバル欄）"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # マージンを0に
        layout.setSpacing(10)  # 左右の要素間のスペース
        widget.setLayout(layout)
        
        # 左側: フィルターエリア
        filter_widget = self.create_filter_widget()
        layout.addWidget(filter_widget, alignment=Qt.AlignTop)  # 上揃え
        
        # 中央: プレーログ表示部
        playlog_widget = self.create_playlog_widget()
        layout.addWidget(playlog_widget, alignment=Qt.AlignTop)  # 上揃え
        
        # 右側: ライバル欄
        rival_widget = self.create_rival_widget()
        layout.addWidget(rival_widget, alignment=Qt.AlignTop)  # 上揃え
        
        return widget
    
    def create_filter_widget(self) -> QWidget:
        """フィルターウィジェットを作成"""
        # QFrameで囲む
        from PySide6.QtWidgets import QFrame
        frame = QFrame()
        # 枠線なし（デフォルト）
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # マージンを0に
        layout.setSpacing(5)  # 要素間のスペースを小さく
        frame.setLayout(layout)
        
        # サイズポリシーを設定（縦方向に伸びないように）
        from PySide6.QtWidgets import QSizePolicy
        frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        # 1行目: Style選択（ラジオボタン）
        style_layout = QHBoxLayout()
        style_group = QGroupBox("Play Style")
        
        # サイズポリシーを設定（必要最小限の高さ）
        style_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        style_group_layout = QHBoxLayout()
        style_group_layout.setContentsMargins(5, 5, 5, 5)  # グループボックス内のマージン
        style_group_layout.setSpacing(5)  # 要素間のスペース
        style_group.setLayout(style_group_layout)
        
        self.style_button_group = QButtonGroup()
        self.style_buttons = {}
        
        for idx, style in enumerate(['SP', 'DP', 'Battle']):
            rb = QRadioButton(style)
            self.style_button_group.addButton(rb, idx)
            rb.toggled.connect(self.on_filter_changed)
            self.style_buttons[style] = rb
            style_group_layout.addWidget(rb)
        
        # デフォルトでSPを選択
        self.style_buttons['SP'].setChecked(True)
        
        style_layout.addWidget(style_group)
        style_layout.addStretch()
        layout.addLayout(style_layout)
        
        # 2行目: レベル選択
        level_layout = QHBoxLayout()
        level_group = QGroupBox("Level")
        
        # サイズポリシーを設定（必要最小限の高さ）
        level_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        level_group_layout = QHBoxLayout()
        level_group_layout.setContentsMargins(5, 5, 5, 5)  # グループボックス内のマージン
        level_group_layout.setSpacing(5)  # 要素間のスペース
        level_group.setLayout(level_group_layout)
        
        # ALLチェックボックス
        self.level_all_checkbox = QCheckBox("ALL")
        self.level_all_checkbox.setChecked(True)
        self.level_all_checkbox.stateChanged.connect(self.on_level_all_changed)
        level_group_layout.addWidget(self.level_all_checkbox)
        
        # 各レベルのチェックボックス
        self.level_checkboxes = {}
        for level in range(1, 13):
            cb = QCheckBox(f"☆{level}")
            cb.setChecked(True)
            cb.stateChanged.connect(self.on_level_checkbox_changed)
            self.level_checkboxes[level] = cb
            level_group_layout.addWidget(cb)
        
        level_layout.addWidget(level_group)
        layout.addLayout(level_layout)
        
        # 3行目: 検索ボックス
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)  # 要素間のスペース
        search_label = QLabel("検索:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("曲名で検索...")
        self.search_box.textChanged.connect(self.on_filter_changed)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        return frame
    
    def create_playlog_widget(self) -> QWidget:
        """プレーログ表示部ウィジェットを作成"""
        from PySide6.QtWidgets import QFrame, QPushButton, QSizePolicy
        frame = QFrame()
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        frame.setLayout(layout)
        
        # サイズポリシーを設定
        frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        # 上部：曲名と難易度 + 削除ボタン
        header_layout = QHBoxLayout()
        header_layout.setSpacing(5)
        
        # 曲名と難易度表示ラベル（必ず1行に収める）
        self.playlog_title_label = QLabel("")
        self.playlog_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.playlog_title_label.setWordWrap(False)  # 折り返し無効
        self.playlog_title_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # 横方向は無視して省略
        header_layout.addWidget(self.playlog_title_label, 1)  # ストレッチファクター1
        
        # 削除ボタン
        self.delete_playlog_button = QPushButton("削除")
        self.delete_playlog_button.setMaximumWidth(80)
        self.delete_playlog_button.clicked.connect(self.on_delete_playlog)
        header_layout.addWidget(self.delete_playlog_button)
        
        layout.addLayout(header_layout)
        
        # プレーログテーブル
        self.playlog_table = QTableWidget()
        self.setup_playlog_table()
        
        # テーブルの高さを制限
        self.playlog_table.setMaximumHeight(120)
        
        layout.addWidget(self.playlog_table)
        
        return frame
    
    def setup_playlog_table(self):
        """プレーログテーブルの初期設定"""
        # 列定義
        columns = ['プレー日時', 'ランプ', 'スコア', 'BP']
        
        self.playlog_table.setColumnCount(len(columns))
        self.playlog_table.setHorizontalHeaderLabels(columns)
        
        # ヘッダー設定
        header = self.playlog_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        # 列幅設定
        self.playlog_table.setColumnWidth(0, 150)  # プレー日時
        self.playlog_table.setColumnWidth(1, 100)  # ランプ
        self.playlog_table.setColumnWidth(2, 100)  # スコア
        self.playlog_table.setColumnWidth(3, 100)  # BP
        
        # 編集不可
        self.playlog_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 選択設定（行全体を選択）
        self.playlog_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.playlog_table.setSelectionMode(QTableWidget.SingleSelection)
    
    def create_rival_widget(self) -> QWidget:
        """ライバル欄ウィジェットを作成"""
        # QFrameで囲む
        from PySide6.QtWidgets import QFrame
        frame = QFrame()
        # 枠線なし（デフォルト）
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # マージンを0に
        layout.setSpacing(5)  # 要素間のスペースを小さく
        frame.setLayout(layout)
        
        # サイズポリシーを設定（縦方向に伸びないように）
        from PySide6.QtWidgets import QSizePolicy
        frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        
        # タイトル
        title_label = QLabel("ライバル欄")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # ライバルテーブル
        self.rival_table = QTableWidget()
        self.setup_rival_table()
        
        # テーブルの高さを制限（最大5行分程度）
        self.rival_table.setMaximumHeight(120)
        
        layout.addWidget(self.rival_table)
        
        return frame
    
    def setup_rival_table(self):
        """ライバルテーブルの初期設定"""
        # 列定義
        columns = ['player', 'lamp', 'score', 'BP', 'last played']
        
        self.rival_table.setColumnCount(len(columns))
        self.rival_table.setHorizontalHeaderLabels(columns)
        
        # ヘッダー設定
        header = self.rival_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        # 列幅設定
        self.rival_table.setColumnWidth(0, 150)  # プレーヤー名
        self.rival_table.setColumnWidth(1, 100)  # ランプ
        self.rival_table.setColumnWidth(2, 100)  # スコア
        self.rival_table.setColumnWidth(3, 100)  # ミスカウント
        self.rival_table.setColumnWidth(4, 150)  # 最終プレー日
        
        # 編集不可
        self.rival_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 選択モード
        self.rival_table.setSelectionMode(QTableWidget.NoSelection)
    
    def setup_table(self):
        """メインテーブルの初期設定"""
        # 列定義
        columns = [
            'Lv',
            '非公式Lv',
            'Title',
            'difficulty',
            'lamp',
            'BPI',
            'score',
            'rate',
            'BP',
            'Option(best score)',
            'Option(min BP)',
            'last played'
        ]
        
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # ヘッダー設定
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        
        # 列幅設定
        self.table.setColumnWidth(0, 60)   # Lv
        self.table.setColumnWidth(1, 80)   # 非公式Lv
        self.table.setColumnWidth(2, 600)  # Title
        self.table.setColumnWidth(3, 80)   # 譜面
        self.table.setColumnWidth(4, 100)  # ランプ
        self.table.setColumnWidth(5, 80)   # BPI
        self.table.setColumnWidth(6, 100)  # ベストスコア
        self.table.setColumnWidth(7, 100)  # スコアレート
        self.table.setColumnWidth(8, 80)   # 最小BP
        self.table.setColumnWidth(9, 200)  # ベストスコア時オプション
        self.table.setColumnWidth(10, 200) # 最小BP時オプション
        self.table.setColumnWidth(11, 150) # 最終プレー日
        
        # BPI列と非公式Lv列は初期状態では非表示
        self.table.setColumnHidden(1, True)  # 非公式Lv
        self.table.setColumnHidden(5, True)  # BPI
        
        # ソート有効化
        self.table.setSortingEnabled(True)
        
        # 選択モード
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        
        # 編集不可
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet("font-size: 14px;")
    
    def load_scores(self):
        """全スコアを読み込んで集計"""
        try:
            self.scores.clear()
            
            if not self.result_database or not self.result_database.results:
                logger.warning("プレーログが空です")
                return
            
            # 全リザルトを処理
            for result in self.result_database.results:
                self.process_result(result)
            
            logger.info(f"{len(self.scores)}件の譜面データを読み込みました")
        
        except Exception as e:
            logger.error(f"スコア読み込みエラー: {e}")
            logger.error(traceback.format_exc())
    
    def process_result(self, result: OneResult):
        """1つのリザルトを処理"""
        try:
            # キー生成 (title, style, difficulty)
            key = (result.title, result.play_style, result.difficulty)
            
            # スコアデータ取得または作成
            if key not in self.scores:
                score = ScoreData()
                score.title = result.title
                score.style = result.play_style
                score.difficulty = result.difficulty
                
                # songinfo取得
                score.songinfo = self.result_database.song_database.search(chart_id=result.chart_id)
                
                self.scores[key] = score
            else:
                score = self.scores[key]
            
            # ベストスコア更新
            if result.score and (not score.best_score_result or result.score > score.best_score_result.score):
                score.best_score_result = result
            
            # 最小BP更新
            current_bp = result.bp if result.bp is not None else 99999
            best_bp = score.min_bp_result.bp if score.min_bp_result and score.min_bp_result.bp is not None else 99999
            if current_bp < best_bp:
                score.min_bp_result = result
            
            # クリアランプ更新（最高値）
            if result.lamp and (not score.best_lamp_result or result.lamp.value > score.best_lamp_result.lamp.value):
                score.best_lamp_result = result
            
            # 最終プレー日更新
            if not score.last_result or result.timestamp > score.last_result.timestamp:
                score.last_result = result
        
        except Exception as e:
            logger.error(f"リザルト処理エラー: {e}")
            logger.error(traceback.format_exc())

    
    def restore_filter_state(self):
        """設定から選択状態を復元"""
        try:
            # 全てのシグナルを一時的にブロック
            for button in self.style_buttons.values():
                button.blockSignals(True)
            for cb in self.level_checkboxes.values():
                cb.blockSignals(True)
            if hasattr(self, 'level_all_checkbox'):
                self.level_all_checkbox.blockSignals(True)
            
            # Play Style復元
            style = self.config.score_viewer_style
            if style in self.style_buttons:
                self.style_buttons[style].setChecked(True)
            
            # Level復元
            levels = self.config.score_viewer_levels
            
            # まず全てのチェックを外す
            for cb in self.level_checkboxes.values():
                cb.setChecked(False)
            
            # 保存されているレベルをチェック
            for level in levels:
                if level in self.level_checkboxes:
                    self.level_checkboxes[level].setChecked(True)
            
            # ALLチェックボックスの状態を更新
            if hasattr(self, 'level_all_checkbox'):
                all_checked = all(cb.isChecked() for cb in self.level_checkboxes.values())
                self.level_all_checkbox.setChecked(all_checked)
            
            # シグナルのブロックを解除
            for button in self.style_buttons.values():
                button.blockSignals(False)
            for cb in self.level_checkboxes.values():
                cb.blockSignals(False)
            if hasattr(self, 'level_all_checkbox'):
                self.level_all_checkbox.blockSignals(False)
        
        except Exception as e:
            logger.error(f"フィルター状態復元エラー: {e}")
    
    def save_filter_state(self):
        """選択状態を設定に保存"""
        try:
            # 属性が存在するかチェック
            if not hasattr(self, 'style_buttons') or not hasattr(self, 'level_checkboxes'):
                return
            
            # Play Style保存
            for style, button in self.style_buttons.items():
                if button.isChecked():
                    self.config.score_viewer_style = style
                    break
            
            # Level保存
            selected_levels = [
                level for level, cb in self.level_checkboxes.items()
                if cb.isChecked()
            ]
            self.config.score_viewer_levels = selected_levels
            
            # 設定を保存
            self.config.save_config()
        
        except Exception as e:
            logger.error(f"フィルター状態保存エラー: {e}")
    
    def update_table(self):
        """テーブルを更新"""
        try:
            # ソートを一時無効化
            self.table.setSortingEnabled(False)
            
            # 選択されているレベルをチェック（11か12が含まれているか）
            selected_levels = [
                level for level, cb in self.level_checkboxes.items()
                if cb.isChecked()
            ]
            show_bpi = 11 in selected_levels or 12 in selected_levels
            
            # 選択されているスタイルをチェック（DPか）
            selected_style = None
            is_battle = None
            for style, button in self.style_buttons.items():
                if button.isChecked():
                    if style == 'SP':
                        selected_style = play_style.sp
                    elif style == 'DP':
                        selected_style = play_style.dp
                    elif style == 'Battle':
                        selected_style = play_style.dp
                        is_battle = True
                    break
            
            # 非公式Lv列の表示判定（DPかつBattleでない場合のみ表示）
            show_unofficial = (selected_style == play_style.dp and not is_battle)
            
            # BPI列と非公式Lv列の表示/非表示を切り替え
            self.table.setColumnHidden(1, not show_unofficial)  # 非公式Lv
            self.table.setColumnHidden(5, not show_bpi)  # BPI
            
            # フィルター適用
            filtered_scores = self.apply_filters()
            
            # テーブルクリア
            self.table.setRowCount(0)
            
            # データ追加
            for score in filtered_scores:
                self.add_table_row(score, show_bpi)
            
            # ソート再有効化
            self.table.setSortingEnabled(True)
            
            # ステータス更新
            self.statusBar().showMessage(f"{len(filtered_scores)}件の譜面を表示中")
        
        except Exception as e:
            logger.error(f"テーブル更新エラー: {e}")
            logger.error(traceback.format_exc())
    
    def apply_filters(self) -> List[ScoreData]:
        """フィルターを適用してスコアリストを返す"""
        filtered = []
        
        # 選択されたstyle
        selected_style = None
        is_battle      = None
        for style, button in self.style_buttons.items():
            if button.isChecked():
                if style == 'SP':
                    selected_style = play_style.sp
                elif style == 'DP':
                    selected_style = play_style.dp
                elif style == 'Battle':
                    selected_style = play_style.dp
                    is_battle = True
                break
        
        # 選択されたレベル
        selected_levels = [
            str(level) for level, cb in self.level_checkboxes.items()
            if cb.isChecked()
        ]
        
        # 検索キーワード（大文字小文字を区別しない）
        search_text = self.search_box.text().strip().lower()
        
        # フィルター適用
        for score in self.scores.values():
            # Style フィルター
            if selected_style and score.style != selected_style:
                continue
            
            # Level フィルター
            if score.level not in selected_levels:
                continue

            # Battleフィルタ
            if is_battle and not score.is_battle:
                continue
            
            # 検索フィルター（大文字小文字を区別せず部分一致）
            if len(search_text) > 0:
                if search_text not in score.title.lower():
                    continue
            
            filtered.append(score)
        
        return filtered
    
    def add_table_row(self, score: ScoreData, show_bpi: bool = False):
        """テーブルに1行追加"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Lv（常に公式レベルを表示）
        item = SortableItem(f"☆{score.level}")
        item.setData(Qt.UserRole, int(score.level))
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 0, item)
        
        # 非公式Lv（DPかつbattle=Falseの場合のみ値を設定）
        unofficial_str = ""
        unofficial_value = None
        if score.style == play_style.dp and not score.is_battle:
            if type(score.songinfo.dp_unofficial) == float:
                unofficial_str = str(score.songinfo.dp_unofficial)
                unofficial_value = score.songinfo.dp_unofficial
        
        item = SortableItem(unofficial_str)
        if unofficial_value is not None:
            item.setData(Qt.UserRole, unofficial_value)
        else:
            item.setData(Qt.UserRole, float(score.level)-0.001)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 1, item)
        
        # Title
        item = QTableWidgetItem(score.title)
        item.setData(Qt.UserRole, score) # 特殊なソートを行わないtitle列にscoreの実体を入れておく
        self.table.setItem(row, 2, item)
        
        # 譜面
        chart_name, chart_color = self.get_chart_info(score.chart)
        item = SortableItem(score.chart)
        item.setData(Qt.UserRole, score.difficulty.value)
        item.setTextAlignment(Qt.AlignCenter)
        if chart_color:
            item.setBackground(QBrush(chart_color))
        self.table.setItem(row, 3, item)
        
        # ランプ（色付き）
        lamp_name, lamp_color = self.get_lamp_info(score.lamp)
        item = SortableItem(lamp_name)
        item.setTextAlignment(Qt.AlignCenter)
        if lamp_color:
            item.setBackground(QBrush(lamp_color))
        item.setData(Qt.UserRole, score.lamp.value)
        self.table.setItem(row, 4, item)
        
        # BPI（11か12レベルの場合のみ計算）
        bpi_str = ""
        bpi_value = None
        if show_bpi:
            try:
                if score.best_score_result and score.songinfo:
                    detailed = DetailedResult(score.songinfo, score.best_score_result)
                    bpi = detailed.get_bpi()
                    if bpi is not None:
                        bpi_str = f"{bpi:.2f}"
                        bpi_value = bpi
            except Exception as e:
                logger.debug(f"BPI計算エラー ({score.title}): {e}")
        
        item = SortableItem(bpi_str)
        if bpi_value is not None:
            item.setData(Qt.UserRole, bpi_value)
        else:
            item.setData(Qt.UserRole, -16)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 5, item)
        
        # ベストスコア
        item = QTableWidgetItem(str(score.best_score))
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 6, item)
        
        # スコアレート
        rate_str = f"{score.score_rate * 100:.2f}%" if score.score_rate > 0 else ""
        item = QTableWidgetItem(rate_str)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 7, item)
        
        # 最小BP
        bp_str = str(score.min_bp) if score.min_bp < 99999 else ""
        item = QTableWidgetItem(bp_str)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 8, item)
        
        # ベストスコア時オプション
        item = QTableWidgetItem(score.best_score_option)
        self.table.setItem(row, 9, item)
        
        # 最小BP時オプション
        item = QTableWidgetItem(score.min_bp_option)
        self.table.setItem(row, 10, item)
        
        # 最終プレー日
        item = QTableWidgetItem(score.last_play_date)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 11, item)

    def get_chart_info(self, diff:str) -> tuple:
        '''譜面情報を送信(名前,色)'''
        try:
            if diff[-1] == 'B':
                return (diff, QColor(150, 255, 150))
            elif diff[-1] == 'N':
                return (diff, QColor(150, 150, 255))
            elif diff[-1] == 'H':
                return (diff, QColor(255, 255, 155))
            elif diff[-1] == 'A':
                return (diff, QColor(255, 150, 150))
            elif diff[-1] == 'L':
                return (diff, QColor(255, 150, 255))
            else:
                return ("", QColor(255,255,255))
        except:
            return ("", QColor(255,255,255))

    def get_lamp_info(self, lamp: clear_lamp) -> tuple:
        """ランプ情報を取得（名前, 色）"""
        # clear_lamp enumを使用
        try:
            if lamp == clear_lamp.noplay:
                return ("NO PLAY", QColor(200, 200, 200))
            elif lamp == clear_lamp.failed:
                return ("FAILED", QColor(128, 128, 128))
            elif lamp == clear_lamp.assist:
                return ("ASSIST", QColor(255, 150, 255))  # 紫
            elif lamp == clear_lamp.easy:
                return ("EASY", QColor(150, 255, 150))     # 赤
            elif lamp == clear_lamp.clear:
                return ("CLEAR", QColor(76, 175, 255))    # 緑
            elif lamp == clear_lamp.hard:
                return ("HARD", QColor(255, 70, 70))     # 黄色
            elif lamp == clear_lamp.exh:
                return ("EXH-CLEAR", QColor(255, 255, 120))  # 白
            elif lamp == clear_lamp.fc:
                return ("FULLCOMBO", QColor(255, 170, 100)) 
            else:
                return ("NO PLAY", QColor(200, 200, 200))
        except:
            return ("NO PLAY", QColor(200, 200, 200))
    
    def update_rival_table(self, score: ScoreData):
        """ライバル欄を更新（自己ベストを表示）"""
        try:
            self.rival_table.setRowCount(0)
            
            if not score:
                return
            
            # 1行追加（自己ベスト）
            row = 0
            self.rival_table.insertRow(row)
            
            # プレーヤー名（自分）
            item = QTableWidgetItem("(MY BEST)")
            self.rival_table.setItem(row, 0, item)
            
            # ランプ（色付き）
            if score.lamp:
                lamp_name, lamp_color = self.get_lamp_info(score.lamp)
                item = QTableWidgetItem(lamp_name)
                item.setTextAlignment(Qt.AlignCenter)
                if lamp_color:
                    item.setBackground(QBrush(lamp_color))
                self.rival_table.setItem(row, 1, item)
            
            # スコア
            item = QTableWidgetItem(str(score.best_score))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.rival_table.setItem(row, 2, item)
            
            # ミスカウント
            bp_str = str(score.min_bp) if score.min_bp < 99999 else ""
            item = QTableWidgetItem(bp_str)
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.rival_table.setItem(row, 3, item)
            
            # 最終プレー日
            item = QTableWidgetItem(score.last_play_date)
            item.setTextAlignment(Qt.AlignCenter)
            self.rival_table.setItem(row, 4, item)
        
        except Exception as e:
            logger.error(f"ライバル欄更新エラー: {e}")
    
    def update_playlog_table(self, score: ScoreData):
        """プレーログ欄を更新（選択中の曲のプレーログを表示）"""
        try:
            self.playlog_table.setRowCount(0)
            
            if not score:
                # 曲が選択されていない場合は曲名ラベルをクリア
                if hasattr(self, 'playlog_title_label'):
                    self.playlog_title_label.setText("")
                return
            
            # 曲名と難易度を表示
            if hasattr(self, 'playlog_title_label'):
                chart_info = f"{score.title} ({score.chart})"
                if score.level:
                    chart_info += f" ☆{score.level}"
                self.playlog_title_label.setText(chart_info)
            
            # 選択中の曲のプレーログをフィルタ（全てのdetect_modeを対象）
            playlogs = []
            for result in self.result_database.results:
                if (result.title == score.title and 
                    result.play_style == score.style and 
                    result.difficulty == score.difficulty):
                    playlogs.append(result)
            
            # タイムスタンプで降順ソート（新しい順）
            playlogs.sort(key=lambda x: x.timestamp, reverse=True)
            
            # テーブルに表示
            for row, log in enumerate(playlogs):
                self.playlog_table.insertRow(row)
                
                # プレー日時
                dt = datetime.fromtimestamp(log.timestamp)
                date_str = dt.strftime('%Y/%m/%d %H:%M')
                item = QTableWidgetItem(date_str)
                item.setTextAlignment(Qt.AlignCenter)
                # OneResultオブジェクトを保持（削除時に使用）
                item.setData(Qt.UserRole, log)
                self.playlog_table.setItem(row, 0, item)
                
                # ランプ（色付き）
                lamp_name, lamp_color = self.get_lamp_info(log.lamp)
                item = QTableWidgetItem(lamp_name)
                item.setTextAlignment(Qt.AlignCenter)
                if lamp_color:
                    item.setBackground(QBrush(lamp_color))
                self.playlog_table.setItem(row, 1, item)
                
                # スコア
                score_str = str(log.score) if log.score else ""
                item = QTableWidgetItem(score_str)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.playlog_table.setItem(row, 2, item)
                
                # BP
                bp_str = str(log.bp) if log.bp is not None else ""
                item = QTableWidgetItem(bp_str)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.playlog_table.setItem(row, 3, item)
        
        except Exception as e:
            logger.error(f"プレーログ欄更新エラー: {e}")
            logger.error(traceback.format_exc())
    
    @Slot()
    def on_delete_playlog(self):
        """プレーログ削除ボタンがクリックされた時"""
        try:
            # 選択されている行を取得
            selected_items = self.playlog_table.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "警告", "削除するプレーログを選択してください。")
                return
            
            # 選択された行からOneResultオブジェクトを取得
            row = selected_items[0].row()
            item = self.playlog_table.item(row, 0)
            if not item:
                return
            
            result_to_delete = item.data(Qt.UserRole)
            if not result_to_delete:
                return
            
            # 確認ダイアログ
            dt = datetime.fromtimestamp(result_to_delete.timestamp)
            date_str = dt.strftime('%Y/%m/%d %H:%M')
            
            reply = QMessageBox.question(
                self,
                "確認",
                f"以下のプレーログを削除しますか?\n\n"
                f"曲名: {result_to_delete.title}\n"
                f"譜面: {get_chart_name(result_to_delete.play_style, result_to_delete.difficulty)}\n"
                f"日時: {date_str}\n"
                f"スコア: {result_to_delete.score}\n"
                f"BP: {result_to_delete.bp}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # プレーログを削除
                if result_to_delete in self.result_database.results:
                    self.result_database.results.remove(result_to_delete)
                    
                    # データベースを保存
                    self.result_database.save()
                    
                    # スコアデータを再読み込み
                    self.load_scores()
                    
                    # テーブル更新
                    self.update_table()
                    
                    # 現在選択中の譜面があればプレーログとライバル欄も更新
                    if self.current_selected_score:
                        key = (
                            self.current_selected_score.title,
                            self.current_selected_score.style,
                            self.current_selected_score.difficulty
                        )
                        if key in self.scores:
                            self.current_selected_score = self.scores[key]
                            self.update_playlog_table(self.current_selected_score)
                            self.update_rival_table(self.current_selected_score)
                    
                    QMessageBox.information(self, "完了", "プレーログを削除しました。")
                    logger.info(f"プレーログを削除: {result_to_delete.title} {date_str}")
                else:
                    QMessageBox.warning(self, "エラー", "プレーログの削除に失敗しました。")
        
        except Exception as e:
            logger.error(f"プレーログ削除エラー: {e}")
            logger.error(traceback.format_exc())
            QMessageBox.critical(self, "エラー", f"プレーログの削除中にエラーが発生しました:\n{e}")
    
    @Slot()
    def on_table_selection_changed(self):
        """テーブルの選択が変更された時"""
        try:
            selected_items = self.table.selectedItems()
            if not selected_items:
                return
            
            # Title列（列2）からScoreDataを取得
            row = selected_items[0].row()
            item = self.table.item(row, 2)
            if item:
                score = item.data(Qt.UserRole)
                if score:
                    self.current_selected_score = score
                    self.update_playlog_table(score)
                    self.update_rival_table(score)
        
        except Exception as e:
            logger.error(f"選択変更エラー: {e}")
    
    @Slot()
    def on_filter_changed(self, arg=None):
        """フィルター変更時
        
        Args:
            arg: ラジオボタンのtoggled(bool)または検索ボックスのtextChanged(str)からの引数
        """
        # テーブルが初期化されていない場合は何もしない
        if not hasattr(self, 'table'):
            return
        
        # ラジオボタンのtoggledシグナルから呼ばれた場合（argがbool）
        # checked=Falseなら何もしない（ボタンが外れた時ではなく、新しいボタンがチェックされた時だけ処理）
        if isinstance(arg, bool) and not arg:
            return
        
        self.update_table()
        self.save_filter_state()
    
    @Slot()
    def on_level_all_changed(self):
        """ALLチェックボックス変更時"""
        # 属性が存在するかチェック
        if not hasattr(self, 'level_all_checkbox') or not hasattr(self, 'level_checkboxes'):
            return
        
        # ALLチェックボックスの現在の状態を取得
        checked = self.level_all_checkbox.isChecked()
        
        # 全てのレベルチェックボックスを変更（シグナルをブロックして一括変更）
        for cb in self.level_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        
        # フィルター更新を明示的に呼び出す
        self.on_filter_changed()
    
    @Slot()
    def on_level_checkbox_changed(self):
        """レベルチェックボックス変更時"""
        # 属性が存在するかチェック
        if not hasattr(self, 'level_checkboxes') or not hasattr(self, 'level_all_checkbox'):
            return
        
        # ALLチェックボックスの状態を更新
        self.update_level_all_checkbox()
        
        # フィルター更新
        self.on_filter_changed()
    
    def update_level_all_checkbox(self):
        """ALLチェックボックスの状態を更新"""
        # 属性が存在するかチェック
        if not hasattr(self, 'level_checkboxes') or not hasattr(self, 'level_all_checkbox'):
            return
        
        all_checked = all(cb.isChecked() for cb in self.level_checkboxes.values())
        
        # stateChangedシグナルを一時的にブロック
        self.level_all_checkbox.blockSignals(True)
        self.level_all_checkbox.setChecked(all_checked)
        self.level_all_checkbox.blockSignals(False)
    
    @Slot()
    def refresh_data(self):
        """データを再読み込み（外部から呼ばれる）"""
        logger.info("スコアビューワのデータを更新します")
        self.load_scores()
        self.update_table()
        
        # 現在選択中の譜面があればプレーログとライバル欄も更新
        if self.current_selected_score:
            # 最新のスコアデータを取得
            key = (
                self.current_selected_score.title,
                self.current_selected_score.style,
                self.current_selected_score.difficulty
            )
            if key in self.scores:
                self.current_selected_score = self.scores[key]
                self.update_playlog_table(self.current_selected_score)
                self.update_rival_table(self.current_selected_score)
    
    def closeEvent(self, event):
        """ウィンドウを閉じる時"""
        # 設定を保存
        self.save_filter_state()
        logger.info("スコアビューワを終了しました")
        event.accept()

if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    class MyWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("検証用ウィンドウ")
            self.resize(600, 400)
            # ここにテーブル作成などのロジックがある想定

    window = MyWindow()
    rdb = ResultDatabase()
    app.setQuitOnLastWindowClosed(True)
    config = Config()
    sv = ScoreViewer(config, rdb, window)
    sv.show()
    sys.exit(app.exec())