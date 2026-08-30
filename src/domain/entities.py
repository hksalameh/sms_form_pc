from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from .enums import CampaignStatus, MessageStatus, ContactImportSource


@dataclass
class Contact:
    id: Optional[int] = None
    name: str = ""
    phone: str = ""
    group_name: str = "عام"
    notes: str = ""
    import_source: ContactImportSource = ContactImportSource.MANUAL
    created_at: datetime = field(default_factory=datetime.now)

    def validate(self) -> list[str]:
        errors = []
        if not self.phone.strip():
            errors.append("رقم الهاتف مطلوب")
        elif not self.phone.strip().isdigit():
            errors.append("رقم الهاتف يجب أن يحتوي على أرقام فقط")
        return errors


@dataclass
class Template:
    id: Optional[int] = None
    name: str = ""
    content: str = ""
    merge_fields: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def estimate_parts(self, encoding: str = "auto") -> tuple[int, int]:
        from ..application.sms.splitter import estimate_sms_parts
        return estimate_sms_parts(self.content, encoding)

    def render(self, contact: Contact) -> str:
        content = self.content
        fields = {
            "{name}": contact.name or "",
            "{phone}": contact.phone or "",
            "{notes}": contact.notes or "",
            "{group}": contact.group_name or "",
        }
        for key, val in fields.items():
            content = content.replace(key, val)
        return content

    def detect_merge_fields(self) -> list[str]:
        import re
        return re.findall(r"\{(\w+)\}", self.content)


@dataclass
class Campaign:
    id: Optional[int] = None
    name: str = ""
    template_id: Optional[int] = None
    template_content: str = ""
    group_name: Optional[str] = None
    status: CampaignStatus = CampaignStatus.DRAFT
    total_messages: int = 0
    sent_count: int = 0
    failed_count: int = 0
    delay_ms: int = 1000
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class Message:
    id: Optional[int] = None
    campaign_id: Optional[int] = None
    contact_id: Optional[int] = None
    contact_name: str = ""
    phone: str = ""
    content: str = ""
    status: MessageStatus = MessageStatus.PENDING
    parts: int = 1
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None


@dataclass
class PhoneConfig:
    ip_address: str = "192.168.42.129"
    port: int = 8000
    timeout_ms: int = 30000
    api_token: str = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.ip_address}:{self.port}"

    def health_check_endpoint(self) -> str:
        return f"{self.base_url}/health"

    def send_endpoint(self) -> str:
        return f"{self.base_url}/send"
