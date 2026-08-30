from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView, QMessageBox,
    QGroupBox, QFileDialog, QComboBox, QLineEdit, QFrame,
)

from src.domain.enums import ExportFormat
from src.application.services.export_service import ExportService


class ReportsWidget(QWidget):
    STATUS_OPTIONS = [
        ("كل الحالات", None),
        ("مرسل", "sent"),
        ("فاشل", "failed"),
        ("معلق", "pending"),
        ("في الانتظار", "queued"),
        ("جاري الإرسال", "sending"),
        ("مرسل جزئياً", "partially_sent"),
    ]

    def __init__(self, service: ExportService, get_campaigns_fn):
        super().__init__()
        self._service = service
        self._get_campaigns = get_campaigns_fn
        self._messages = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        selection_row = QHBoxLayout()
        selection_row.addWidget(QLabel("عملية الإرسال:"))
        self._campaign_combo = QComboBox()
        self._campaign_combo.setMinimumWidth(280)
        self._campaign_combo.currentIndexChanged.connect(self._load_selected_operation)
        selection_row.addWidget(self._campaign_combo, 1)

        btn_export_excel = QPushButton("تصدير Excel")
        btn_export_excel.clicked.connect(lambda: self._export(ExportFormat.EXCEL))
        selection_row.addWidget(btn_export_excel)

        btn_export_pdf = QPushButton("تصدير PDF")
        btn_export_pdf.clicked.connect(lambda: self._export(ExportFormat.PDF))
        selection_row.addWidget(btn_export_pdf)

        btn_all = QPushButton("تصدير كل العمليات")
        btn_all.setObjectName("secondaryAction")
        btn_all.clicked.connect(self._export_all)
        selection_row.addWidget(btn_all)
        layout.addLayout(selection_row)

        summary = QFrame()
        summary.setObjectName("reportSummary")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(18)

        self._total_label = QLabel("الإجمالي: 0")
        self._sent_label = QLabel("تم الإرسال: 0")
        self._failed_label = QLabel("فشل: 0")
        self._waiting_label = QLabel("معلق/انتظار: 0")
        for label in (
            self._total_label,
            self._sent_label,
            self._failed_label,
            self._waiting_label,
        ):
            label.setObjectName("reportMetric")
            summary_layout.addWidget(label)
        summary_layout.addStretch()
        layout.addWidget(summary)

        filters = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("بحث بالاسم أو رقم الهاتف...")
        self._search_input.textChanged.connect(self._apply_filters)
        filters.addWidget(self._search_input, 1)

        filters.addWidget(QLabel("الحالة:"))
        self._status_combo = QComboBox()
        for label, value in self.STATUS_OPTIONS:
            self._status_combo.addItem(label, value)
        self._status_combo.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(self._status_combo)

        btn_refresh = QPushButton("تحديث")
        btn_refresh.setObjectName("secondaryAction")
        btn_refresh.clicked.connect(self._load_selected_operation)
        filters.addWidget(btn_refresh)
        layout.addLayout(filters)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "الاسم",
            "رقم الهاتف",
            "الحالة",
            "الأجزاء",
            "المحاولات",
            "تاريخ الإرسال",
            "الخطأ",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        self._visible_count = QLabel("الرسائل الظاهرة: 0")
        self._visible_count.setObjectName("messageMeta")
        layout.addWidget(self._visible_count)

        backup_group = QGroupBox("النسخ الاحتياطي لقاعدة البيانات")
        backup_layout = QHBoxLayout(backup_group)
        backup_layout.addWidget(QLabel(
            "يمكنك حفظ نسخة من بيانات جهات الاتصال وعمليات الإرسال واستعادتها لاحقاً."
        ))
        backup_layout.addStretch()

        btn_backup = QPushButton("إنشاء نسخة احتياطية")
        btn_backup.clicked.connect(self._backup)
        backup_layout.addWidget(btn_backup)

        btn_restore = QPushButton("استعادة نسخة احتياطية")
        btn_restore.setObjectName("btnWarning")
        btn_restore.clicked.connect(self._restore)
        backup_layout.addWidget(btn_restore)
        layout.addWidget(backup_group)

    @staticmethod
    def _status_text(value: str) -> str:
        return {
            "sent": "مرسل",
            "failed": "فاشل",
            "pending": "معلق",
            "queued": "في الانتظار",
            "sending": "جاري الإرسال",
            "partially_sent": "مرسل جزئياً",
        }.get(value, value)

    def refresh(self):
        current_id = self._campaign_combo.currentData()
        self._campaign_combo.blockSignals(True)
        self._campaign_combo.clear()
        for operation in self._get_campaigns():
            date_text = operation.created_at.strftime("%Y-%m-%d %H:%M") if operation.created_at else ""
            self._campaign_combo.addItem(f"{operation.name}  •  {date_text}", operation.id)

        if current_id is not None:
            index = self._campaign_combo.findData(current_id)
            if index >= 0:
                self._campaign_combo.setCurrentIndex(index)
        self._campaign_combo.blockSignals(False)
        self._load_selected_operation()

    def _load_selected_operation(self):
        campaign_id = self._campaign_combo.currentData()
        self._messages = (
            self._service.get_campaign_messages(campaign_id)
            if campaign_id
            else []
        )
        self._update_summary()
        self._apply_filters()

    def _update_summary(self):
        total = len(self._messages)
        sent = sum(1 for message in self._messages if message.status.value == "sent")
        failed = sum(1 for message in self._messages if message.status.value == "failed")
        waiting = sum(
            1 for message in self._messages
            if message.status.value in {"pending", "queued", "sending"}
        )
        self._total_label.setText(f"الإجمالي: {total}")
        self._sent_label.setText(f"تم الإرسال: {sent}")
        self._failed_label.setText(f"فشل: {failed}")
        self._waiting_label.setText(f"معلق/انتظار: {waiting}")

    def _apply_filters(self):
        query = self._search_input.text().strip().lower()
        status_filter = self._status_combo.currentData()

        visible = []
        for message in self._messages:
            if status_filter and message.status.value != status_filter:
                continue
            if query:
                haystack = f"{message.contact_name} {message.phone}".lower()
                if query not in haystack:
                    continue
            visible.append(message)

        self._table.setRowCount(len(visible))
        for row, message in enumerate(visible):
            values = [
                message.contact_name,
                message.phone,
                self._status_text(message.status.value),
                str(message.parts),
                str(message.retry_count),
                message.sent_at.strftime("%Y-%m-%d %H:%M:%S") if message.sent_at else "",
                message.error_message or "",
            ]
            for column, value in enumerate(values):
                self._table.setItem(row, column, QTableWidgetItem(value))

        self._visible_count.setText(f"الرسائل الظاهرة: {len(visible)} من {len(self._messages)}")

    def _export(self, fmt: ExportFormat):
        campaign_id = self._campaign_combo.currentData()
        if not campaign_id:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار عملية إرسال")
            return
        ext = "xlsx" if fmt == ExportFormat.EXCEL else "pdf"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ التقرير",
            f"sms_report.{ext}",
            f"*.{ext}",
        )
        if not path:
            return
        self._service.export_campaign_report(campaign_id, path, fmt)
        QMessageBox.information(self, "تصدير", f"تم حفظ التقرير في:\n{path}")

    def _export_all(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ التقرير",
            "send_operations.xlsx",
            "Excel (*.xlsx)",
        )
        if not path:
            return
        self._service.export_all_campaigns(path)
        QMessageBox.information(self, "تصدير", f"تم حفظ التقرير في:\n{path}")

    def _backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ النسخة الاحتياطية",
            "smscaster_backup.db",
            "Database (*.db)",
        )
        if not path:
            return
        self._service.backup_database(path)
        QMessageBox.information(self, "نسخ احتياطي", f"تم إنشاء النسخة في:\n{path}")

    def _restore(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "اختيار نسخة احتياطية",
            "",
            "Database (*.db)",
        )
        if not path:
            return
        confirm = QMessageBox.question(
            self,
            "تأكيد",
            "هل أنت متأكد من استعادة النسخة الاحتياطية؟\nسيتم استبدال البيانات الحالية، ثم يجب إعادة تشغيل البرنامج.",
        )
        if confirm == QMessageBox.Yes:
            self._service.restore_database(path)
            QMessageBox.information(
                self,
                "استعادة",
                "تمت استعادة قاعدة البيانات. أغلق البرنامج وافتحه من جديد لتحديث جميع البيانات.",
            )
