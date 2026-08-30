import sys
import os
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt
from src.domain.entities import PhoneConfig
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repository import (
    SQLContactRepository, SQLTemplateRepository,
    SQLCampaignRepository, SQLMessageRepository, SettingsRepository,
)
from src.presentation.main_window import MainWindow


def _load_stylesheet() -> str:
    resources_dir = os.path.join(os.path.dirname(__file__), "resources")
    parts = []
    for filename in ("styles.qss", "contacts.qss"):
        path = os.path.join(resources_dir, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                parts.append(file.read())
    return "\n\n".join(parts)


def run():
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("SmsHks")
    app.setDisplayName("SmsHks")
    app.setLayoutDirection(Qt.RightToLeft)

    stylesheet = _load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    settings_repo = SettingsRepository()
    phone_config = PhoneConfig(
        ip_address=settings_repo.get("phone_ip", "192.168.42.129"),
        port=int(settings_repo.get("phone_port", "8000")),
        timeout_ms=int(settings_repo.get("phone_timeout_ms", "30000")),
        api_token=settings_repo.get("phone_api_token", ""),
    )

    contact_repo = SQLContactRepository()
    template_repo = SQLTemplateRepository()
    campaign_repo = SQLCampaignRepository()
    message_repo = SQLMessageRepository()

    window = MainWindow(phone_config, contact_repo, template_repo, campaign_repo, message_repo)
    window.setWindowTitle("SmsHks - مدير الرسائل عبر الهاتف")
    brand_label = window.findChild(QLabel, "brandTitle")
    if brand_label is not None:
        brand_label.setText("SmsHks")
    window.show()

    exit_code = app.exec()

    settings_repo.set("phone_ip", phone_config.ip_address)
    settings_repo.set("phone_port", str(phone_config.port))
    settings_repo.set("phone_timeout_ms", str(phone_config.timeout_ms))
    settings_repo.set("phone_api_token", phone_config.api_token)

    sys.exit(exit_code)
