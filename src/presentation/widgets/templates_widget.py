from PySide6.QtWidgets import (
    QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QLabel, QDialog,
    QDialogButtonBox,
)
from src.domain.entities import Template
from src.application.sms.splitter import estimate_sms_parts


class TemplateDialog(QDialog):
    def __init__(self, parent=None, template: Template = None):
        super().__init__(parent)
        self._template = template or Template()
        self.setWindowTitle("بيانات القالب")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name_input = QLineEdit(self._template.name)
        form.addRow("اسم القالب:", self._name_input)
        layout.addLayout(form)

        QLabel("ملاحظة: استخدم {name}, {phone}, {notes}, {group} كمتغيرات").setStyleSheet("color: #666;")
        layout.addWidget(QLabel("ملاحظة: استخدم {name}, {phone}, {notes}, {group} كمتغيرات"))

        self._content_input = QTextEdit()
        self._content_input.setPlainText(self._template.content)
        self._content_input.setMinimumHeight(150)
        layout.addWidget(QLabel("نص الرسالة:"))
        layout.addWidget(self._content_input)

        self._info_label = QLabel("")
        layout.addWidget(self._info_label)
        self._content_input.textChanged.connect(self._update_info)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_info()

    def _update_info(self):
        text = self._content_input.toPlainText()
        parts, per_part = estimate_sms_parts(text)
        self._info_label.setText(
            f"عدد الأحرف: {len(text)} | الأجزاء المتوقعة: {parts} (الحد: {per_part} حرف للجزء)"
        )

    @property
    def template(self) -> Template:
        return Template(
            name=self._name_input.text().strip(),
            content=self._content_input.toPlainText().strip(),
        )
