"""
スコアビューワ
全プレーログを集計して自己ベスト情報をテーブル表示
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QLineEdit, QLabel, QGroupBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QBrush
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
import traceback

from src.result import ResultDatabase, OneResult
from src.classes import play_style, difficulty, clear_lamp as LampType
from src.logger import get_logger

logger = get_logger(__name__)


class ScoreData:
    """1譜面の自己ベスト情報"""
    def __init__(self):
        self.level: str = ""
        self.title: str = ""
        self.chart: str = ""  # SPA, SPH, DPA, etc.
        self.style: play_style = play_style.sp
        self.difficulty: difficulty = difficulty.hyper
        self.lamp: int = 0  # クリアランプ
        self.best_score: int = 0
        self.score_rate: float = 0.0
        self.min_bp: int = 99999
        self.best_score_option: str = ""
        self.min_bp_option: str = ""
        self.last_play_date: str = ""
        self.notes: int = 0  # ノーツ数


class ScoreViewer(QMainWindow):
    """スコアビューワウィンドウ"""
    
    # データ更新シグナル
    data_updated = Signal()
    
    def __init__(self, result_database: ResultDatabase, parent=None):
        super().__init__(parent)
        
        self.result_database = result_database
        self.scores: Dict[str, ScoreData] = {}  # key: (title, style, difficulty)
        
        # ウィンドウ設定
        self.setWindowTitle("スコアビューワ")
        self.setGeometry(100, 100, 1400, 800)
        
        # UI初期化
        self.init_ui()
        
        # データ読み込み
        self.load_scores()
        
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
        central_widget.setLayout(main_layout)
        
        # フィルターエリア
        filter_widget = self.create_filter_widget()
        main_layout.addWidget(filter_widget)
        
        # テーブル
        self.table = QTableWidget()
        self.setup_table()
        main_layout.addWidget(self.table)
        
        # ステータスバー
        self.statusBar().showMessage("準備完了")
    
    def create_filter_widget(self) -> QWidget:
        """フィルターウィジェットを作成"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 1行目: Style選択
        style_layout = QHBoxLayout()
        style_group = QGroupBox("Play Style")
        style_group_layout = QHBoxLayout()
        style_group.setLayout(style_group_layout)
        
        self.style_checkboxes = {}
        for style in ['SP', 'DP', 'Battle']:
            cb = QCheckBox(style)
            cb.setChecked(True)
            cb.stateChanged.connect(self.on_filter_changed)
            self.style_checkboxes[style] = cb
            style_group_layout.addWidget(cb)
        
        style_layout.addWidget(style_group)
        style_layout.addStretch()
        layout.addLayout(style_layout)
        
        # 2行目: レベル選択
        level_layout = QHBoxLayout()
        level_group = QGroupBox("Level")
        level_group_layout = QHBoxLayout()
        level_group.setLayout(level_group_layout)
        
        self.level_checkboxes = {}
        for level in range(1, 13):
            cb = QCheckBox(f"☆{level}")
            cb.setChecked(True)
            cb.stateChanged.connect(self.on_filter_changed)
            self.level_checkboxes[level] = cb
            level_group_layout.addWidget(cb)
        
        level_layout.addWidget(level_group)
        layout.addLayout(level_layout)
        
        # 3行目: 検索ボックス
        search_layout = QHBoxLayout()
        search_label = QLabel("検索:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("曲名で検索...")
        self.search_box.textChanged.connect(self.on_filter_changed)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        return widget
    
    def setup_table(self):
        """テーブルの初期設定"""
        # 列定義
        columns = [
            'Lv',
            'Title',
            '譜面',
            'ランプ',
            'ベストスコア',
            'スコアレート',
            '最小BP',
            'ベストスコア時オプション',
            '最小BP時オプション',
            '最終プレー日'
        ]
        
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # ヘッダー設定
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        
        # 列幅設定
        self.table.setColumnWidth(0, 60)   # Lv
        self.table.setColumnWidth(1, 300)  # Title
        self.table.setColumnWidth(2, 80)   # 譜面
        self.table.setColumnWidth(3, 100)  # ランプ
        self.table.setColumnWidth(4, 100)  # ベストスコア
        self.table.setColumnWidth(5, 100)  # スコアレート
        self.table.setColumnWidth(6, 80)   # 最小BP
        self.table.setColumnWidth(7, 200)  # ベストスコア時オプション
        self.table.setColumnWidth(8, 200)  # 最小BP時オプション
        self.table.setColumnWidth(9, 150)  # 最終プレー日
        
        # ソート有効化
        self.table.setSortingEnabled(True)
        
        # 選択モード
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        
        # 編集不可
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
    
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
                score.notes = result.notes
                
                # レベル取得（曲データベースから取得する場合は別途実装）
                score.level = str(result.notes // 100)  # 仮実装
                
                # 譜面表記作成 (SPA, SPH, DPA, etc.)
                score.chart = self.get_chart_name(result.play_style, result.difficulty)
                
                self.scores[key] = score
            else:
                score = self.scores[key]
            
            # ベストスコア更新
            if result.score > score.best_score:
                score.best_score = result.score
                score.score_rate = result.score / (result.notes * 2) if result.notes > 0 else 0
                score.best_score_option = self.format_option(result.option)
            
            # 最小BP更新
            if result.bp < score.min_bp:
                score.min_bp = result.bp
                score.min_bp_option = self.format_option(result.option)
            
            # クリアランプ更新（最高値）
            if result.lamp > score.lamp:
                score.lamp = result.lamp
            
            # 最終プレー日更新
            play_date = datetime.fromtimestamp(result.timestamp).strftime('%Y-%m-%d %H:%M')
            if play_date > score.last_play_date:
                score.last_play_date = play_date
        
        except Exception as e:
            logger.error(f"リザルト処理エラー: {e}")
    
    def get_chart_name(self, style: play_style, diff: difficulty) -> str:
        """譜面名を取得 (SPA, SPH, DPA, etc.)"""
        style_prefix = ""
        if style == play_style.sp:
            style_prefix = "SP"
        elif style == play_style.dp:
            style_prefix = "DP"
        elif style == play_style.battle:
            return "Battle"
        
        diff_suffix = ""
        if diff == difficulty.beginner:
            diff_suffix = "B"
        elif diff == difficulty.normal:
            diff_suffix = "N"
        elif diff == difficulty.hyper:
            diff_suffix = "H"
        elif diff == difficulty.another:
            diff_suffix = "A"
        elif diff == difficulty.leggendaria:
            diff_suffix = "L"
        
        return style_prefix + diff_suffix
    
    def format_option(self, option) -> str:
        """オプションを文字列にフォーマット"""
        if option is None:
            return ""
        
        # PlayOptionオブジェクトの場合
        if hasattr(option, 'get_option_str'):
            return option.get_option_str()
        
        # 文字列の場合
        return str(option)
    
    def update_table(self):
        """テーブルを更新"""
        try:
            # ソートを一時無効化
            self.table.setSortingEnabled(False)
            
            # フィルター適用
            filtered_scores = self.apply_filters()
            
            # テーブルクリア
            self.table.setRowCount(0)
            
            # データ追加
            for score in filtered_scores:
                self.add_table_row(score)
            
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
        selected_styles = []
        if self.style_checkboxes['SP'].isChecked():
            selected_styles.append(play_style.sp)
        if self.style_checkboxes['DP'].isChecked():
            selected_styles.append(play_style.dp)
        if self.style_checkboxes['Battle'].isChecked():
            selected_styles.append(play_style.battle)
        
        # 選択されたレベル
        selected_levels = [
            str(level) for level, cb in self.level_checkboxes.items()
            if cb.isChecked()
        ]
        
        # 検索キーワード
        search_text = self.search_box.text().lower()
        
        # フィルター適用
        for score in self.scores.values():
            # Style フィルター
            if score.style not in selected_styles:
                continue
            
            # Level フィルター
            if score.level not in selected_levels:
                continue
            
            # 検索フィルター
            if search_text and search_text not in score.title.lower():
                continue
            
            filtered.append(score)
        
        return filtered
    
    def add_table_row(self, score: ScoreData):
        """テーブルに1行追加"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Lv
        item = QTableWidgetItem(f"☆{score.level}")
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 0, item)
        
        # Title
        item = QTableWidgetItem(score.title)
        self.table.setItem(row, 1, item)
        
        # 譜面
        item = QTableWidgetItem(score.chart)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 2, item)
        
        # ランプ（色付き）
        lamp_name, lamp_color = self.get_lamp_info(score.lamp)
        item = QTableWidgetItem(lamp_name)
        item.setTextAlignment(Qt.AlignCenter)
        if lamp_color:
            item.setBackground(QBrush(lamp_color))
        self.table.setItem(row, 3, item)
        
        # ベストスコア
        item = QTableWidgetItem(str(score.best_score))
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 4, item)
        
        # スコアレート
        rate_str = f"{score.score_rate * 100:.2f}%" if score.score_rate > 0 else ""
        item = QTableWidgetItem(rate_str)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 5, item)
        
        # 最小BP
        bp_str = str(score.min_bp) if score.min_bp < 99999 else ""
        item = QTableWidgetItem(bp_str)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.table.setItem(row, 6, item)
        
        # ベストスコア時オプション
        item = QTableWidgetItem(score.best_score_option)
        self.table.setItem(row, 7, item)
        
        # 最小BP時オプション
        item = QTableWidgetItem(score.min_bp_option)
        self.table.setItem(row, 8, item)
        
        # 最終プレー日
        item = QTableWidgetItem(score.last_play_date)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 9, item)
    
    def get_lamp_info(self, lamp: int) -> tuple:
        """ランプ情報を取得（名前, 色）"""
        # LampType enumを使用
        try:
            if lamp == LampType.no_play.value:
                return ("NO PLAY", QColor(200, 200, 200))
            elif lamp == LampType.failed.value:
                return ("FAILED", QColor(128, 128, 128))
            elif lamp == LampType.assist.value:
                return ("ASSIST", QColor(171, 71, 188))  # 紫
            elif lamp == LampType.easy.value:
                return ("EASY", QColor(244, 67, 54))     # 赤
            elif lamp == LampType.clear.value:
                return ("CLEAR", QColor(76, 175, 80))    # 緑
            elif lamp == LampType.hard.value:
                return ("HARD", QColor(255, 193, 7))     # 黄色
            elif lamp == LampType.ex_hard.value:
                return ("EX-HARD", QColor(255, 255, 255))  # 白
            elif lamp == LampType.fullcombo.value:
                return ("FULLCOMBO", QColor(255, 235, 59)) # 金
            else:
                return ("UNKNOWN", None)
        except:
            return ("UNKNOWN", None)
    
    @Slot()
    def on_filter_changed(self):
        """フィルター変更時"""
        self.update_table()
    
    @Slot()
    def refresh_data(self):
        """データを再読み込み（外部から呼ばれる）"""
        logger.info("スコアビューワのデータを更新します")
        self.load_scores()
        self.update_table()
    
    def closeEvent(self, event):
        """ウィンドウを閉じる時"""
        logger.info("スコアビューワを終了しました")
        event.accept()
