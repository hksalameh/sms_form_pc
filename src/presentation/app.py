import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.domain.entities import PhoneConfig
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repository import (
    SQLContactRepository, SQLTemplateRepository,
    SQLCampaignRepository, SQLMessageRepository, SettingsRepository,
)
from src.presentation.main_window import MainWindow


def run():
    init_db()

    app = QApplication(sys.argv)

    app.setLayoutDirection(Qt.RightToLeft)

    qss_path = os.path.join(os.path.dirname(__file__), "resources", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

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
    window.show()

    exit_code = app.exec()

    settings_repo.set("phone_ip", phone_config.ip_address)
    settings_repo.set("phone_port", str(phone_config.port))
    settings_repo.set("phone_timeout_ms", str(phone_config.timeout_ms))
    settings_repo.set("phone_api_token", phone_config.api_token)

    sys.exit(exit_code)
