import asyncio
from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.application.services.campaign_service import CampaignService
from src.application.sms.splitter import detect_encoding, estimate_sms_parts
from src.domain.entities import Campaign, Message, Template
from src.domain.enums import CampaignStatus


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
            asyncio.run(
                self._service.start_campaign(
                    self._campaign_id,
                    self.progress_updated.emit,
                )
            )
            operation = self._service.get_by_id(self._campaign_id)
            if operation and operation.status == CampaignStatus.CANCELLED:
                self.finished.emit("تم إيقاف الإرسال")
            elif operation and operation.status == CampaignStatus.PAUSED:
                self.finished.emit("توقفت عملية الإرسال مع رسائل معلقة")
            else:
                self.finished.emit("اكتمل الإرسال")
        except Exception as exc:
            self.failed.emit(str(exc))


class CampaignsWidget(QWidget):
    COMPOSER_PAGE = 0
    HISTORY_PAGE = 1

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
        self._templates: list[Template] = []
        self._build_ui()
        self._load_campaigns()
        self._reset_composer()

    def set_service(self, service: CampaignService):
        self._service = service

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        switcher = QHBoxLayout()
        switcher.setSpacing(8)

        self._btn_compose_mode = QPushButton("✉  رسالة جديدة")
        self._btn_compose_mode.setObjectName("workspaceModeButton")
        self._btn_compose_mode.setCheckable(True)
        self._btn_compose_mode.clicked.connect(self._show_composer)
        switcher.addWidget(self._btn_compose_mode)

        self._btn_history_mode = QPushButton("▤  عمليات الإرسال")
        self._btn_history_mode.setObjectName("workspaceModeButton")
        self._btn_history_mode.setCheckable(True)
        self._btn_history_mode.clicked.connect(self._show_history)
        switcher.addWidget(self._btn_history_mode)
        switcher.addStretch()
        layout.addLayout(switcher)

        self._workspace = QStackedWidget()
        self._workspace.setObjectName("sendWorkspace")
        self._workspace.addWidget(self._build_composer_page())
        self._workspace.addWidget(self._build_history_page())
        layout.addWidget(self._workspace, 1)

        self._signals.progress_updated.connect(self._on_progress)
        self._signals.campaign_finished.connect(self._on_finished)
        self._show_composer()

    def _build_composer_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("composerPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        form_card = QFrame()
        form_card.setObjectName("composerCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("إنشاء رسالة SMS")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        clear_btn = QPushButton("مسح الحقول")
        clear_btn.setObjectName("secondaryAction")
        clear_btn.clicked.connect(self._reset_composer)
        title_row.addWidget(clear_btn)
        form_layout.addLayout(title_row)

        name_row = QHBoxLayout()
        name_label = QLabel("اسم العملية")
        name_label.setObjectName("fieldLabel")
        name_row.addWidget(name_label)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("اختياري - سيتم إنشاء اسم تلقائي إذا تركته فارغًا")
        name_row.addWidget(self._name_input, 1)
        form_layout.addLayout(name_row)

        recipient_row = QHBoxLayout()
        recipient_label = QLabel("المستلمون")
        recipient_label.setObjectName("fieldLabel")
        recipient_row.addWidget(recipient_label)
        self._group_combo = QComboBox()
        self._group_combo.setMinimumWidth(280)
        recipient_row.addWidget(self._group_combo, 1)
        refresh_groups = QPushButton("تحديث المجموعات")
        refresh_groups.setObjectName("secondaryAction")
        refresh_groups.clicked.connect(self._reload_groups)
        recipient_row.addWidget(refresh_groups)
        form_layout.addLayout(recipient_row)

        template_row = QHBoxLayout()
        template_label = QLabel("القالب")
        template_label.setObjectName("fieldLabel")
        template_row.addWidget(template_label)
        self._template_combo = QComboBox()
        self._template_combo.currentIndexChanged.connect(self._on_template_select)
        template_row.addWidget(self._template_combo, 1)
        form_layout.addLayout(template_row)

        message_header = QHBoxLayout()
        message_label = QLabel("نص الرسالة")
        message_label.setObjectName("fieldLabel")
        message_header.addWidget(message_label)
        message_header.addStretch()

        self._variable_combo = QComboBox()
        self._variable_combo.addItem("الاسم", "{name}")
        self._variable_combo.addItem("رقم الهاتف", "{phone}")
        self._variable_combo.addItem("المجموعة", "{group}")
        self._variable_combo.addItem("الملاحظات", "{notes}")
        self._variable_combo.addItem("المعرف", "{id}")
        message_header.addWidget(self._variable_combo)

        insert_variable = QPushButton("إدراج متغير")
        insert_variable.setObjectName("secondaryAction")
        insert_variable.clicked.connect(self._insert_variable)
        message_header.addWidget(insert_variable)
        form_layout.addLayout(message_header)

        self._content_input = QTextEdit()
        self._content_input.setObjectName("messageEditor")
        self._content_input.setPlaceholderText("اكتب نص الرسالة هنا...")
        self._content_input.setMinimumHeight(180)
        self._content_input.textChanged.connect(self._update_message_info)
        form_layout.addWidget(self._content_input, 1)

        info_row = QHBoxLayout()
        self._encoding_label = QLabel("الترميز المتوقع: GSM-7")
        self._encoding_label.setObjectName("messageMeta")
        info_row.addWidget(self._encoding_label)
        info_row.addStretch()
        self._parts_label = QLabel("0 حرف | 1 SMS")
        self._parts_label.setObjectName("messageMetaStrong")
        info_row.addWidget(self._parts_label)
        form_layout.addLayout(info_row)

        layout.addWidget(form_card, 1)

        options_card = QGroupBox("خيارات الإرسال")
        options_layout = QHBoxLayout(options_card)
        options_layout.setContentsMargins(14, 12, 14, 12)
        options_layout.setSpacing(12)

        options_layout.addWidget(QLabel("الفاصل بين الرسائل:"))
        self._delay_input = QSpinBox()
        self._delay_input.setRange(100, 60000)
        self._delay_input.setValue(1000)
        self._delay_input.setSuffix(" ms")
        options_layout.addWidget(self._delay_input)

        options_layout.addWidget(QLabel("إعادة المحاولة:"))
        self._retry_input = QSpinBox()
        self._retry_input.setRange(0, 10)
        self._retry_input.setValue(3)
        self._retry_input.setSuffix(" مرة")
        options_layout.addWidget(self._retry_input)
        options_layout.addStretch()
        layout.addWidget(options_card)

        action_bar = QFrame()
        action_bar.setObjectName("composerActionBar")
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(14, 10, 14, 10)
        action_layout.addStretch()

        save_btn = QPushButton("حفظ في عمليات الإرسال")
        save_btn.setObjectName("secondaryAction")
        save_btn.clicked.connect(lambda: self._create_send_operation(False))
        action_layout.addWidget(save_btn)

        send_btn = QPushButton("▶  حفظ وبدء الإرسال")
        send_btn.setObjectName("btnSuccess")
        send_btn.clicked.connect(lambda: self._create_send_operation(True))
        action_layout.addWidget(send_btn)
        layout.addWidget(action_bar)

        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("historyPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        btn_new = QPushButton("✉  رسالة جديدة")
        btn_new.clicked.connect(self._new_campaign)
        actions.addWidget(btn_new)

        btn_view = QPushButton("عرض التفاصيل")
        btn_view.setObjectName("secondaryAction")
        btn_view.clicked.connect(self._view_campaign)
        actions.addWidget(btn_view)

        btn_delete = QPushButton("حذف عملية الإرسال")
        btn_delete.setObjectName("btnDanger")
        btn_delete.clicked.connect(self._delete_campaign)
        actions.addWidget(btn_delete)
        actions.addStretch()
        layout.addLayout(actions)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["العملية", "الحالة", "الإجمالي", "تم الإرسال", "فشل", "التاريخ"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.doubleClicked.connect(self._view_campaign)
        layout.addWidget(self._table, 1)

        control_group = QGroupBox("تنفيذ عملية الإرسال المحددة")
        control_layout = QHBoxLayout(control_group)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimumWidth(240)
        self._progress_bar.setVisible(False)
        control_layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        control_layout.addWidget(self._status_label)
        control_layout.addStretch()

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
        return page

    def _show_composer(self):
        self._workspace.setCurrentIndex(self.COMPOSER_PAGE)
        self._btn_compose_mode.setChecked(True)
        self._btn_history_mode.setChecked(False)
        self._reload_groups()
        self._reload_templates()

    def _show_history(self):
        self._workspace.setCurrentIndex(self.HISTORY_PAGE)
        self._btn_compose_mode.setChecked(False)
        self._btn_history_mode.setChecked(True)
        self._load_campaigns()

    def _reload_groups(self):
        current = self._group_combo.currentData() if self._group_combo.count() else None
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        self._group_combo.addItem("كل جهات الاتصال", None)
        for group_name in self._get_groups():
            self._group_combo.addItem(group_name, group_name)
        if current is not None:
            index = self._group_combo.findData(current)
            if index >= 0:
                self._group_combo.setCurrentIndex(index)
        self._group_combo.blockSignals(False)

    def _reload_templates(self):
        current = self._template_combo.currentData() if self._template_combo.count() else None
        self._templates = list(self._get_templates())
        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        self._template_combo.addItem("بدون قالب - كتابة يدوية", None)
        for template in self._templates:
            self._template_combo.addItem(template.name, template.id)
        if current is not None:
            index = self._template_combo.findData(current)
            if index >= 0:
                self._template_combo.setCurrentIndex(index)
        self._template_combo.blockSignals(False)

    def _on_template_select(self):
        template_id = self._template_combo.currentData()
        if not template_id:
            return
        for template in self._templates:
            if template.id == template_id:
                self._content_input.setPlainText(template.content)
                return

    def _insert_variable(self):
        token = self._variable_combo.currentData()
        if token:
            self._content_input.insertPlainText(token)
            self._content_input.setFocus()

    def _update_message_info(self):
        text = self._content_input.toPlainText()
        parts, _ = estimate_sms_parts(text)
        encoding = detect_encoding(text)
        encoding_text = "Unicode / عربي" if encoding == "ucs_2" else "GSM-7"
        self._encoding_label.setText(f"الترميز المتوقع: {encoding_text}")
        self._parts_label.setText(f"{len(text)} حرف | {parts} SMS")

    def _reset_composer(self):
        if not hasattr(self, "_name_input"):
            return
        self._name_input.clear()
        self._content_input.clear()
        self._delay_input.setValue(1000)
        self._retry_input.setValue(3)
        self._reload_groups()
        self._reload_templates()
        self._group_combo.setCurrentIndex(0)
        self._template_combo.setCurrentIndex(0)
        self._update_message_info()

    def _create_send_operation(self, start_now: bool):
        content = self._content_input.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "تنبيه", "اكتب نص الرسالة أولاً")
            self._content_input.setFocus()
            return

        name = self._name_input.text().strip()
        if not name:
            name = datetime.now().strftime("إرسال %Y-%m-%d %H:%M")

        operation = Campaign(
            name=name,
            template_id=self._template_combo.currentData(),
            template_content=content,
            group_name=self._group_combo.currentData(),
            delay_ms=self._delay_input.value(),
            max_retries=self._retry_input.value(),
        )

        try:
            saved = self._service.add(operation)
            saved.template_content = operation.template_content
            saved.group_name = operation.group_name
            saved.delay_ms = operation.delay_ms
            saved.max_retries = operation.max_retries
            self._service.update(saved)
            saved, _ = self._service.prepare_campaign(saved)
        except Exception as exc:
            QMessageBox.critical(self, "خطأ", f"تعذر حفظ عملية الإرسال:\n{exc}")
            return

        if saved.total_messages == 0:
            QMessageBox.warning(
                self,
                "لا يوجد مستلمون",
                "تم حفظ العملية، لكن لا توجد جهات اتصال ضمن الاختيار الحالي.",
            )
            self._show_history()
            self._select_operation_by_id(saved.id)
            return

        self._show_history()
        self._select_operation_by_id(saved.id)
        self._reset_composer()

        if start_now:
            self._start_sending_by_id(saved.id)
        else:
            QMessageBox.information(
                self,
                "تم الحفظ",
                f"تم حفظ عملية الإرسال بنجاح.\nعدد المستلمين: {saved.total_messages}",
            )

    def _load_campaigns(self):
        campaigns = self._service.get_all()
        self._table.setRowCount(len(campaigns))
        status_map = {
            CampaignStatus.DRAFT: "مسودة",
            CampaignStatus.RUNNING: "قيد الإرسال",
            CampaignStatus.PAUSED: "متوقف مؤقتاً",
            CampaignStatus.COMPLETED: "مكتمل",
            CampaignStatus.CANCELLED: "ملغي",
        }
        for row, operation in enumerate(campaigns):
            self._table.setItem(row, 0, QTableWidgetItem(operation.name))
            self._table.setItem(
                row,
                1,
                QTableWidgetItem(status_map.get(operation.status, operation.status.value)),
            )
            self._table.setItem(row, 2, QTableWidgetItem(str(operation.total_messages)))
            self._table.setItem(row, 3, QTableWidgetItem(str(operation.sent_count)))
            self._table.setItem(row, 4, QTableWidgetItem(str(operation.failed_count)))
            self._table.setItem(
                row,
                5,
                QTableWidgetItem(
                    operation.created_at.strftime("%Y-%m-%d %H:%M")
                    if operation.created_at
                    else ""
                ),
            )
            self._table.item(row, 0).setData(256, operation.id)

    def refresh(self):
        self._load_campaigns()
        if self._workspace.currentIndex() == self.COMPOSER_PAGE:
            self._reload_groups()
            self._reload_templates()

    def _new_campaign(self):
        self._reset_composer()
        self._show_composer()
        self._name_input.setFocus()

    def _selected_operation_id(self):
        row = self._table.currentRow()
        if row < 0 or not self._table.item(row, 0):
            return None
        return self._table.item(row, 0).data(256)

    def _select_operation_by_id(self, operation_id):
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.data(256) == operation_id:
                self._table.selectRow(row)
                return True
        return False

    def _view_campaign(self):
        campaign_id = self._selected_operation_id()
        if not campaign_id:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار عملية إرسال")
            return
        operation = self._service.get_by_id(campaign_id)
        if not operation:
            return
        messages = self._service.get_messages(campaign_id)
        dialog = CampaignDetailDialog(operation, messages, self)
        dialog.exec()

    def _delete_campaign(self):
        campaign_id = self._selected_operation_id()
        if not campaign_id:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار عملية إرسال")
            return

        operation = self._service.get_by_id(campaign_id)
        operation_name = operation.name if operation else "هذه العملية"
        confirm = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل تريد حذف عملية الإرسال '{operation_name}'؟\nسيتم حذف سجلها المرتبط بها.",
        )
        if confirm == QMessageBox.Yes:
            self._service.delete(campaign_id)
            self.refresh()

    def _start_sending(self):
        campaign_id = self._selected_operation_id()
        if not campaign_id:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار عملية إرسال")
            return
        self._start_sending_by_id(campaign_id)

    def _start_sending_by_id(self, campaign_id: int):
        operation = self._service.get_by_id(campaign_id)
        if not operation:
            return
        if self._running or operation.status == CampaignStatus.RUNNING:
            QMessageBox.warning(self, "تنبيه", "عملية الإرسال قيد التنفيذ بالفعل")
            return
        if operation.total_messages == 0:
            QMessageBox.warning(self, "تنبيه", "لا توجد رسائل ضمن عملية الإرسال هذه")
            return

        self._show_history()
        self._select_operation_by_id(campaign_id)
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
            self._progress_bar.setValue(int(current / total * 100))
        self._status_label.setText(
            f"تم: {sent} | فشل: {failed} | متبقي: {max(total - current, 0)}"
        )
        self._load_campaigns()
        if self._current_campaign_id:
            self._select_operation_by_id(self._current_campaign_id)

    def _on_finished(self, message="اكتمل الإرسال"):
        self._running = False
        finished_id = self._current_campaign_id
        self._current_campaign_id = None
        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_pause.setText("إيقاف مؤقت")
        self._progress_bar.setVisible(False)
        self._status_label.setText(message)
        self._load_campaigns()
        if finished_id:
            self._select_operation_by_id(finished_id)

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
            try:
                self._btn_pause.clicked.disconnect()
            except TypeError:
                pass
            self._btn_pause.clicked.connect(self._resume_sending)
            self._status_label.setText("متوقف مؤقتاً")

    def _resume_sending(self):
        if self._running:
            self._service.resume_campaign()
            self._btn_pause.setText("إيقاف مؤقت")
            try:
                self._btn_pause.clicked.disconnect()
            except TypeError:
                pass
            self._btn_pause.clicked.connect(self._pause_sending)
            self._status_label.setText("جاري الإرسال...")

    def _stop_sending(self):
        if self._running:
            self._service.stop_campaign()
            self._btn_stop.setEnabled(False)
            self._btn_pause.setEnabled(False)
            self._status_label.setText("جاري إيقاف الإرسال...")


class CampaignDetailDialog(QDialog):
    def __init__(self, campaign: Campaign, messages: list[Message], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"تفاصيل الإرسال: {campaign.name}")
        self.setMinimumSize(760, 520)
        self._build_ui(campaign, messages)

    def _build_ui(self, campaign: Campaign, messages: list[Message]):
        layout = QVBoxLayout(self)

        status_map = {
            CampaignStatus.DRAFT: "مسودة",
            CampaignStatus.RUNNING: "قيد الإرسال",
            CampaignStatus.PAUSED: "متوقف مؤقتاً",
            CampaignStatus.COMPLETED: "مكتمل",
            CampaignStatus.CANCELLED: "ملغي",
        }
        status_text = status_map.get(campaign.status, campaign.status.value)

        info = QLabel(
            f"<b>الحالة:</b> {status_text} | "
            f"<b>الإجمالي:</b> {campaign.total_messages} | "
            f"<b>تم:</b> {campaign.sent_count} | "
            f"<b>فشل:</b> {campaign.failed_count} | "
            f"<b>الفاصل:</b> {campaign.delay_ms}ms"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["الاسم", "رقم الهاتف", "الحالة", "المحاولات", "الخطأ"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(messages))
        message_status_map = {
            "sent": "مرسل",
            "failed": "فاشل",
            "pending": "معلق",
            "queued": "في الانتظار",
            "sending": "جاري الإرسال",
        }
        for row, message in enumerate(messages):
            table.setItem(row, 0, QTableWidgetItem(message.contact_name))
            table.setItem(row, 1, QTableWidgetItem(message.phone))
            table.setItem(
                row,
                2,
                QTableWidgetItem(
                    message_status_map.get(message.status.value, message.status.value)
                ),
            )
            table.setItem(row, 3, QTableWidgetItem(str(message.retry_count)))
            table.setItem(row, 4, QTableWidgetItem(message.error_message))
        layout.addWidget(table)

        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
