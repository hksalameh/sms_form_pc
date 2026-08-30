import asyncio
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QLineEdit, QComboBox, QSpinBox,
    QTextEdit, QMessageBox, QHeaderView, QGroupBox, QDialog,
    QFormLayout, QDialogButtonBox, QProgressBar,
)
from PySide6.QtCore import QThread, Signal, QObject, Slot
from src.domain.entities import Campaign, Template, Message
from src.domain.enums import CampaignStatus
from src.application.services.campaign_service import CampaignService
from src.application.sms.splitter import estimate_sms_parts


class CampaignSignals(QObject):
    progress_updated = Signal(int, int, int, int)
    campaign_finished = Signal()


class CampaignWorker(QObject):
    progress_updated = Signal(int, int, int, int)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, service: CampaignService, campaign_id: int):
        super().__init__()
        self._service = service
        self._campaign_id = campaign_id

    @Slot()
    def run(self):
        try:
            asyncio.run(self._service.start_campaign(
                self._campaign_id,
                self.progress_updated.emit,
            ))
            campaign = self._service.get_by_id(self._campaign_id)
            if campaign and campaign.status == CampaignStatus.CANCELLED:
                self.finished.emit("تم إيقاف الإرسال")
            elif campaign and campaign.status == CampaignStatus.PAUSED:
                self.finished.emit("توقفت الحملة مع رسائل معلقة")
            else:
                self.finished.emit("اكتمل الإرسال")
        except Exception as e:
            self.failed.emit(str(e))


