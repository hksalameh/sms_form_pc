import os
from openpyxl import Workbook

from src.domain.entities import Message
from src.domain.interfaces import CampaignRepository, MessageRepository
from src.domain.enums import ExportFormat
from src.infrastructure.database.connection import DB_PATH


class ExportService:
    def __init__(self, campaign_repo: CampaignRepository, message_repo: MessageRepository):
        self._campaign_repo = campaign_repo
        self._message_repo = message_repo

    def get_campaign_messages(self, campaign_id: int) -> list[Message]:
        return self._message_repo.get_by_campaign(campaign_id)

    def export_campaign_report(self, campaign_id: int, file_path: str,
                               fmt: ExportFormat = ExportFormat.EXCEL) -> str:
        operation = self._campaign_repo.get_by_id(campaign_id)
        if not operation:
            raise ValueError(f"عملية الإرسال {campaign_id} غير موجودة")
        messages = self._message_repo.get_by_campaign(campaign_id)
        return self._export(messages, file_path, fmt)

    def export_all_campaigns(self, file_path: str) -> str:
        wb = Workbook()
        ws = wb.active
        ws.title = "عمليات الإرسال"
        ws.append([
            "المعرف", "الاسم", "الحالة", "إجمالي الرسائل",
            "تم الإرسال", "فشل", "تاريخ الإنشاء"
        ])
        for operation in self._campaign_repo.get_all():
            ws.append([
                operation.id,
                operation.name,
                operation.status.value,
                operation.total_messages,
                operation.sent_count,
                operation.failed_count,
                operation.created_at.strftime("%Y-%m-%d %H:%M")
                if operation.created_at else "",
            ])
        wb.save(file_path)
        return file_path

    def _export(self, messages: list[Message], file_path: str, fmt: ExportFormat) -> str:
        if fmt == ExportFormat.EXCEL:
            return self._export_excel(messages, file_path)
        return self._export_pdf(messages, file_path)

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

    def _export_excel(self, messages: list[Message], file_path: str) -> str:
        wb = Workbook()
        ws = wb.active
        ws.title = "تقرير الرسائل"
        ws.append([
            "الاسم", "رقم الهاتف", "الحالة", "عدد الأجزاء",
            "المحاولات", "الخطأ", "تاريخ الإرسال"
        ])
        for message in messages:
            ws.append([
                message.contact_name,
                message.phone,
                self._status_text(message.status.value),
                message.parts,
                message.retry_count,
                message.error_message,
                message.sent_at.strftime("%Y-%m-%d %H:%M:%S")
                if message.sent_at else "",
            ])
        wb.save(file_path)
        return file_path

    def _export_pdf(self, messages: list[Message], file_path: str) -> str:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        import arabic_reshaper
        from bidi.algorithm import get_display

        doc = SimpleDocTemplate(file_path, pagesize=A4)
        styles = getSampleStyleSheet()

        def _ar(text: str) -> str:
            return get_display(arabic_reshaper.reshape(str(text)))

        data = [[_ar("الاسم"), _ar("رقم الهاتف"), _ar("الحالة"), _ar("ملاحظات")]]
        for message in messages:
            data.append([
                _ar(message.contact_name),
                _ar(message.phone),
                _ar(self._status_text(message.status.value)),
                _ar(message.error_message or ""),
            ])

        table = Table(data, colWidths=[120, 100, 80, 180])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        doc.build([Paragraph(_ar("تقرير عملية الإرسال"), styles["Title"]), table])
        return file_path

    def backup_database(self, backup_path: str) -> str:
        import shutil

        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, backup_path)
        return backup_path

    def restore_database(self, backup_path: str) -> str:
        import shutil

        if os.path.exists(backup_path):
            shutil.copy2(backup_path, DB_PATH)
        return DB_PATH
