import asyncio
from typing import Optional, Callable
from src.domain.entities import Campaign, Message, Contact, Template
from src.domain.enums import CampaignStatus, MessageStatus
from src.domain.interfaces import CampaignRepository, MessageRepository, ContactRepository
from src.application.sms.queue_manager import QueueManager
from src.application.sms.throttler import AdaptiveThrottler
from src.application.sms.sender import SmsSender
from src.application.sms.splitter import split_message


class CampaignService:
    def __init__(
        self,
        campaign_repo: CampaignRepository,
        message_repo: MessageRepository,
        contact_repo: ContactRepository,
        sender: SmsSender,
    ):
        self._campaign_repo = campaign_repo
        self._message_repo = message_repo
        self._contact_repo = contact_repo
        self._sender = sender
        self._throttler = AdaptiveThrottler()
        self._queue_manager = QueueManager(
            message_repo=message_repo,
            campaign_repo=campaign_repo,
            send_fn=sender.send,
            throttler=self._throttler,
        )

    def add(self, campaign: Campaign) -> Campaign:
        return self._campaign_repo.add(campaign)

    def update(self, campaign: Campaign) -> bool:
        return self._campaign_repo.update(campaign)

    def get_all(self) -> list[Campaign]:
        return self._campaign_repo.get_all()

    def get_by_id(self, campaign_id: int) -> Optional[Campaign]:
        return self._campaign_repo.get_by_id(campaign_id)

    def delete(self, campaign_id: int) -> bool:
        return self._campaign_repo.delete(campaign_id)

    def get_messages(self, campaign_id: int) -> list[Message]:
        return self._message_repo.get_by_campaign(campaign_id)

    def prepare_campaign(self, campaign: Campaign) -> tuple[Campaign, list[Message]]:
        contacts = self._contact_repo.get_all(campaign.group_name)
        messages = []
        for contact in contacts:
            content = campaign.template_content
            content = content.replace("{name}", contact.name or "")
            content = content.replace("{phone}", contact.phone or "")
            content = content.replace("{notes}", contact.notes or "")
            content = content.replace("{group}", contact.group_name or "")
            content = content.replace("{id}", str(contact.id or ""))
            parts = len(split_message(content))
            msg = Message(
                campaign_id=campaign.id,
                contact_id=contact.id,
                contact_name=contact.name,
                phone=contact.phone,
                content=content,
                status=MessageStatus.PENDING,
                parts=parts,
                max_retries=campaign.max_retries,
            )
            messages.append(msg)

        campaign.total_messages = len(messages)
        if messages:
            self._message_repo.add_batch(messages)
        self._campaign_repo.update(campaign)
        return campaign, messages

    async def start_campaign(self, campaign_id: int,
                              progress_callback: Optional[Callable] = None) -> None:
        campaign = self._campaign_repo.get_by_id(campaign_id)
        if not campaign:
            return
        messages = self._message_repo.get_by_campaign(campaign_id)
        self._throttler.set_delay(campaign.delay_ms)
        self._queue_manager.set_progress_callback(progress_callback)
        await self._queue_manager.run(campaign, messages)

    def pause_campaign(self):
        self._queue_manager.pause()

    def resume_campaign(self):
        self._queue_manager.resume()

    def stop_campaign(self):
        self._queue_manager.stop()

    async def check_phone_health(self) -> tuple[bool, str]:
        return await self._sender.check_health()