class CampaignsWidget(QWidget):
    def __init__(self, service: CampaignService, get_groups_fn, get_templates_fn):
        super().__init__()
        self._service = service
        self._get_groups = get_groups_fn
        self._get_templates = get_templates_fn
        self._signals = CampaignSignals()
        self._running = False
        self._current_campaign_id = None
        self._thread = None
        self._worker = None
        self._build_ui()
        self._load_campaigns()

    def set_service(self, service: CampaignService):
        self._service = service

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        btn_new = QPushButton("حملة جديدة")
        btn_new.clicked.connect(self._new_campaign)
        actions.addWidget(btn_new)

        btn_view = QPushButton("عرض التفاصيل")
        btn_view.clicked.connect(self._view_campaign)
        actions.addWidget(btn_view)

        btn_delete = QPushButton("حذف")
        btn_delete.setObjectName("btnDanger")
        btn_delete.clicked.connect(self._delete_campaign)
        actions.addWidget(btn_delete)
        actions.addStretch()
        layout.addLayout(actions)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "الاسم", "الحالة", "إجمالي", "تم الإرسال", "فشل", "التاريخ"
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        control_group = QGroupBox("التحكم بالإرسال")
        control_layout = QHBoxLayout(control_group)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimumWidth(260)
        self._progress_bar.setVisible(False)
        control_layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        control_layout.addWidget(self._status_label)

        self._btn_start = QPushButton("بدء الإرسال")
        self._btn_start.setObjectName("btnSuccess")
        self._btn_start.clicked.connect(self._start_sending)
        control_layout.addWidget(self._btn_start)

        self._btn_pause = QPushButton("إيقاف مؤقت")
        self._btn_pause.clicked.connect(self._pause_sending)
        self._btn_pause.setEnabled(False)
        control_layout.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("إيقاف")
        self._btn_stop.setObjectName("btnDanger")
        self._btn_stop.clicked.connect(self._stop_sending)
        self._btn_stop.setEnabled(False)
        control_layout.addWidget(self._btn_stop)

        layout.addWidget(control_group)

        self._signals.progress_updated.connect(self._on_progress)
        self._signals.campaign_finished.connect(self._on_finished)

    def _load_campaigns(self):
        campaigns = self._service.get_all()
        self._table.setRowCount(len(campaigns))
        for i, c in enumerate(campaigns):
            self._table.setItem(i, 0, QTableWidgetItem(c.name))
            status_map = {
                CampaignStatus.DRAFT: "مسودة",
                CampaignStatus.RUNNING: "قيد الإرسال",
                CampaignStatus.PAUSED: "متوقف مؤقتاً",
                CampaignStatus.COMPLETED: "مكتمل",
                CampaignStatus.CANCELLED: "ملغي",
            }
            self._table.setItem(i, 1, QTableWidgetItem(status_map.get(c.status, c.status.value)))
            self._table.setItem(i, 2, QTableWidgetItem(str(c.total_messages)))
            self._table.setItem(i, 3, QTableWidgetItem(str(c.sent_count)))
            self._table.setItem(i, 4, QTableWidgetItem(str(c.failed_count)))
            self._table.setItem(i, 5, QTableWidgetItem(
                c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
            ))
            self._table.item(i, 0).setData(256, c.id)

    def refresh(self):
        self._load_campaigns()

    def _new_campaign(self):
        dialog = CampaignDialog(self, self._get_groups(), self._get_templates())
        if dialog.exec() == QDialog.Accepted:
            campaign = dialog.campaign
            saved = self._service.add(campaign)
            saved.template_content = campaign.template_content
            saved.group_name = campaign.group_name
            saved.delay_ms = campaign.delay_ms
            saved.max_retries = campaign.max_retries
            self._service.update(saved)
            saved, messages = self._service.prepare_campaign(saved)
            QMessageBox.information(
                self, "تم",
                f"تم إنشاء الحملة '{saved.name}' بنجاح\nإجمالي الرسائل: {saved.total_messages}"
            )
            self.refresh()

    def _view_campaign(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار حملة")
            return
        campaign_id = self._table.item(row, 0).data(256)
        campaign = self._service.get_by_id(campaign_id)
        if not campaign:
            return
        messages = self._service.get_messages(campaign_id)
        dialog = CampaignDetailDialog(campaign, messages, self)
        dialog.exec()

    def _delete_campaign(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار حملة")
            return
        campaign_id = self._table.item(row, 0).data(256)
        confirm = QMessageBox.question(self, "تأكيد", "هل أنت متأكد من حذف الحملة؟")
        if confirm == QMessageBox.Yes:
            self._service.delete(campaign_id)
            self.refresh()

    def _start_sending(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار حملة")
            return
        campaign_id = self._table.item(row, 0).data(256)
        campaign = self._service.get_by_id(campaign_id)
        if not campaign:
            return
        if self._running or campaign.status == CampaignStatus.RUNNING:
            QMessageBox.warning(self, "تنبيه", "الحملة قيد الإرسال بالفعل")
            return
        if campaign.total_messages == 0:
            QMessageBox.warning(self, "تنبيه", "لا توجد رسائل في هذه الحملة")
            return

        self._current_campaign_id = campaign_id
        self._running = True
        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._btn_pause.setText("إيقاف مؤقت")
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("جاري الإرسال...")

        self._thread = QThread(self)
        self._worker = CampaignWorker(self._service, campaign_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker_refs)
        self._thread.start()

    def _progress_callback(self, current, total, sent, failed):
        self._signals.progress_updated.emit(current, total, sent, failed)

    def _on_progress(self, current, total, sent, failed):
        if total > 0:
            pct = int(current / total * 100)
            self._progress_bar.setValue(pct)
        self._status_label.setText(f"تم: {sent} | فشل: {failed} | متبقي: {total - current}")
        self.refresh()

    def _on_finished(self, message="اكتمل الإرسال"):
        self._running = False
        self._current_campaign_id = None
        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_pause.setText("إيقاف مؤقت")
        self._progress_bar.setVisible(False)
        self._status_label.setText(message)
        self.refresh()

    def _on_failed(self, error):
        self._on_finished("فشل الإرسال")
        QMessageBox.critical(self, "خطأ", error)

    def _clear_worker_refs(self):
        self._thread = None
        self._worker = None

    def _pause_sending(self):
        if self._running:
            self._service.pause_campaign()
            self._btn_pause.setText("استئناف")
            self._btn_pause.clicked.disconnect()
            self._btn_pause.clicked.connect(self._resume_sending)
            self._status_label.setText("متوقف مؤقتاً")

    def _resume_sending(self):
        if self._running:
            self._service.resume_campaign()
            self._btn_pause.setText("إيقاف مؤقت")
            self._btn_pause.clicked.disconnect()
            self._btn_pause.clicked.connect(self._pause_sending)
            self._status_label.setText("جاري الإرسال...")

    def _stop_sending(self):
        if self._running:
            self._service.stop_campaign()
            self._btn_stop.setEnabled(False)
            self._btn_pause.setEnabled(False)
            self._status_label.setText("جاري إيقاف الإرسال...")


class CampaignDialog(QDialog):
    def __init__(self, parent, groups: list[str], templates: list[Template]):
        super().__init__(parent)
        self._groups = groups
        self._templates = templates
        self.setWindowTitle("حملة جديدة")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name_input = QLineEdit()
        form.addRow("اسم الحملة:", self._name_input)
        layout.addLayout(form)

        self._template_combo = QComboBox()
        self._template_combo.addItem("-- بدون قالب (كتابة يدوية) --", None)
        for t in self._templates:
            self._template_combo.addItem(t.name, t.id)
        self._template_combo.currentIndexChanged.connect(self._on_template_select)
        layout.addWidget(QLabel("القالب:"))
        layout.addWidget(self._template_combo)

        self._group_combo = QComboBox()
        self._group_combo.addItem("كل جهات الاتصال", None)
        for g in self._groups:
            self._group_combo.addItem(g, g)
        layout.addWidget(QLabel("مجموعة جهات الاتصال:"))
        layout.addWidget(self._group_combo)

        layout.addWidget(QLabel("نص الرسالة:"))
        self._content_input = QTextEdit()
        self._content_input.setMinimumHeight(120)
        layout.addWidget(self._content_input)

        self._info_label = QLabel("")
        layout.addWidget(self._info_label)
        self._content_input.textChanged.connect(self._update_info)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("التأخير بين الرسائل (مللي ثانية):"))
        self._delay_input = QSpinBox()
        self._delay_input.setRange(100, 60000)
        self._delay_input.setValue(1000)
        self._delay_input.setSuffix(" ms")
        delay_row.addWidget(self._delay_input)
        layout.addLayout(delay_row)

        retry_row = QHBoxLayout()
        retry_row.addWidget(QLabel("عدد محاولات إعادة الإرسال:"))
        self._retry_input = QSpinBox()
        self._retry_input.setRange(0, 10)
        self._retry_input.setValue(3)
        retry_row.addWidget(self._retry_input)
        layout.addLayout(retry_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_info()

    def _on_template_select(self):
        template_id = self._template_combo.currentData()
        if template_id:
            for t in self._templates:
                if t.id == template_id:
                    self._content_input.setPlainText(t.content)
                    break

    def _update_info(self):
        text = self._content_input.toPlainText()
        parts, per_part = estimate_sms_parts(text)
        self._info_label.setText(
            f"الأحرف: {len(text)} | الأجزاء: {parts}"
        )

    @property
    def campaign(self) -> Campaign:
        template_id = self._template_combo.currentData()
        return Campaign(
            name=self._name_input.text().strip() or "حملة جديدة",
            template_id=template_id,
            template_content=self._content_input.toPlainText(),
            group_name=self._group_combo.currentData(),
            delay_ms=self._delay_input.value(),
            max_retries=self._retry_input.value(),
        )


class CampaignDetailDialog(QDialog):
    def __init__(self, campaign: Campaign, messages: list[Message], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"تفاصيل الحملة: {campaign.name}")
        self.setMinimumSize(700, 500)
        self._build_ui(campaign, messages)

    def _build_ui(self, campaign: Campaign, messages: list[Message]):
        layout = QVBoxLayout(self)

        info = QLabel(
            f"<b>الحالة:</b> {campaign.status.value} | "
            f"<b>الإجمالي:</b> {campaign.total_messages} | "
            f"<b>تم:</b> {campaign.sent_count} | "
            f"<b>فشل:</b> {campaign.failed_count} | "
            f"<b>التأخير:</b> {campaign.delay_ms}ms"
        )
        layout.addWidget(info)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["الاسم", "رقم الهاتف", "الحالة", "المحاولات", "الخطأ"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setRowCount(len(messages))
        status_map = {
            "sent": "مرسل", "failed": "فاشل", "pending": "معلق",
            "queued": "في الانتظار", "sending": "جاري الإرسال",
        }
        for i, m in enumerate(messages):
            table.setItem(i, 0, QTableWidgetItem(m.contact_name))
            table.setItem(i, 1, QTableWidgetItem(m.phone))
            table.setItem(i, 2, QTableWidgetItem(status_map.get(m.status.value, m.status.value)))
            table.setItem(i, 3, QTableWidgetItem(str(m.retry_count)))
            table.setItem(i, 4, QTableWidgetItem(m.error_message))
        layout.addWidget(table)

        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
