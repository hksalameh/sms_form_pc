import asyncio

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities import PhoneConfig
from src.domain.interfaces import (
    CampaignRepository,
    ContactRepository,
    MessageRepository,
    TemplateRepository,
)
from src.application.services.campaign_service import CampaignService
from src.application.services.contact_service import ContactService
from src.application.services.export_service import ExportService
from src.application.services.template_service import TemplateService
from src.application.sms.sender import SmsSender
from src.presentation.widgets.campaigns_widget import CampaignsWidget
from src.presentation.widgets.contacts_widget import ContactsWidget
from src.presentation.widgets.reports_widget import ReportsWidget
from src.presentation.widgets.settings_widget import SettingsWidget


class PhoneHealthWorker(QObject):
    finished = Signal(bool, str, str)

    def __init__(self, config: PhoneConfig):
        super().__init__()
        self._config = PhoneConfig(
            ip_address=config.ip_address,
            port=config.port,
            timeout_ms=config.timeout_ms,
            api_token=config.api_token,
        )

    @Slot()
    def run(self):
        sender = SmsSender(self._config)
        try:
            success, message = asyncio.run(sender.check_health())
            self.finished.emit(success, message, self._config.ip_address)
        except Exception as exc:
            self.finished.emit(False, str(exc), self._config.ip_address)


