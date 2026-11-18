"""アカウント登録・編集ダイアログ。"""

from copy import deepcopy
from uuid import uuid4

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class AccountEditDialog(QDialog):
    def __init__(self, ui, account=None, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.account = deepcopy(account) if account else {
            "id": uuid4().hex,
            "name": "",
            "image_save_path": "",
            "color": "#ffffff",
            "rivals": [],
        }
        self.setWindowTitle(ui.account.edit_title if account else ui.account.add_title)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self.account["name"])
        form.addRow(ui.account.name, self.name_edit)

        path_row = QHBoxLayout()
        self.image_path_edit = QLineEdit(self.account.get("image_save_path", ""))
        self.image_path_edit.setPlaceholderText(ui.account.image_path_default)
        browse_button = QPushButton(ui.dialog.browse)
        browse_button.clicked.connect(self._browse_image_path)
        path_row.addWidget(self.image_path_edit, 1)
        path_row.addWidget(browse_button)
        form.addRow(ui.account.image_path, path_row)

        color_row = QHBoxLayout()
        self.color_edit = QLineEdit(self.account.get("color", "#ffffff"))
        self.color_edit.setReadOnly(True)
        self.color_button = QPushButton(ui.account.choose_color)
        self.color_button.clicked.connect(self._choose_color)
        color_row.addWidget(self.color_edit, 1)
        color_row.addWidget(self.color_button)
        form.addRow(ui.account.color, color_row)
        layout.addLayout(form)

        hint = QLabel(ui.account.image_path_help)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_image_path(self):
        path = QFileDialog.getExistingDirectory(
            self, self.ui.dialog.select_image_path, self.image_path_edit.text()
        )
        if path:
            self.image_path_edit.setText(path)

    def _choose_color(self):
        color = QColorDialog.getColor(QColor(self.color_edit.text()), self)
        if color.isValid():
            self.color_edit.setText(color.name())

    def _accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, self.ui.account.validation_title, self.ui.account.name_required)
            return
        self.account["name"] = name
        self.account["image_save_path"] = self.image_path_edit.text().strip()
        self.account["color"] = self.color_edit.text().lower()
        self.accept()


class AccountManagerDialog(QDialog):
    def __init__(self, config, ui, parent=None):
        super().__init__(parent)
        self.config = config
        self.ui = ui
        self.config._sync_selected_account_rivals()
        self.accounts = deepcopy(config.accounts)
        self.setWindowTitle(ui.account.manage_title)
        self.resize(680, 360)

        layout = QVBoxLayout(self)
        description = QLabel(ui.account.description)
        description.setWordWrap(True)
        layout.addWidget(description)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [ui.account.name, ui.account.image_path, ui.account.color]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table, 1)

        action_row = QHBoxLayout()
        add_button = QPushButton(ui.account.add)
        edit_button = QPushButton(ui.account.edit)
        delete_button = QPushButton(ui.account.delete)
        add_button.clicked.connect(self._add)
        edit_button.clicked.connect(self._edit)
        delete_button.clicked.connect(self._delete)
        action_row.addWidget(add_button)
        action_row.addWidget(edit_button)
        action_row.addWidget(delete_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh()

    def _refresh(self):
        self.table.setRowCount(len(self.accounts))
        for row, account in enumerate(self.accounts):
            name = account["name"]
            if account["id"] == self.config.selected_account_id:
                name += self.ui.account.selected_suffix
            self.table.setItem(row, 0, QTableWidgetItem(name))
            path = account.get("image_save_path") or self.ui.account.use_default
            self.table.setItem(row, 1, QTableWidgetItem(path))
            color_item = QTableWidgetItem(account.get("color", "#ffffff"))
            color_item.setForeground(QColor(account.get("color", "#ffffff")))
            self.table.setItem(row, 2, color_item)
        self.table.resizeColumnsToContents()

    def _selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _add(self, *_args):
        dialog = AccountEditDialog(self.ui, parent=self)
        if dialog.exec() == QDialog.Accepted:
            if self._name_exists(dialog.account["name"]):
                QMessageBox.warning(self, self.ui.account.validation_title, self.ui.account.name_duplicate)
                return
            self.accounts.append(dialog.account)
            self._refresh()

    def _edit(self, *_args):
        row = self._selected_row()
        if row < 0:
            return
        dialog = AccountEditDialog(self.ui, self.accounts[row], self)
        if dialog.exec() == QDialog.Accepted:
            if self._name_exists(dialog.account["name"], except_row=row):
                QMessageBox.warning(self, self.ui.account.validation_title, self.ui.account.name_duplicate)
                return
            self.accounts[row] = dialog.account
            self._refresh()

    def _delete(self, *_args):
        row = self._selected_row()
        if row < 0:
            return
        account = self.accounts[row]
        if account["id"] == "default":
            QMessageBox.warning(self, self.ui.account.validation_title, self.ui.account.default_not_deletable)
            return
        if account["id"] == self.config.selected_account_id:
            QMessageBox.warning(self, self.ui.account.validation_title, self.ui.account.selected_not_deletable)
            return
        if QMessageBox.question(
            self,
            self.ui.account.delete_title,
            self.ui.account.delete_confirm.format(name=account["name"]),
        ) == QMessageBox.Yes:
            del self.accounts[row]
            self._refresh()

    def _name_exists(self, name, except_row=None):
        normalized = name.casefold()
        return any(
            row != except_row and account["name"].casefold() == normalized
            for row, account in enumerate(self.accounts)
        )

    def _save(self):
        self.config._sync_selected_account_rivals()
        self.config.accounts = deepcopy(self.accounts)
        self.config.rivals = deepcopy(self.config.selected_account.get("rivals", []))
        self.config.save_config()
        self.accept()
