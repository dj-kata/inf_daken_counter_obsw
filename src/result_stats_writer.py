from PIL import Image, ImageDraw, ImageFont
import os
from src.classes import *
from src.funcs import *

# 難易度ごとの色マッピング: (fill, glow_color)
_DIFFICULTY_COLORS = {
    difficulty.another:     ((250, 100, 100), (150, 0, 0)),
    difficulty.leggendaria: ((250, 100, 250), (80, 0, 80)),
    difficulty.hyper:       ((250, 250, 100), (80, 80, 0)),
    difficulty.normal:      ((100, 100, 250), (0, 0, 80)),
    difficulty.beginner:    ((100, 250, 100), (0, 80, 0)),
}

# クリアランプごとの表示: (display_text, fill, glow_color)
_LAMP_DISPLAY = {
    clear_lamp.assist: ('A-CLEAR',   (255, 155, 250), (80, 0, 80)),
    clear_lamp.easy:   ('E-CLEAR',   (100, 255, 100), (80, 150, 80)),
    clear_lamp.clear:  (None,        (100, 190, 255), (80, 100, 150)),  # None = lamp.name.upper()を使用
    clear_lamp.hard:   ('H-CLEAR',   (255, 50, 100),  (150, 30, 50)),
    clear_lamp.exh:    ('EXH-CLEAR', (255, 255, 100), (150, 150, 50)),
    clear_lamp.fc:     ('F-COMBO',   (255, 170, 250), (200, 50, 150)),
}

_ARENA_RANK_COLORS = {
    'A1': (255, 213, 79),
    'A2': (100, 216, 255),
    'A3': (105, 240, 174),
    'A4': (255, 183, 77),
    'A5': (255, 138, 128),
}