class MainWindow(QMainWindow):
    PAGE_CONTACTS = 0
    PAGE_CAMPAIGNS = 1
    PAGE_REPORTS = 2
    PAGE_SETTINGS = 3

    def __init__(
        self,
        config: PhoneConfig,
        contact_repo: ContactRepository,
        template_repo: TemplateRepository,
        campaign_repo: CampaignRepository,
        message_repo: MessageRepository,
    ):
        super().__init__()
        self._config = config
        self._contact_repo = contact_repo
        self._template_repo = template_repo
        self._campaign_repo = campaign_repo
        self._message_repo = message_repo

        self._contact_service = ContactService(contact_repo)
        self._template_service = TemplateService(template_repo)
        self._sender = SmsSender(config)
        self._campaign_service = CampaignService(
            campaign_repo, message_repo, contact_repo, self._sender
        )
        self._export_service = ExportService(campaign_repo, message_repo)

        self._health_thread = None
        self._health_worker = None
        self._nav_buttons = []

        self.setWindowTitle("SmsHks - مدير الرسائل عبر الهاتف")
        self.setMinimumSize(1080, 680)
        self.resize(1380, 820)
        self._build_ui()
        self._show_page(self.PAGE_CAMPAIGNS)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_topbar())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(10, 9, 10, 9)
        body_layout.setSpacing(9)

        body_layout.addWidget(self._build_sidebar())
        body_layout.addWidget(self._build_content(), 1)
        body_layout.addWidget(self._build_phone_panel())

        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

        self._status_label = QLabel("جاهز")
        self.statusBar().addWidget(self._status_label)
        self._status_phone = QLabel("الهاتف: لم يتم الفحص")
        self.statusBar().addPermanentWidget(self._status_phone)

    def _build_topbar(self) -> QWidget:
        topbar = QFrame()
        topbar.setObjectName("topBar")
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(14, 7, 14, 7)
        layout.setSpacing(8)

        brand = QLabel("SmsHks")
        brand.setObjectName("brandTitle")
        layout.addWidget(brand)

        subtitle = QLabel("مدير الرسائل عبر الهاتف")
        subtitle.setObjectName("brandSubtitle")
        layout.addWidget(subtitle)
        layout.addStretch()

        btn_new = QPushButton("✉  رسالة جديدة")
        btn_new.setObjectName("topPrimaryButton")
        btn_new.clicked.connect(self._new_campaign)
        layout.addWidget(btn_new)

        return topbar

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sideBar")
        sidebar.setFixedWidth(185)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(4)

        caption = QLabel("التنقل")
        caption.setObjectName("sideCaption")
        layout.addWidget(caption)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        nav_items = [
            (self.PAGE_CAMPAIGNS, "✎  عمليات الإرسال"),
            (self.PAGE_CONTACTS, "●  جهات الاتصال"),
            (self.PAGE_REPORTS, "▥  التقارير"),
            (self.PAGE_SETTINGS, "⚙  الإعدادات"),
        ]

        for page_index, text in nav_items:
            button = QPushButton(text)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setProperty("pageIndex", page_index)
            button.clicked.connect(
                lambda checked=False, index=page_index: self._show_page(index)
            )
            self._nav_group.addButton(button)
            self._nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch()
        return sidebar

    def _build_content(self) -> QWidget:
        container = QFrame()
        container.setObjectName("contentCard")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("pageHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 8)
        header_layout.setSpacing(1)

        self._page_title = QLabel("")
        self._page_title.setObjectName("pageTitle")
        header_layout.addWidget(self._page_title)

        self._page_subtitle = QLabel("")
        self._page_subtitle.setObjectName("pageSubtitle")
        header_layout.addWidget(self._page_subtitle)
        layout.addWidget(header)

        self._stack = QStackedWidget()
        self._stack.setObjectName("mainStack")

        self._contacts_widget = ContactsWidget(self._contact_service)
        self._stack.addWidget(self._contacts_widget)

        self._campaigns_widget = CampaignsWidget(
            self._campaign_service,
            get_groups_fn=lambda: self._contact_service.get_groups(),
            get_templates_fn=lambda: self._template_service.get_all(),
        )
        self._stack.addWidget(self._campaigns_widget)

        self._reports_widget = ReportsWidget(
            self._export_service,
            get_campaigns_fn=lambda: self._campaign_service.get_all(),
        )
        self._stack.addWidget(self._reports_widget)

        self._settings_widget = SettingsWidget(
            self._config, self._update_config, self._template_service
        )
        self._stack.addWidget(self._settings_widget)

        layout.addWidget(self._stack, 1)
        return container

    def _build_phone_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("phonePanel")
        panel.setFixedWidth(185)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)

        title = QLabel("حالة الهاتف")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._phone_indicator = QLabel("●")
        self._phone_indicator.setObjectName("phoneIndicatorUnknown")
        self._phone_indicator.setFixedWidth(22)
        status_row.addWidget(self._phone_indicator)

        self._phone_state = QLabel("لم يتم فحص الاتصال")
        self._phone_state.setObjectName("phoneState")
        self._phone_state.setWordWrap(True)
        status_row.addWidget(self._phone_state, 1)
        layout.addLayout(status_row)

        self._phone_address = QLabel(self._phone_address_text())
        self._phone_address.setObjectName("phoneAddress")
        self._phone_address.setWordWrap(True)
        layout.addWidget(self._phone_address)

        self._panel_health_button = QPushButton("فحص الاتصال")
        self._panel_health_button.setObjectName("panelActionButton")
        self._panel_health_button.clicked.connect(self._check_phone_health)
        layout.addWidget(self._panel_health_button)

        layout.addStretch()

        hint = QLabel("الاتصال يتم مباشرة عبر USB عند تفعيل USB debugging.")
        hint.setObjectName("panelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return panel

    def _show_page(self, index: int):
        if index < 0 or index >= self._stack.count():
            return

        self._stack.setCurrentIndex(index)
        titles = {
            self.PAGE_CONTACTS: (
                "جهات الاتصال",
                "إدارة الأرقام والمجموعات والبحث والاستيراد.",
            ),
            self.PAGE_CAMPAIGNS: (
                "عمليات الإرسال",
                "أنشئ رسالة جديدة وتابع الإرسال والنتائج من مكان واحد.",
            ),
            self.PAGE_REPORTS: (
                "التقارير",
                "راجع نتائج عمليات الإرسال والرسائل المرسلة والفاشلة.",
            ),
            self.PAGE_SETTINGS: (
                "الإعدادات",
                "إعداد اتصال الهاتف والقوالب وخيارات الإرسال.",
            ),
        }
        title, subtitle = titles.get(index, ("SmsHks", ""))
        self._page_title.setText(title)
        self._page_subtitle.setText(subtitle)

        for button in self._nav_buttons:
            if button.property("pageIndex") == index:
                button.setChecked(True)
                break

        widget = self._stack.currentWidget()
        if hasattr(widget, "refresh"):
            widget.refresh()
        self._status_label.setText(title)

    def _refresh_current_page(self):
        widget = self._stack.currentWidget()
        if hasattr(widget, "refresh"):
            widget.refresh()
        self._status_label.setText("تم تحديث الصفحة")

    def _new_campaign(self):
        self._show_page(self.PAGE_CAMPAIGNS)
        if hasattr(self._campaigns_widget, "_new_campaign"):
            self._campaigns_widget._new_campaign()

    def _phone_address_text(self) -> str:
        return f"{self._config.ip_address}:{self._config.port}"

    def _check_phone_health(self):
        if self._health_thread is not None:
            return

        self._set_phone_status("checking", "جاري الفحص...")
        self._panel_health_button.setEnabled(False)

        self._health_thread = QThread(self)
        self._health_worker = PhoneHealthWorker(self._config)
        self._health_worker.moveToThread(self._health_thread)
        self._health_thread.started.connect(self._health_worker.run)
        self._health_worker.finished.connect(self._on_phone_health_result)
        self._health_worker.finished.connect(self._health_thread.quit)
        self._health_thread.finished.connect(self._health_worker.deleteLater)
        self._health_thread.finished.connect(self._health_thread.deleteLater)
        self._health_thread.finished.connect(self._clear_health_worker)
        self._health_thread.start()

    def _on_phone_health_result(self, success: bool, message: str, address: str):
        connected = success and str(message).lower() == "connected"

        if connected and address:
            self._config.ip_address = address
            self._sender._client = None
            self._phone_address.setText(self._phone_address_text())

        if connected:
            self._set_phone_status("connected", "متصل وجاهز")
        elif success:
            self._set_phone_status("disconnected", f"غير جاهز: {message}")
        else:
            self._set_phone_status("disconnected", f"تعذر الاتصال: {message}")

    def _set_phone_status(self, state: str, text: str):
        object_names = {
            "connected": "phoneIndicatorConnected",
            "disconnected": "phoneIndicatorDisconnected",
            "checking": "phoneIndicatorChecking",
        }
        indicator_name = object_names.get(state, "phoneIndicatorUnknown")
        self._phone_indicator.setObjectName(indicator_name)
        self._phone_indicator.style().unpolish(self._phone_indicator)
        self._phone_indicator.style().polish(self._phone_indicator)

        self._phone_state.setText(text)
        self._status_phone.setText(f"الهاتف: {text}")

    def _clear_health_worker(self):
        self._health_thread = None
        self._health_worker = None
        self._panel_health_button.setEnabled(True)

    def _update_config(self, config: PhoneConfig):
        self._config.ip_address = config.ip_address
        self._config.port = config.port
        self._config.timeout_ms = config.timeout_ms
        self._config.api_token = config.api_token
        self._sender._config = self._config
        self._sender._client = None
        self._campaign_service = CampaignService(
            self._campaign_repo,
            self._message_repo,
            self._contact_repo,
            self._sender,
        )
        self._campaigns_widget.set_service(self._campaign_service)

        self._phone_address.setText(self._phone_address_text())
        self._set_phone_status("unknown", "لم يتم الفحص بعد تغيير الإعدادات")
