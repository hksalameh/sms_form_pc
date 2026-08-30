from enum import Enum, auto


class MessageEncoding(Enum):
    GSM_7 = "gsm_7"
    UCS_2 = "ucs_2"


class MessageStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    PARTIALLY_SENT = "partially_sent"


class CampaignStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExportFormat(Enum):
    EXCEL = "excel"
    PDF = "pdf"


class ContactImportSource(Enum):
    MANUAL = "manual"
    TXT = "txt"
    CSV = "csv"
