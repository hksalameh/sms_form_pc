from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, relationship
from src.domain.enums import CampaignStatus, MessageStatus, ContactImportSource


class Base(DeclarativeBase):
    pass


class ContactModel(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), default="", index=True)
    phone = Column(String(50), nullable=False, index=True)
    group_name = Column(String(255), default="عام", index=True)
    notes = Column(Text, default="")
    import_source = Column(SAEnum(ContactImportSource), default=ContactImportSource.MANUAL)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_contact_group_phone", "group_name", "phone"),
    )


class TemplateModel(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CampaignModel(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    template_content = Column(Text, default="")
    group_name = Column(String(255), nullable=True)
    status = Column(SAEnum(CampaignStatus), default=CampaignStatus.DRAFT)
    total_messages = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    delay_ms = Column(Integer, default=1000)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    messages = relationship("MessageModel", back_populates="campaign", cascade="all, delete-orphan")


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    contact_name = Column(String(255), default="")
    phone = Column(String(50), nullable=False, index=True)
    content = Column(Text, default="")
    status = Column(SAEnum(MessageStatus), default=MessageStatus.PENDING, index=True)
    parts = Column(Integer, default=1)
    error_message = Column(Text, default="")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.now)
    sent_at = Column(DateTime, nullable=True)

    campaign = relationship("CampaignModel", back_populates="messages")

    __table_args__ = (
        Index("idx_msg_campaign_status", "campaign_id", "status"),
    )


class AppSettingsModel(Base):
    __tablename__ = "app_settings"

    key = Column(String(255), primary_key=True)
    value = Column(Text, default="")
