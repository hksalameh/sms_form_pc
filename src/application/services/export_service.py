import os
from typing import Optional
from datetime import datetime
from openpyxl import Workbook
from src.domain.entities import Campaign, Message
from src.domain.interfaces import CampaignRepository, MessageRepository
from src.domain.enums import ExportFormat


class ExportService:
    def __init__(self, campaign_repo: CampaignRepository, message_repo: MessageRepository):
        self._campaign_repo = campaign_repo
        self._message_repo = message_repo

    def export_campaign_report(self, campaign_id: int, file_path: str,
                               fmt: ExportFormat = ExportFormat.EXCEL) -> str:
        campaign = self._campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise ValueError(f"الحملة {campaign_id} غير موجودة")
        messages = self._message_repo.get_by_campaign(campaign_id)
        return self._export(messages, file_path, fmt)

    def export_all_campaigns(self, file_path: str) -> str:
        wb = Workbook()
        ws = wb.active
        ws.title = "الحملات"
        ws.append(["المعرف", "الاسم", "الحالة", "إجمالي الرسائل", "تم الإرسال", "فشل", "تاريخ الإنشاء"])
        for c in self._campaign_repo.get_all():
            ws.append([c.id, c.name, c.status.value, c.total_messages, c.sent_count, c.failed_count,
                       c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""])
        wb.save(file_path)
        return file_path

    def _export(self, messages: list[Message], file_path: str, fmt: ExportFormat) -> str:
        if fmt == ExportFormat.EXCEL:
            return self._export_excel(messages, file_path)
        return self._export_pdf(messages, file_path)

    def _export_excel(self, messages: list[Message], file_path: str) -> str:
        wb = Workbook()
        ws = wb.active
        ws.title = "تقرير الرسائل"
        ws.append(["الاسم", "رقم الهاتف", "الحالة", "عدد الأجزاء", "الخطأ", "تاريخ الإرسال"])
        for m in messages:
            ws.append([
                m.contact_name, m.phone,
                {"sent": "مرسل", "failed": "فاشل", "pending": "معلق", "queued": "في الانتظار"}.get(m.status.value, m.status.value),
                m.parts, m.error_message,
                m.sent_at.strftime("%Y-%m-%d %H:%M:%S") if m.sent_at else "",
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
        status_map = {"sent": "مرسل", "failed": "فاشل", "pending": "معلق"}
        for m in messages:
            data.append([
                _ar(m.contact_name), _ar(m.phone),
                _ar(status_map.get(m.status.value, m.status.value)),
                _ar(m.error_message or ""),
            ])

        table = Table(data, colWidths=[120, 100, 80, 180])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        doc.build([Paragraph(_ar("تقرير الحملة"), styles["Title"]), table])
        return file_path

    def backup_database(self, backup_path: str) -> str:
        import shutil
        db_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "smscaster.db")
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
        return backup_path

    def restore_database(self, backup_path: str) -> str:
        import shutil
        db_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "smscaster.db")
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, db_path)
        return db_path
