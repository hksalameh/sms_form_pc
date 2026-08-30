from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView, QMessageBox,
    QGroupBox, QFileDialog, QComboBox,
)
from src.domain.enums import ExportFormat
from src.application.services.export_service import ExportService


class ReportsWidget(QWidget):
    def __init__(self, service: ExportService, get_campaigns_fn):
        super().__init__()
        self._service = service
        self._get_campaigns = get_campaigns_fn
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        actions = QHBoxLayout()
        self._campaign_combo = QComboBox()
        self._campaign_combo.setMinimumWidth(250)
        actions.addWidget(QLabel("اختر الحملة:"))
        actions.addWidget(self._campaign_combo)

        btn_export_excel = QPushButton("تصدير تقرير Excel")
        btn_export_excel.clicked.connect(lambda: self._export(ExportFormat.EXCEL))
        actions.addWidget(btn_export_excel)

        btn_export_pdf = QPushButton("تصدير تقرير PDF")
        btn_export_pdf.clicked.connect(lambda: self._export(ExportFormat.PDF))
        actions.addWidget(btn_export_pdf)

        btn_all = QPushButton("تصدير جميع الحملات")
        btn_all.clicked.connect(self._export_all)
        actions.addWidget(btn_all)
        layout.addLayout(actions)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "الاسم", "رقم الهاتف", "الحالة", "عدد الأجزاء", "تاريخ الإرسال"
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        backup_group = QGroupBox("النسخ الاحتياطي لقاعدة البيانات")
        backup_layout = QHBoxLayout(backup_group)
        btn_backup = QPushButton("إنشاء نسخة احتياطية")
        btn_backup.clicked.connect(self._backup)
        backup_layout.addWidget(btn_backup)
        btn_restore = QPushButton("استعادة نسخة احتياطية")
        btn_restore.setObjectName("btnWarning")
        btn_restore.clicked.connect(self._restore)
        backup_layout.addWidget(btn_restore)
        layout.addWidget(backup_group)

    def refresh(self):
        self._campaign_combo.clear()
        for c in self._get_campaigns():
            label = f"{c.name} ({c.created_at.strftime('%Y-%m-%d') if c.created_at else ''})"
            self._campaign_combo.addItem(label, c.id)

    def _export(self, fmt: ExportFormat):
        campaign_id = self._campaign_combo.currentData()
        if not campaign_id:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار حملة")
            return
        ext = "xlsx" if fmt == ExportFormat.EXCEL else "pdf"
        path, _ = QFileDialog.getSaveFileName(self, "حفظ التقرير", f"report.{ext}", f"*.{ext}")
        if not path:
            return
        self._service.export_campaign_report(campaign_id, path, fmt)
        QMessageBox.information(self, "تصدير", f"تم حفظ التقرير في:\n{path}")

    def _export_all(self):
        path, _ = QFileDialog.getSaveFileName(self, "حفظ التقرير", "all_campaigns.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        self._service.export_all_campaigns(path)
        QMessageBox.information(self, "تصدير", f"تم حفظ التقرير في:\n{path}")

    def _backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ النسخة الاحتياطية", "smscaster_backup.db", "Database (*.db)"
        )
        if not path:
            return
        self._service.backup_database(path)
        QMessageBox.information(self, "نسخ احتياطي", f"تم إنشاء النسخة في:\n{path}")

    def _restore(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "اختيار نسخة احتياطية", "", "Database (*.db)"
        )
        if not path:
            return
        confirm = QMessageBox.question(
            self, "تأكيد",
            "هل أنت متأكد من استعادة النسخة الاحتياطية؟\nسيتم فقدان البيانات الحالية!"
        )
        if confirm == QMessageBox.Yes:
            self._service.restore_database(path)
            QMessageBox.information(self, "استعادة", "تمت استعادة قاعدة البيانات بنجاح")