class ResultStatsWriter:
    """リザルト画像に統計情報を埋め込むためのクラス"""
    
    def __init__(self, font_dir="fonts"):
        """
        Args:
            font_dir: フォントファイルを保存するディレクトリ（未使用）
        """
        # フォント読み込み
        self.title_font = self._load_font(size=55, bold=True)
        self.main_font = self._load_font(size=34, bold=True)
        self.sub_font = self._load_font(size=28)
        self.label_font = self._load_font(size=21, bold=True)
        self.small_font = self._load_font(size=22)
    
    def _load_font(self, size=28, bold=False):
        """システムフォントを読み込む"""
        # Windowsフォント
        windows_fonts = [
            "C:/Windows/Fonts/meiryob.ttc" if bold else "C:/Windows/Fonts/meiryo.ttc",  # メイリオ
            "C:/Windows/Fonts/YuGothB.ttc" if bold else "C:/Windows/Fonts/YuGothM.ttc",  # 游ゴシック
            "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
        ]
        
        for font_path in windows_fonts:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except:
                    pass
        
        return ImageFont.load_default()
    
    def write_statistics(
        self,
        img,
        title,
        level,
        play_style:play_style,
        difficulty:difficulty,
        ex_score,
        bp,
        max_notes,
        lamp:clear_lamp,
        bpi=None,
        bpi_label='BPI',
        bpi_arena_average_text=None,
        bpi_arena_averages=None,
        sp12_clear:clear_lamp=None,
        sp12_hard:clear_lamp=None,
        songinfo=None,
        enable_katate_difficulty_display=False,
        position=(600, 405),  # (x, y) 座標で指定
        box_width=790,     # ボックス幅（Noneで画像幅）
        box_height=430,
        box_alpha=230       # 背景の透明度 (0-255)
    ):
        """
        リザルト画像に統計情報を書き込む。
        
        Args:
            position: 描画位置 (x, y) のタプル。"top"/"bottom"も可
            box_width: ボックス幅（Noneで画像幅いっぱい）
            box_alpha: 背景の透明度 (0=完全透明, 255=不透明)
        """
        # 画像を開く
        max_score = max_notes * 2
        
        # RGBA変換（透明度サポート）
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # 半透明レイヤーを作成
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # 位置を解決（文字列または座標）
        if position == "top":
            x, y = 40, 10
        elif position == "bottom":
            x, y = 40, img.height - 220
        else:
            x, y = position
        
        # ボックス幅のデフォルト値
        if box_width is None:
            box_width = img.width - x * 2
        
        padding_x = 28
        content_x = x
        content_w = box_width - padding_x * 2
        panel_left = x - padding_x
        panel_top = y - 12
        panel_right = panel_left + box_width
        panel_bottom = y + box_height

        # 背景ボックスを描画（半透明、透明度を指定可能）
        self._draw_rounded_rectangle(
            draw, 
            (panel_left, panel_top, panel_right, panel_bottom),
            radius=8,
            fill=(0, 0, 0, box_alpha)
        )

        # ゲーム画面側の直線的なUIに寄せた細いアクセント。
        draw.rectangle((panel_left + 8, panel_top + 8, panel_right - 8, panel_top + 11), fill=(60, 220, 255, 180))
        draw.rectangle((panel_left + 8, panel_bottom - 11, panel_right - 8, panel_bottom - 8), fill=(255, 235, 80, 150))

        y += 18
        title_text = self._truncate_text(draw, title, self.title_font, content_w)
        self._draw_text_with_glow(draw, (content_x, y), title_text, self.title_font,
                                  fill=(255, 255, 255), glow_color=(30, 30, 30))
        y += 76

        chart_text = get_chart_name(play_style, difficulty)
        level_text = self._format_level_text(level, play_style, songinfo, enable_katate_difficulty_display)
        diff_fill, diff_glow = _DIFFICULTY_COLORS.get(difficulty, ((255, 255, 255), (50, 50, 50)))
        self._draw_text_with_glow(draw, (content_x, y), chart_text, self.sub_font,
                                  fill=diff_fill, glow_color=diff_glow)
        self._draw_text_with_glow(draw, (content_x + 92, y), level_text, self.sub_font,
                                  fill=(120, 245, 255), glow_color=(0, 100, 120))

        extra_level_text = self._format_extra_level_text(play_style, songinfo, sp12_clear, sp12_hard)
        if extra_level_text:
            extra = self._truncate_text(draw, extra_level_text, self.small_font, content_w - 215)
            self._draw_text_with_glow(draw, (content_x + 215, y + 4), extra, self.small_font,
                                      fill=(235, 245, 255), glow_color=(35, 35, 45))
        y += 45

        if lamp in _LAMP_DISPLAY:
            lamp_text, lamp_fill, lamp_glow = _LAMP_DISPLAY[lamp]
            if lamp_text is None:
                lamp_text = lamp.name.upper()
            lamp_text = self._truncate_text(draw, lamp_text, self.main_font, content_w)
            self._draw_text_with_glow(draw, (content_x, y), lamp_text, self.main_font,
                                      fill=lamp_fill, glow_color=lamp_glow)
        y += 48

        rate = ex_score / max_score*100
        col_gap = 28
        col_w = (content_w - col_gap) // 2
        row_h = 50
        self._draw_metric(draw, content_x, y, col_w, "SCORE", f"{ex_score} / {max_score}", (115, 255, 135))
        self._draw_metric(draw, content_x + col_w + col_gap, y, col_w, "BP", f"{bp} / {max_notes}", (115, 255, 135))
        y += row_h

        bpi_text = f"{bpi:.2f}" if bpi is not None else "--"
        self._draw_metric(draw, content_x, y, col_w, "RATE", f"{rate:.2f}%", (255, 245, 90))
        self._draw_metric(draw, content_x + col_w + col_gap, y, col_w, bpi_label, bpi_text, (255, 245, 90))
        y += row_h + 3

        arena_text = self._format_arena_average_text(bpi_arena_averages, bpi_arena_average_text)
        if arena_text:
            self._draw_arena_average(draw, content_x, y, content_w, bpi_arena_averages, arena_text)
            y += 40

        ereter_items = self._format_ereter_items(play_style, songinfo, lamp)
        if ereter_items:
            self._draw_ereter_items(draw, content_x, y, content_w, ereter_items)
        
        # オーバーレイを合成
        img = Image.alpha_composite(img, overlay)
        
        # RGB変換して保存
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        return img

    def _format_level_text(self, level, play_style_value, songinfo, enable_katate):
        level_text = f"☆{level}"
        if not (enable_katate and play_style_value == play_style.sp and songinfo):
            return level_text
        try:
            lv = int(getattr(songinfo, "level", level) or level)
        except (TypeError, ValueError):
            lv = None
        band = None
        if lv == 12:
            band = getattr(songinfo, "katate_12", None)
        elif lv == 11:
            band = getattr(songinfo, "katate_11", None)
        mark = self._katate_mark(band)
        return f"☆{level}-{mark}" if mark else level_text

    def _katate_mark(self, band):
        marks = ["", "①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
        try:
            value = int(band)
        except (TypeError, ValueError):
            return ""
        return marks[value] if 1 <= value < len(marks) else ""

    def _format_extra_level_text(self, play_style_value, songinfo, sp12_clear, sp12_hard):
        if play_style_value == play_style.dp and songinfo:
            dp_unofficial = getattr(songinfo, "dp_unofficial", None)
            if dp_unofficial:
                return f"({dp_unofficial})"
        if sp12_clear or sp12_hard:
            return f"({sp12_clear or '?'}/{sp12_hard or '?'})"
        if songinfo:
            sp11_clear = getattr(songinfo, "sp11_clear", None)
            sp11_hard = getattr(songinfo, "sp11_hard", None)
            if sp11_clear or sp11_hard:
                return f"({sp11_clear or '?'}/{sp11_hard or '?'})"
        return ""

    def _format_arena_average_text(self, averages, fallback_text):
        if averages:
            return "   ".join(f"{avg.rank} {avg.avg_ex_score}" for avg in averages)
        if fallback_text:
            return fallback_text.replace(" avg ", " ")
        return ""

    def _format_ereter_items(self, play_style_value, songinfo, lamp):
        if play_style_value != play_style.dp or not songinfo:
            return []
        items = [
            ("EC", getattr(songinfo, "dp_ereter_easy", None), clear_lamp.easy),
            ("HC", getattr(songinfo, "dp_ereter_hard", None), clear_lamp.hard),
            ("EXH", getattr(songinfo, "dp_ereter_exh", None), clear_lamp.exh),
        ]
        return [(label, str(value), lamp.value >= target.value) for label, value, target in items if value]

    def _draw_metric(self, draw, x, y, width, label, value, value_fill, compact=False):
        label_bbox = draw.textbbox((0, 0), label, font=self.label_font)
        measured_label_w = label_bbox[2] - label_bbox[0]
        label_w = max(122 if compact else 92, measured_label_w + 18)
        draw.text((x, y + 6), label, font=self.label_font, fill=(170, 190, 205))
        value_x = x + label_w
        value_text = self._truncate_text(draw, value, self.main_font if not compact else self.sub_font, width - label_w)
        self._draw_text_with_glow(draw, (value_x, y), value_text, self.main_font if not compact else self.sub_font,
                                  fill=value_fill, glow_color=(25, 45, 25))

    def _draw_arena_average(self, draw, x, y, width, averages, fallback_text):
        label = "ARENA AVG"
        label_bbox = draw.textbbox((0, 0), label, font=self.label_font)
        label_w = max(122, label_bbox[2] - label_bbox[0] + 18)
        draw.text((x, y + 6), label, font=self.label_font, fill=(170, 190, 205))

        value_x = x + label_w
        max_x = x + width
        if not averages:
            value_text = self._truncate_text(draw, fallback_text, self.sub_font, max_x - value_x)
            self._draw_text_with_glow(draw, (value_x, y), value_text, self.sub_font,
                                      fill=(255, 245, 90), glow_color=(25, 45, 25))
            return

        cursor_x = value_x
        for index, avg in enumerate(averages):
            if index:
                cursor_x += 20
            rank = str(avg.rank)
            score = str(avg.avg_ex_score)
            rank_fill = _ARENA_RANK_COLORS.get(rank, (255, 245, 90))
            rank_bbox = draw.textbbox((0, 0), rank, font=self.sub_font)
            score_bbox = draw.textbbox((0, 0), f" {score}", font=self.sub_font)
            item_w = (rank_bbox[2] - rank_bbox[0]) + (score_bbox[2] - score_bbox[0])
            if cursor_x + item_w > max_x:
                break
            self._draw_text_with_glow(draw, (cursor_x, y), rank, self.sub_font,
                                      fill=rank_fill, glow_color=(35, 35, 45))
            cursor_x += rank_bbox[2] - rank_bbox[0]
            self._draw_text_with_glow(draw, (cursor_x, y), f" {score}", self.sub_font,
                                      fill=(255, 245, 90), glow_color=(25, 45, 25))
            cursor_x += score_bbox[2] - score_bbox[0]

    def _draw_ereter_items(self, draw, x, y, width, items):
        draw.text((x, y + 8), "ERETER", font=self.label_font, fill=(170, 190, 205))
        item_w = (width - 118) // max(1, len(items))
        item_x = x + 118
        for label, value, achieved in items:
            fill = (115, 255, 155) if achieved else (190, 200, 210)
            prefix = "✓ " if achieved else "- "
            text = self._truncate_text(draw, f"{prefix}{label} {value}", self.small_font, item_w - 4)
            self._draw_text_with_glow(draw, (item_x, y + 4), text, self.small_font,
                                      fill=fill, glow_color=(20, 45, 25) if achieved else (35, 35, 45))
            item_x += item_w

    def _truncate_title_with_difficulty(self, draw, title, difficulty_part, font, max_width):
        """
        曲名を省略するが、難易度部分は必ず表示する
        
        Args:
            draw: ImageDrawオブジェクト
            title: 曲名（難易度なし）
            difficulty_part: 難易度部分（例: " (SPA)"）
            font: フォント
            max_width: 最大幅
        
        Returns:
            str: 省略された曲名 + 難易度
        """
        # 難易度部分の幅を計算
        difficulty_bbox = draw.textbbox((0, 0), difficulty_part, font=font)
        difficulty_width = difficulty_bbox[2] - difficulty_bbox[0]
        
        # 曲名に使える幅
        available_width = max_width - difficulty_width
        
        # 曲名全体が収まるかチェック
        title_bbox = draw.textbbox((0, 0), title, font=font)
        title_width = title_bbox[2] - title_bbox[0]
        
        if title_width <= available_width:
            # 収まる場合はそのまま
            return title + difficulty_part
        
        # 収まらない場合、曲名を省略
        ellipsis = "..."
        ellipsis_bbox = draw.textbbox((0, 0), ellipsis, font=font)
        ellipsis_width = ellipsis_bbox[2] - ellipsis_bbox[0]
        
        # 曲名 + "..." の幅が収まるように調整
        available_for_title = available_width - ellipsis_width
        
        for i in range(len(title), 0, -1):
            truncated_title = title[:i]
            bbox = draw.textbbox((0, 0), truncated_title, font=font)
            truncated_width = bbox[2] - bbox[0]
            
            if truncated_width <= available_for_title:
                return truncated_title + ellipsis + difficulty_part
        
        return ellipsis + difficulty_part
    
    def _truncate_text(self, draw, text, font, max_width):
        """
        テキストが長すぎる場合、省略記号を付けて切り詰める
        
        Args:
            draw: ImageDrawオブジェクト
            text: 元のテキスト
            font: フォント
            max_width: 最大幅
        
        Returns:
            str: 切り詰められたテキスト
        """
        # テキストの幅を取得
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            return text
        
        # 省略記号を追加して切り詰め
        ellipsis = "..."
        ellipsis_bbox = draw.textbbox((0, 0), ellipsis, font=font)
        ellipsis_width = ellipsis_bbox[2] - ellipsis_bbox[0]
        
        # 1文字ずつ削りながら幅をチェック
        for i in range(len(text), 0, -1):
            truncated = text[:i] + ellipsis
            bbox = draw.textbbox((0, 0), truncated, font=font)
            truncated_width = bbox[2] - bbox[0]
            
            if truncated_width <= max_width:
                return truncated
        
        return ellipsis
    
    def _draw_rounded_rectangle(self, draw, coords, radius=10, fill=(0, 0, 0, 180)):
        """角丸矩形を描画"""
        x1, y1, x2, y2 = coords
        
        # 矩形本体
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        
        # 四隅の円
        draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
        draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
        draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
        draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)
    
    def _draw_text_with_glow(self, draw, position, text, font, fill=(255, 255, 255), glow_color=(0, 0, 0)):
        """光彩付きテキストを描画（多重影で光彩効果）"""
        x, y = position
        
        # 光彩効果（複数の影を重ねる）
        for offset in [(3, 3), (3, -3), (-3, 3), (-3, -3), (0, 3), (3, 0), (0, -3), (-3, 0)]:
            draw.text((x + offset[0], y + offset[1]), text, font=font, fill=glow_color)
        
        # 本体
        draw.text((x, y), text, font=font, fill=fill)


if __name__ == "__main__":
    writer = ResultStatsWriter()
    
    img = Image.open('test.png')

    img = writer.write_statistics(
        img,
        title="Colors",
        level=12,
        play_style=play_style.sp,
        difficulty=difficulty.another,
        ex_score=2128,
        bp=15,
        max_notes=1258,
        lamp=clear_lamp.fc,
        bpi=1.22,
        sp12_clear=unofficial_difficulty.jiriki_d,
        sp12_hard=unofficial_difficulty.jiriki_e
    )
    img = img.crop((560,0,1920,1080))
    img.save('test_result_custom.png')
