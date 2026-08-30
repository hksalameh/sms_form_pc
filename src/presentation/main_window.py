import asyncio

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
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
    finished = Signal(bool, str)

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
            self.finished.emit(success, message)
        except Exception as exc:
            self.finished.emit(False, str(exc))


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

        self.setWindowTitle("SMSCaster - مدير الرسائل عبر الهاتف")
        self.setMinimumSize(1180, 720)
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
        body_layout.setContentsMargins(14, 12, 14, 12)
        body_layout.setSpacing(12)

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
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(10)

        brand = QLabel("SMSCaster")
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

        btn_refresh = QPushButton("↻  تحديث")
        btn_refresh.setObjectName("topSecondaryButton")
        btn_refresh.clicked.connect(self._refresh_current_page)
        layout.addWidget(btn_refresh)

        self._btn_health = QPushButton("●  فحص الاتصال")
        self._btn_health.setObjectName("topConnectionButton")
        self._btn_health.clicked.connect(self._check_phone_health)
        layout.addWidget(self._btn_health)

        return topbar

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sideBar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(6)

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

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("sideSeparator")
        layout.addWidget(separator)

        phone_caption = QLabel("الهاتف المتصل")
        phone_caption.setObjectName("sideCaption")
        layout.addWidget(phone_caption)

        self._side_phone_status = QLabel("●  لم يتم الفحص")
        self._side_phone_status.setObjectName("phoneStatusUnknown")
        layout.addWidget(self._side_phone_status)

        self._side_phone_address = QLabel(self._phone_address_text())
        self._side_phone_address.setObjectName("mutedText")
        self._side_phone_address.setWordWrap(True)
        layout.addWidget(self._side_phone_address)

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
        header_layout.setContentsMargins(20, 16, 20, 12)
        header_layout.setSpacing(3)

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
        panel.setFixedWidth(235)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("حالة الهاتف")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self._phone_indicator = QLabel("●")
        self._phone_indicator.setObjectName("phoneIndicatorUnknown")
        self._phone_indicator.setAlignment(self._phone_indicator.alignment())
        layout.addWidget(self._phone_indicator)

        self._phone_state = QLabel("لم يتم فحص الاتصال")
        self._phone_state.setObjectName("phoneState")
        self._phone_state.setWordWrap(True)
        layout.addWidget(self._phone_state)

        self._phone_address = QLabel(self._phone_address_text())
        self._phone_address.setObjectName("phoneAddress")
        self._phone_address.setWordWrap(True)
        layout.addWidget(self._phone_address)

        self._panel_health_button = QPushButton("فحص الاتصال الآن")
        self._panel_health_button.setObjectName("panelActionButton")
        self._panel_health_button.clicked.connect(self._check_phone_health)
        layout.addWidget(self._panel_health_button)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("panelSeparator")
        layout.addWidget(separator)

        summary_title = QLabel("وصول سريع")
        summary_title.setObjectName("panelTitle")
        layout.addWidget(summary_title)

        quick_contacts = QPushButton("جهات الاتصال")
        quick_contacts.setObjectName("quickLink")
        quick_contacts.clicked.connect(lambda: self._show_page(self.PAGE_CONTACTS))
        layout.addWidget(quick_contacts)

        quick_campaigns = QPushButton("عمليات الإرسال")
        quick_campaigns.setObjectName("quickLink")
        quick_campaigns.clicked.connect(lambda: self._show_page(self.PAGE_CAMPAIGNS))
        layout.addWidget(quick_campaigns)

        quick_reports = QPushButton("التقارير")
        quick_reports.setObjectName("quickLink")
        quick_reports.clicked.connect(lambda: self._show_page(self.PAGE_REPORTS))
        layout.addWidget(quick_reports)

        layout.addStretch()

        hint = QLabel(
            "يفضل فحص اتصال الهاتف قبل بدء أي عملية إرسال."
        )
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
        title, subtitle = titles.get(index, ("SMSCaster", ""))
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

        self._set_phone_status("checking", "جاري فحص الاتصال...")
        self._btn_health.setEnabled(False)
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

    def _on_phone_health_result(self, success: bool, message: str):
        connected = success and str(message).lower() == "connected"
        if connected:
            self._set_phone_status("connected", "الهاتف متصل وجاهز")
        elif success:
            self._set_phone_status("disconnected", f"الهاتف غير جاهز: {message}")
        else:
            self._set_phone_status("disconnected", f"تعذر الاتصال: {message}")

    def _set_phone_status(self, state: str, text: str):
        object_names = {
            "connected": ("phoneIndicatorConnected", "phoneStatusConnected"),
            "disconnected": ("phoneIndicatorDisconnected", "phoneStatusDisconnected"),
            "checking": ("phoneIndicatorChecking", "phoneStatusChecking"),
        }
        indicator_name, side_name = object_names.get(
            state, ("phoneIndicatorUnknown", "phoneStatusUnknown")
        )
        self._phone_indicator.setObjectName(indicator_name)
        self._side_phone_status.setObjectName(side_name)
        self._phone_indicator.style().unpolish(self._phone_indicator)
        self._phone_indicator.style().polish(self._phone_indicator)
        self._side_phone_status.style().unpolish(self._side_phone_status)
        self._side_phone_status.style().polish(self._side_phone_status)

        self._phone_state.setText(text)
        self._side_phone_status.setText(f"●  {text}")
        self._status_phone.setText(f"الهاتف: {text}")

    def _clear_health_worker(self):
        self._health_thread = None
        self._health_worker = None
        self._btn_health.setEnabled(True)
        self._panel_health_button.setEnabled(True)

    def _update_config(self, config: PhoneConfig):
        self._config.ip_address = config.ip_address
        self._config.port = config.port
        self._config.timeout_ms = config.timeout_ms
        self._config.api_token = config.api_token
        self._sender._config = config
        self._sender._client = None
        self._campaign_service = CampaignService(
            self._campaign_repo,
            self._message_repo,
            self._contact_repo,
            self._sender,
        )
        self._campaigns_widget.set_service(self._campaign_service)

        address = self._phone_address_text()
        self._phone_address.setText(address)
        self._side_phone_address.setText(address)
        self._set_phone_status("unknown", "لم يتم فحص الاتصال بعد تغيير الإعدادات")