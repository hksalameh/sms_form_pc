import asyncio
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QGroupBox, QMessageBox,
)
from src.domain.entities import PhoneConfig
from src.application.sms.sender import SmsSender


class PhoneSettingsDialog(QDialog):
    def __init__(self, config: PhoneConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._sender = SmsSender(config)
        self.setWindowTitle("إعدادات الاتصال بالهاتف")
        self.setMinimumWidth(450)
        self.setLayoutDirection(self.layoutDirection())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("بيانات الهاتف")
        gl = QVBoxLayout(group)

        ip_row = QHBoxLayout()
        ip_row.addWidget(QLabel("IP الهاتف:"))
        self._ip_input = QLineEdit(self._config.ip_address)
        ip_row.addWidget(self._ip_input)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("المنفذ (Port):"))
        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(self._config.port)
        port_row.addWidget(self._port_input)

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("مهلة الاتصال (ثانية):"))
        self._timeout_input = QSpinBox()
        self._timeout_input.setRange(1, 120)
        self._timeout_input.setValue(self._config.timeout_ms // 1000)
        timeout_row.addWidget(self._timeout_input)

        token_row = QHBoxLayout()
        token_row.addWidget(QLabel("API Token:"))
        self._token_input = QLineEdit(self._config.api_token)
        self._token_input.setEchoMode(QLineEdit.Password)
        self._token_input.setPlaceholderText("PHONE_SERVER_API_TOKEN")
        token_row.addWidget(self._token_input)

        gl.addLayout(ip_row)
        gl.addLayout(port_row)
        gl.addLayout(timeout_row)
        gl.addLayout(token_row)
        layout.addWidget(group)

        btn_health = QPushButton("فحص الاتصال (Health Check)")
        btn_health.clicked.connect(self._health_check)
        layout.addWidget(btn_health)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("حفظ")
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("إلغاء")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _health_check(self):
        self._status_label.setText("جاري فحص الاتصال...")
        self._status_label.setStyleSheet("color: #F39C12; font-weight: bold; padding: 8px;")
        config = self._current_config()
        self._sender._client = None
        self._sender._config = config
        try:
            loop = asyncio.new_event_loop()
            success, msg = loop.run_until_complete(self._sender.check_health())
            loop.close()
            if success:
                self._status_label.setText(f"✓ متصل - {msg}")
                self._status_label.setStyleSheet("color: #27AE60; font-weight: bold; padding: 8px;")
            else:
                self._status_label.setText(f"✗ فشل الاتصال: {msg}")
                self._status_label.setStyleSheet("color: #C44444; font-weight: bold; padding: 8px;")
        except Exception as e:
            self._status_label.setText(f"✗ خطأ: {e}")
            self._status_label.setStyleSheet("color: #C44444; font-weight: bold; padding: 8px;")

    def _current_config(self) -> PhoneConfig:
        return PhoneConfig(
            ip_address=self._ip_input.text().strip(),
            port=self._port_input.value(),
            timeout_ms=self._timeout_input.value() * 1000,
            api_token=self._token_input.text().strip(),
        )

    def _save(self):
        config = self._current_config()
        self._config.ip_address = config.ip_address
        self._config.port = config.port
        self._config.timeout_ms = config.timeout_ms
        self._config.api_token = config.api_token
        self.accept()

    @property
    def config(self) -> PhoneConfig:
        return self._config
