from typing import Optional
from sqlalchemy import func, or_
from src.domain.entities import Contact, Template, Campaign, Message
from src.domain.enums import CampaignStatus, MessageStatus, ContactImportSource
from src.domain.interfaces import (
    ContactRepository, TemplateRepository,
    CampaignRepository, MessageRepository,
)
from .models import ContactModel, TemplateModel, CampaignModel, MessageModel, AppSettingsModel
from .connection import get_session


class SQLContactRepository(ContactRepository):
    def add(self, contact: Contact) -> Contact:
        with get_session() as session:
            model = self._to_model(contact)
            session.add(model)
            session.flush()
            contact.id = model.id
            contact.created_at = model.created_at
            return contact

    def get_by_id(self, contact_id: int) -> Optional[Contact]:
        with get_session() as session:
            model = session.get(ContactModel, contact_id)
            return self._from_model(model) if model else None

    def get_all(self, group: Optional[str] = None) -> list[Contact]:
        with get_session() as session:
            query = session.query(ContactModel)
            if group:
                query = query.filter(ContactModel.group_name == group)
            return [self._from_model(m) for m in query.order_by(ContactModel.created_at.desc()).all()]

    def get_groups(self) -> list[str]:
        with get_session() as session:
            rows = session.query(ContactModel.group_name).distinct().order_by(ContactModel.group_name).all()
            return [r[0] for r in rows]

    def update(self, contact: Contact) -> bool:
        with get_session() as session:
            model = session.get(ContactModel, contact.id)
            if not model:
                return False
            model.name = contact.name
            model.phone = contact.phone
            model.group_name = contact.group_name
            model.notes = contact.notes
            return True

    def delete(self, contact_id: int) -> bool:
        with get_session() as session:
            model = session.get(ContactModel, contact_id)
            if not model:
                return False
            session.delete(model)
            return True

    def delete_all(self) -> int:
        with get_session() as session:
            count = session.query(ContactModel).delete()
            return count

    def delete_group(self, group_name: str) -> int:
        with get_session() as session:
            count = session.query(ContactModel).filter(
                ContactModel.group_name == group_name
            ).delete()
            return count

    def count(self, group: Optional[str] = None) -> int:
        with get_session() as session:
            query = session.query(func.count(ContactModel.id))
            if group:
                query = query.filter(ContactModel.group_name == group)
            return query.scalar() or 0

    def bulk_add(self, contacts: list[Contact]) -> list[Contact]:
        with get_session() as session:
            models = [self._to_model(c) for c in contacts]
            session.add_all(models)
            session.flush()
            for contact, model in zip(contacts, models):
                contact.id = model.id
                contact.created_at = model.created_at
            return contacts

    def search(self, query_str: str) -> list[Contact]:
        with get_session() as session:
            q = f"%{query_str}%"
            results = session.query(ContactModel).filter(
                or_(
                    ContactModel.name.like(q),
                    ContactModel.phone.like(q),
                    ContactModel.group_name.like(q),
                )
            ).order_by(ContactModel.name).all()
            return [self._from_model(m) for m in results]

    def _to_model(self, c: Contact) -> ContactModel:
        return ContactModel(
            name=c.name, phone=c.phone, group_name=c.group_name,
            notes=c.notes, import_source=c.import_source or ContactImportSource.MANUAL,
        )

    def _from_model(self, m: ContactModel) -> Contact:
        return Contact(
            id=m.id, name=m.name, phone=m.phone, group_name=m.group_name,
            notes=m.notes, import_source=m.import_source, created_at=m.created_at,
        )


class SQLTemplateRepository(TemplateRepository):
    def add(self, template: Template) -> Template:
        with get_session() as session:
            model = TemplateModel(name=template.name, content=template.content)
            session.add(model)
            session.flush()
            template.id = model.id
            template.created_at = model.created_at
            template.updated_at = model.updated_at
            return template

    def get_by_id(self, template_id: int) -> Optional[Template]:
        with get_session() as session:
            model = session.get(TemplateModel, template_id)
            return self._from_model(model) if model else None

    def get_all(self) -> list[Template]:
        with get_session() as session:
            return [self._from_model(m) for m in session.query(TemplateModel).order_by(TemplateModel.name).all()]

    def update(self, template: Template) -> bool:
        with get_session() as session:
            model = session.get(TemplateModel, template.id)
            if not model:
                return False
            model.name = template.name
            model.content = template.content
            return True

    def delete(self, template_id: int) -> bool:
        with get_session() as session:
            model = session.get(TemplateModel, template_id)
            if not model:
                return False
            session.delete(model)
            return True

    def _from_model(self, m: TemplateModel) -> Template:
        return Template(id=m.id, name=m.name, content=m.content, created_at=m.created_at, updated_at=m.updated_at)


