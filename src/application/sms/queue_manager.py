import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable
from src.domain.entities import Message, Campaign
from src.domain.enums import MessageStatus, CampaignStatus
from src.domain.interfaces import MessageRepository, CampaignRepository
from .throttler import AdaptiveThrottler

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(
        self,
        message_repo: MessageRepository,
        campaign_repo: CampaignRepository,
        send_fn: Callable,
        throttler: AdaptiveThrottler,
    ):
        self._message_repo = message_repo
        self._campaign_repo = campaign_repo
        self._send_fn = send_fn
        self._throttler = throttler
        self._running = False
        self._paused = False
        self._current_campaign_id: Optional[int] = None
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Optional[Callable]):
        self._progress_callback = callback

    async def run(self, campaign: Campaign, messages: list[Message]):
        self._running = True
        self._paused = False
        self._current_campaign_id = campaign.id
        campaign.status = CampaignStatus.RUNNING
        campaign.started_at = datetime.now()
        campaign.completed_at = None
        self._refresh_campaign_counts(campaign, messages)
        self._campaign_repo.update(campaign)

        try:
            await self._process(campaign, messages)
        except asyncio.CancelledError:
            campaign.status = CampaignStatus.CANCELLED
            self._campaign_repo.update(campaign)
        except Exception as e:
            logger.exception(f"Campaign error: {e}")
            campaign.status = CampaignStatus.CANCELLED
            self._campaign_repo.update(campaign)
        finally:
            self._refresh_campaign_counts(campaign, messages)
            if campaign.status == CampaignStatus.RUNNING:
                if not self._running:
                    campaign.status = CampaignStatus.CANCELLED
                elif self._pending_messages(messages):
                    campaign.status = CampaignStatus.PAUSED
                else:
                    campaign.status = CampaignStatus.COMPLETED
                    campaign.completed_at = datetime.now()
                self._campaign_repo.update(campaign)
            self._running = False
            self._current_campaign_id = None

    async def _process(self, campaign: Campaign, messages: list[Message]):
        campaign.total_messages = len(messages)
        self._refresh_campaign_counts(campaign, messages)
        self._campaign_repo.update(campaign)
        self._emit_progress(campaign, messages)

        while self._running:
            pending = self._pending_messages(messages)
            if not pending:
                return

            progressed = False
            for message in pending:
                if not self._running:
                    return
                while self._paused and self._running:
                    await asyncio.sleep(0.5)
                if not self._running:
                    return

                await self._throttler.wait()
                message.status = MessageStatus.SENDING
                self._message_repo.update(message)

                success, error = await self._send_fn(message.phone, message.content)
                if success:
                    message.status = MessageStatus.SENT
                    message.sent_at = datetime.now()
                    message.error_message = ""
                    self._throttler.record_success()
                    progressed = True
                else:
                    message.retry_count += 1
                    message.error_message = error
                    if message.retry_count >= max(1, message.max_retries):
                        message.status = MessageStatus.FAILED
                        progressed = True
                    else:
                        message.status = MessageStatus.QUEUED
                    self._throttler.record_failure()

                self._message_repo.update(message)
                self._throttler.record_send()
                self._refresh_campaign_counts(campaign, messages)
                self._campaign_repo.update(campaign)
                self._emit_progress(campaign, messages)

            if not progressed and self._pending_messages(messages):
                await asyncio.sleep(0.5)

    def _pending_messages(self, messages: list[Message]) -> list[Message]:
        return [
            message for message in messages
            if message.status in (MessageStatus.PENDING, MessageStatus.QUEUED)
            and message.retry_count < max(1, message.max_retries)
        ]

    def _refresh_campaign_counts(self, campaign: Campaign, messages: list[Message]):
        campaign.total_messages = len(messages)
        campaign.sent_count = sum(1 for m in messages if m.status == MessageStatus.SENT)
        campaign.failed_count = sum(1 for m in messages if m.status == MessageStatus.FAILED)

    def _emit_progress(self, campaign: Campaign, messages: list[Message]):
        if self._progress_callback:
            current = campaign.sent_count + campaign.failed_count
            self._progress_callback(current, len(messages), campaign.sent_count, campaign.failed_count)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._running = False
        self._paused = False
