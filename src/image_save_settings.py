"""画像保存タブ。アプリと説明書用キャプチャで共用する。"""

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QButtonGroup,
    QRadioButton, QCheckBox, QFormLayout, QLineEdit, QPushButton, QFileDialog,
)

from src.classes import config_autosave_image, config_modify_rivalarea


class ImageSaveSettings(QWidget):
    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        layout = QVBoxLayout(self)

        output_group = QGroupBox(self.ui.image_save.output_group)
        output_layout = QFormLayout(output_group)
        self.image_save_path_edit = QLineEdit()
        self.browse_button = QPushButton(self.ui.dialog.browse)
        self.browse_button.clicked.connect(self.on_browse_clicked)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.image_save_path_edit)
        path_layout.addWidget(self.browse_button)
        output_layout.addRow(self.ui.feature.image_save_path, path_layout)
        layout.addWidget(output_group)

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

    def on_browse_clicked(self):
        current_dir = self.image_save_path_edit.text()
        if not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~")
        dir_path = QFileDialog.getExistingDirectory(
            self, self.ui.dialog.select_image_path, current_dir
        )
        if dir_path:
            self.image_save_path_edit.setText(dir_path)

    def load_config_values(self, config):
        """設定値を表示する。設定ファイルへの読み書きは行わない。"""
        self.image_save_path_edit.setText(config.image_save_path)
        if hasattr(config, 'autosave_image_mode'):
            button = self.autosave_button_group.button(config.autosave_image_mode.value)
            if button:
                button.setChecked(True)

        if hasattr(config, 'modify_rivalarea_mode'):
            button = self.rivalarea_button_group.button(config.modify_rivalarea_mode.value)
            if button:
                button.setChecked(True)

        if hasattr(config, 'write_statistics'):
            self.write_statistics_check.setChecked(config.write_statistics)

    def apply_to_config(self, config):
        """操作結果を設定オブジェクトへ反映する。保存は呼び出し元で行う。"""
        config.autosave_image_mode = config_autosave_image(self.autosave_button_group.checkedId())
        config.modify_rivalarea_mode = config_modify_rivalarea(self.rivalarea_button_group.checkedId())
        config.write_statistics = self.write_statistics_check.isChecked()
        config.image_save_path = self.image_save_path_edit.text()
