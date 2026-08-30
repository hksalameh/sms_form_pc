from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QSpinBox, QTableWidget, QTableWidgetItem,
    QGroupBox, QMessageBox, QHeaderView,
)
from src.domain.entities import PhoneConfig, Campaign
from src.application.sms.sender import SmsSender
from src.application.services.template_service import TemplateService
from src.presentation.widgets.phone_settings_dialog import PhoneSettingsDialog
from src.presentation.widgets.templates_widget import TemplateDialog
from src.application.sms.splitter import estimate_sms_parts


class SettingsWidget(QWidget):
    def __init__(self, config: PhoneConfig, update_config_fn,
                 template_service: TemplateService):
        super().__init__()
        self._config = config
        self._update_config = update_config_fn
        self._template_service = template_service
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        phone_group = QGroupBox("إعدادات الهاتف")
        phone_layout = QHBoxLayout(phone_group)
        self._ip_label = QLabel(f"IP: {self._config.ip_address}:{self._config.port}")
        self._ip_label.setStyleSheet("font-size: 14px; padding: 8px;")
        phone_layout.addWidget(self._ip_label)

        btn_edit = QPushButton("تعديل الإعدادات")
        btn_edit.clicked.connect(self._edit_phone_settings)
        phone_layout.addWidget(btn_edit)

        btn_health = QPushButton("فحص الاتصال")
        btn_health.clicked.connect(self._health_check)
        phone_layout.addWidget(btn_health)
        layout.addWidget(phone_group)

        default_group = QGroupBox("الإعدادات الافتراضية للحملات")
        defaults_layout = QVBoxLayout(default_group)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("التأخير الافتراضي (مللي ثانية):"))
        self._default_delay = QSpinBox()
        self._default_delay.setRange(100, 60000)
        self._default_delay.setValue(1000)
        self._default_delay.setSuffix(" ms")
        delay_row.addWidget(self._default_delay)
        defaults_layout.addLayout(delay_row)

        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("عدد المحاولات الافتراضي:"))
        self._default_retries = QSpinBox()
        self._default_retries.setRange(0, 10)
        self._default_retries.setValue(3)
        retry_row.addWidget(self._default_retries)
        defaults_layout.addLayout(retry_row)
        layout.addWidget(default_group)

        template_group = QGroupBox("القوالب")
        template_layout = QVBoxLayout(template_group)

        template_actions = QHBoxLayout()
        btn_add = QPushButton("قالب جديد")
        btn_add.clicked.connect(self._add_template)
        template_actions.addWidget(btn_add)

        btn_edit = QPushButton("تعديل")
        btn_edit.clicked.connect(self._edit_template)
        template_actions.addWidget(btn_edit)

        btn_delete = QPushButton("حذف")
        btn_delete.setObjectName("btnDanger")
        btn_delete.clicked.connect(self._delete_template)
        template_actions.addWidget(btn_delete)
        template_actions.addStretch()
        template_layout.addLayout(template_actions)

        self._template_table = QTableWidget()
        self._template_table.setColumnCount(3)
        self._template_table.setHorizontalHeaderLabels(["الاسم", "المحتوى", "الأجزاء"])
        self._template_table.horizontalHeader().setStretchLastSection(True)
        self._template_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._template_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._template_table.setSelectionMode(QTableWidget.SingleSelection)
        self._template_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._template_table.setAlternatingRowColors(True)
        self._template_table.setMaximumHeight(200)
        template_layout.addWidget(self._template_table)

        layout.addWidget(template_group)

        layout.addStretch()

        self._health_label = QLabel("")
        self._health_label.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(self._health_label)

    def refresh(self):
        self._load_templates()

    def _load_templates(self):
        templates = self._template_service.get_all()
        self._template_table.setRowCount(len(templates))
        for i, t in enumerate(templates):
            parts, _ = estimate_sms_parts(t.content)
            display = t.content[:80] + "..." if len(t.content) > 80 else t.content
            self._template_table.setItem(i, 0, QTableWidgetItem(t.name))
            self._template_table.setItem(i, 1, QTableWidgetItem(display))
            self._template_table.setItem(i, 2, QTableWidgetItem(str(parts)))
            self._template_table.item(i, 0).setData(256, t.id)

    def _add_template(self):
        dialog = TemplateDialog(self)
        if dialog.exec():
            self._template_service.add(dialog.template)
            self._load_templates()

    def _edit_template(self):
        row = self._template_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار قالب")
            return
        template_id = self._template_table.item(row, 0).data(256)
        template = self._template_service.get_by_id(template_id)
        if not template:
            return
        dialog = TemplateDialog(self, template)
        if dialog.exec():
            updated = dialog.template
            updated.id = template.id
            self._template_service.update(updated)
            self._load_templates()

    def _delete_template(self):
        row = self._template_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار قالب")
            return
        template_id = self._template_table.item(row, 0).data(256)
        confirm = QMessageBox.question(self, "تأكيد", "هل أنت متأكد من حذف القالب؟")
        if confirm == QMessageBox.Yes:
            self._template_service.delete(template_id)
            self._load_templates()

    def _edit_phone_settings(self):
        dialog = PhoneSettingsDialog(self._config, self)
        if dialog.exec():
            self._ip_label.setText(f"IP: {self._config.ip_address}:{self._config.port}")
            self._update_config(self._config)

    def _health_check(self):
        self._health_label.setText("جاري الفحص...")
        self._health_label.setStyleSheet("color: #F39C12; font-weight: bold; padding: 8px;")
        sender = SmsSender(self._config)
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            success, msg = loop.run_until_complete(sender.check_health())
            loop.close()
            if success:
                self._health_label.setText(f"✓ متصل: {msg}")
                self._health_label.setStyleSheet("color: #27AE60; font-weight: bold; padding: 8px;")
            else:
                self._health_label.setText(f"✗ غير متصل: {msg}")
                self._health_label.setStyleSheet("color: #C44444; font-weight: bold; padding: 8px;")
        except Exception as e:
            self._health_label.setText(f"✗ خطأ: {e}")
            self._health_label.setStyleSheet("color: #C44444; font-weight: bold; padding: 8px;")
