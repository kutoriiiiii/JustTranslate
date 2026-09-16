"""Dialog for probing, selecting and batch-importing available LLM models."""

from typing import List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt


class ModelProbeDialog(QDialog):
    """Model probe results dialog allowing single apply or batch profile import."""

    ACTION_NONE = 0
    ACTION_APPLY_CURRENT = 1
    ACTION_BATCH_IMPORT = 2

    def __init__(self, models: List[str], current_model: str = "", parent=None):
        super().__init__(parent)
        self.all_models = models
        self.current_model = current_model
        self.action = self.ACTION_NONE
        self.chosen_model = ""
        self.chosen_models_batch: List[str] = []

        self.setWindowTitle("API 模型探测结果与导入")
        self.setMinimumSize(560, 480)
        self.resize(600, 520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # 标题提示
        lbl_info = QLabel(f"共探测到 <b>{len(self.all_models)}</b> 个可用模型。<br>您可以选择单个模型应用到当前配置，或勾选多个模型批量导入为独立配置：")
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        # 搜索过滤框
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 输入关键字实时过滤模型名称...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_models)
        search_layout.addWidget(self.search_edit)

        btn_select_all = QPushButton("全选")
        btn_select_all.clicked.connect(self._select_all)
        btn_unselect_all = QPushButton("全不选")
        btn_unselect_all.clicked.connect(self._unselect_all)
        search_layout.addWidget(btn_select_all)
        search_layout.addWidget(btn_unselect_all)
        layout.addLayout(search_layout)

        # 模型列表控件 (支持复选框)
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._populate_list(self.all_models)
        layout.addWidget(self.list_widget, 1)

        # 底部操作按钮栏
        btn_layout = QHBoxLayout()

        self.btn_apply_current = QPushButton("应用选定模型到当前配置")
        self.btn_apply_current.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold; padding: 6px 12px;")
        self.btn_apply_current.clicked.connect(self._on_apply_current)
        btn_layout.addWidget(self.btn_apply_current)

        self.btn_batch_import = QPushButton("批量导入勾选模型为新配置")
        self.btn_batch_import.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 6px 12px;")
        self.btn_batch_import.clicked.connect(self._on_batch_import)
        btn_layout.addWidget(self.btn_batch_import)

        btn_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _populate_list(self, models: List[str]):
        self.list_widget.clear()
        for model in models:
            item = QListWidgetItem(model)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            # 如果是当前使用的模型，默认高亮
            if model == self.current_model:
                item.setCheckState(Qt.Checked)
                item.setText(f"{model} (当前使用)")
                self.list_widget.addItem(item)
                self.list_widget.setCurrentItem(item)
            else:
                item.setCheckState(Qt.Unchecked)
                self.list_widget.addItem(item)

    def _filter_models(self, text: str):
        query = text.strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            raw_text = item.data(Qt.UserRole) or item.text().replace(" (当前使用)", "")
            item.setHidden(query not in raw_text.lower())

    def _select_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def _unselect_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Unchecked)

    def _get_item_model_name(self, item: QListWidgetItem) -> str:
        return item.text().replace(" (当前使用)", "").strip()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self.chosen_model = self._get_item_model_name(item)
        self.action = self.ACTION_APPLY_CURRENT
        self.accept()

    def _on_apply_current(self):
        # 优先使用高亮选中的项，若无高亮则取勾选项中的第一个
        current = self.list_widget.currentItem()
        if current:
            self.chosen_model = self._get_item_model_name(current)
        else:
            checked = self._get_checked_models()
            if checked:
                self.chosen_model = checked[0]
            else:
                QMessageBox.warning(self, "未选择模型", "请在列表中点击选中一个模型后再点击此按钮。")
                return

        self.action = self.ACTION_APPLY_CURRENT
        self.accept()

    def _get_checked_models(self) -> List[str]:
        res = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                res.append(self._get_item_model_name(item))
        return res

    def _on_batch_import(self):
        checked = self._get_checked_models()
        if not checked:
            current = self.list_widget.currentItem()
            if current:
                checked = [self._get_item_model_name(current)]
            else:
                QMessageBox.warning(self, "未勾选模型", "请在左侧勾选框中至少勾选一个想要导入的模型。")
                return

        self.chosen_models_batch = checked
        self.action = self.ACTION_BATCH_IMPORT
        self.accept()