class SQLCampaignRepository(CampaignRepository):
    def add(self, campaign: Campaign) -> Campaign:
        with get_session() as session:
            model = CampaignModel(
                name=campaign.name, template_id=campaign.template_id,
                template_content=campaign.template_content, group_name=campaign.group_name,
                status=campaign.status, total_messages=campaign.total_messages,
                delay_ms=campaign.delay_ms, max_retries=campaign.max_retries,
            )
            session.add(model)
            session.flush()
            campaign.id = model.id
            campaign.created_at = model.created_at
            return campaign

    def get_by_id(self, campaign_id: int) -> Optional[Campaign]:
        with get_session() as session:
            model = session.get(CampaignModel, campaign_id)
            return self._from_model(model) if model else None

    def get_all(self) -> list[Campaign]:
        with get_session() as session:
            return [self._from_model(m) for m in session.query(CampaignModel).order_by(CampaignModel.created_at.desc()).all()]

    def update(self, campaign: Campaign) -> bool:
        with get_session() as session:
            model = session.get(CampaignModel, campaign.id)
            if not model:
                return False
            model.name = campaign.name
            model.template_id = campaign.template_id
            model.template_content = campaign.template_content
            model.group_name = campaign.group_name
            model.status = campaign.status
            model.total_messages = campaign.total_messages
            model.sent_count = campaign.sent_count
            model.failed_count = campaign.failed_count
            model.delay_ms = campaign.delay_ms
            model.max_retries = campaign.max_retries
            model.started_at = campaign.started_at
            model.completed_at = campaign.completed_at
            return True

    def delete(self, campaign_id: int) -> bool:
        with get_session() as session:
            model = session.get(CampaignModel, campaign_id)
            if not model:
                return False
            session.delete(model)
            return True

    def _from_model(self, m: CampaignModel) -> Campaign:
        return Campaign(
            id=m.id, name=m.name, template_id=m.template_id,
            template_content=m.template_content, group_name=m.group_name,
            status=m.status, total_messages=m.total_messages,
            sent_count=m.sent_count, failed_count=m.failed_count,
            delay_ms=m.delay_ms, max_retries=m.max_retries,
            created_at=m.created_at, started_at=m.started_at, completed_at=m.completed_at,
        )


class SQLMessageRepository(MessageRepository):
    def add(self, message: Message) -> Message:
        with get_session() as session:
            model = self._to_model(message)
            session.add(model)
            session.flush()
            message.id = model.id
            message.created_at = model.created_at
            return message

    def add_batch(self, messages: list[Message]) -> list[Message]:
        with get_session() as session:
            models = [self._to_model(m) for m in messages]
            session.add_all(models)
            session.flush()
            for msg, model in zip(messages, models):
                msg.id = model.id
                msg.created_at = model.created_at
            return messages

    def get_by_id(self, message_id: int) -> Optional[Message]:
        with get_session() as session:
            model = session.get(MessageModel, message_id)
            return self._from_model(model) if model else None

    def get_by_campaign(self, campaign_id: int) -> list[Message]:
        with get_session() as session:
            models = session.query(MessageModel).filter(
                MessageModel.campaign_id == campaign_id
            ).order_by(MessageModel.id).all()
            return [self._from_model(m) for m in models]

    def update(self, message: Message) -> bool:
        with get_session() as session:
            model = session.get(MessageModel, message.id)
            if not model:
                return False
            model.status = message.status
            model.error_message = message.error_message
            model.retry_count = message.retry_count
            model.sent_at = message.sent_at
            return True

    def update_batch(self, messages: list[Message]) -> bool:
        with get_session() as session:
            for message in messages:
                model = session.get(MessageModel, message.id)
                if model:
                    model.status = message.status
                    model.error_message = message.error_message
                    model.retry_count = message.retry_count
                    model.sent_at = message.sent_at
            return True

    def get_pending(self, limit: int = 50) -> list[Message]:
        with get_session() as session:
            models = session.query(MessageModel).filter(
                MessageModel.status.in_([MessageStatus.PENDING, MessageStatus.QUEUED])
            ).order_by(MessageModel.id).limit(limit).all()
            return [self._from_model(m) for m in models]

    def count_by_status(self, campaign_id: int) -> dict:
        with get_session() as session:
            rows = session.query(
                MessageModel.status, func.count(MessageModel.id)
            ).filter(MessageModel.campaign_id == campaign_id).group_by(MessageModel.status).all()
            return {str(r[0].value): r[1] for r in rows}

    def _to_model(self, m: Message) -> MessageModel:
        return MessageModel(
            campaign_id=m.campaign_id, contact_id=m.contact_id,
            contact_name=m.contact_name, phone=m.phone, content=m.content,
            status=m.status, parts=m.parts, error_message=m.error_message,
            retry_count=m.retry_count, max_retries=m.max_retries,
        )

    def _from_model(self, m: MessageModel) -> Message:
        return Message(
            id=m.id, campaign_id=m.campaign_id, contact_id=m.contact_id,
            contact_name=m.contact_name, phone=m.phone, content=m.content,
            status=m.status, parts=m.parts, error_message=m.error_message,
            retry_count=m.retry_count, max_retries=m.max_retries,
            created_at=m.created_at, sent_at=m.sent_at,
        )


class SettingsRepository:
    def get(self, key: str, default: str = "") -> str:
        with get_session() as session:
            model = session.get(AppSettingsModel, key)
            return model.value if model else default

    def set(self, key: str, value: str) -> None:
        with get_session() as session:
            model = session.get(AppSettingsModel, key)
            if model:
                model.value = value
            else:
                session.add(AppSettingsModel(key=key, value=value))
