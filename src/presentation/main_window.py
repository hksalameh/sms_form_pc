from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt
from src.domain.entities import PhoneConfig, Campaign, Template
from src.domain.interfaces import ContactRepository, TemplateRepository, CampaignRepository, MessageRepository
from src.application.services.contact_service import ContactService
from src.application.services.template_service import TemplateService
from src.application.services.campaign_service import CampaignService
from src.application.services.export_service import ExportService
from src.application.sms.sender import SmsSender
from src.presentation.widgets.contacts_widget import ContactsWidget
from src.presentation.widgets.campaigns_widget import CampaignsWidget
from src.presentation.widgets.reports_widget import ReportsWidget
from src.presentation.widgets.settings_widget import SettingsWidget


class MainWindow(QMainWindow):
    def __init__(self, config: PhoneConfig,
                 contact_repo: ContactRepository,
                 template_repo: TemplateRepository,
                 campaign_repo: CampaignRepository,
                 message_repo: MessageRepository):
        super().__init__()
        self._config = config
        self._contact_repo = contact_repo
        self._template_repo = template_repo
        self._campaign_repo = campaign_repo
        self._message_repo = message_repo

        self._contact_service = ContactService(contact_repo)
        self._template_service = TemplateService(template_repo)
        self._sender = SmsSender(config)
        self._campaign_service = CampaignService(campaign_repo, message_repo, contact_repo, self._sender)
        self._export_service = ExportService(campaign_repo, message_repo)

        self.setWindowTitle("SMSCaster - نظام إرسال الرسائل الجماعية")
        self.setMinimumSize(1100, 700)
        self._build_ui()

    def _build_ui(self):
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        self._contacts_widget = ContactsWidget(self._contact_service)
        self._tabs.addTab(self._contacts_widget, "جهات الاتصال")

        self._campaigns_widget = CampaignsWidget(
            self._campaign_service,
            get_groups_fn=lambda: self._contact_service.get_groups(),
            get_templates_fn=lambda: self._template_service.get_all(),
        )
        self._tabs.addTab(self._campaigns_widget, "الحملات")

        self._reports_widget = ReportsWidget(
            self._export_service,
            get_campaigns_fn=lambda: self._campaign_service.get_all(),
        )
        self._tabs.addTab(self._reports_widget, "التقارير")

        self._settings_widget = SettingsWidget(self._config, self._update_config, self._template_service)
        self._tabs.addTab(self._settings_widget, "الإعدادات")

        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._status_label = QLabel("جاهز")
        self.statusBar().addWidget(self._status_label)

    def _on_tab_changed(self, index):
        widget = self._tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _update_config(self, config: PhoneConfig):
        self._config.ip_address = config.ip_address
        self._config.port = config.port
        self._config.timeout_ms = config.timeout_ms
        self._config.api_token = config.api_token
        self._sender._config = config
        self._sender._client = None
        self._campaign_service = CampaignService(
            self._campaign_repo, self._message_repo, self._contact_repo, self._sender
        )
        if hasattr(self, "_campaigns_widget"):
            self._campaigns_widget.set_service(self._campaign_service)
