import sys
import os
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from src.domain.entities import PhoneConfig
from src.infrastructure.database.connection import init_db
from src.infrastructure.database.repository import (
    SQLContactRepository, SQLTemplateRepository,
    SQLCampaignRepository, SQLMessageRepository, SettingsRepository,
)
from src.presentation.main_window import MainWindow


def _resource_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "resources", filename)


def _load_stylesheet() -> str:
    resources_dir = os.path.join(os.path.dirname(__file__), "resources")
    parts = []
    for filename in ("styles.qss", "contacts.qss", "compact.qss"):
        path = os.path.join(resources_dir, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                parts.append(file.read())
    return "\n\n".join(parts)


def _shortcut(parent, sequence: str, callback):
    shortcut = QShortcut(QKeySequence(sequence), parent)
    shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    shortcut.activated.connect(callback)
    return shortcut


def _focus_search(search_input):
    search_input.setFocus()
    search_input.selectAll()


def _install_keyboard_shortcuts(window: MainWindow):
    """Install Windows-style shortcuts without changing destructive behaviour."""
    shortcuts = []

    contacts = getattr(window, "_contacts_widget", None)
    if contacts is not None:
        table = getattr(contacts, "_table", None)
        search = getattr(contacts, "_search_input", None)

        if table is not None:
            # Only active while the contacts table (or its viewport) has focus.
            shortcuts.append(_shortcut(table, "Delete", contacts._delete_selected_contacts))
            shortcuts.append(_shortcut(table, "Ctrl+A", table.selectAll))
            shortcuts.append(_shortcut(table, "F2", contacts._edit_contact))

        if search is not None:
            shortcuts.append(
                _shortcut(contacts, "Ctrl+F", lambda: _focus_search(search))
            )

    reports = getattr(window, "_reports_widget", None)
    if reports is not None:
        report_search = getattr(reports, "_search_input", None)
        report_table = getattr(reports, "_table", None)
        if report_search is not None:
            shortcuts.append(
                _shortcut(reports, "Ctrl+F", lambda: _focus_search(report_search))
            )
        if report_table is not None:
            shortcuts.append(_shortcut(report_table, "Ctrl+A", report_table.selectAll))

    # Standard safe shortcuts available throughout the desktop application.
    shortcuts.append(_shortcut(window, "Ctrl+N", window._new_campaign))
    shortcuts.append(_shortcut(window, "F5", window._refresh_current_page))

    # Keep Python references alive for the whole window lifetime.
    window._keyboard_shortcuts = shortcuts


def run():
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("SmsHks")
    app.setLayoutDirection(Qt.RightToLeft)

    icon_path = _resource_path("smshks.ico")
    app_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

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
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    brand_label = window.findChild(QLabel, "brandTitle")
    if brand_label is not None:
        brand_label.setText("SmsHks")

    _install_keyboard_shortcuts(window)
    window.show()

    exit_code = app.exec()

    settings_repo.set("phone_ip", phone_config.ip_address)
    settings_repo.set("phone_port", str(phone_config.port))
    settings_repo.set("phone_timeout_ms", str(phone_config.timeout_ms))
    settings_repo.set("phone_api_token", phone_config.api_token)

    sys.exit(exit_code)
