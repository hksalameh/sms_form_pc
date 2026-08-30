from abc import ABC, abstractmethod
from typing import Optional, Protocol
from .entities import Contact, Template, Campaign, Message


class ContactRepository(ABC):
    @abstractmethod
    def add(self, contact: Contact) -> Contact: ...

    @abstractmethod
    def get_by_id(self, contact_id: int) -> Optional[Contact]: ...

    @abstractmethod
    def get_all(self, group: Optional[str] = None) -> list[Contact]: ...

    @abstractmethod
    def get_groups(self) -> list[str]: ...

    @abstractmethod
    def update(self, contact: Contact) -> bool: ...

    @abstractmethod
    def delete(self, contact_id: int) -> bool: ...

    @abstractmethod
    def delete_all(self) -> int: ...

    @abstractmethod
    def delete_group(self, group_name: str) -> int: ...

    @abstractmethod
    def count(self, group: Optional[str] = None) -> int: ...

    @abstractmethod
    def bulk_add(self, contacts: list[Contact]) -> list[Contact]: ...

    @abstractmethod
    def search(self, query: str) -> list[Contact]: ...


class TemplateRepository(ABC):
    @abstractmethod
    def add(self, template: Template) -> Template: ...

    @abstractmethod
    def get_by_id(self, template_id: int) -> Optional[Template]: ...

    @abstractmethod
    def get_all(self) -> list[Template]: ...

    @abstractmethod
    def update(self, template: Template) -> bool: ...

    @abstractmethod
    def delete(self, template_id: int) -> bool: ...


class CampaignRepository(ABC):
    @abstractmethod
    def add(self, campaign: Campaign) -> Campaign: ...

    @abstractmethod
    def get_by_id(self, campaign_id: int) -> Optional[Campaign]: ...

    @abstractmethod
    def get_all(self) -> list[Campaign]: ...

    @abstractmethod
    def update(self, campaign: Campaign) -> bool: ...

    @abstractmethod
    def delete(self, campaign_id: int) -> bool: ...


class MessageRepository(ABC):
    @abstractmethod
    def add(self, message: Message) -> Message: ...

    @abstractmethod
    def add_batch(self, messages: list[Message]) -> list[Message]: ...

    @abstractmethod
    def get_by_id(self, message_id: int) -> Optional[Message]: ...

    @abstractmethod
    def get_by_campaign(self, campaign_id: int) -> list[Message]: ...

    @abstractmethod
    def update(self, message: Message) -> bool: ...

    @abstractmethod
    def update_batch(self, messages: list[Message]) -> bool: ...

    @abstractmethod
    def get_pending(self, limit: int = 50) -> list[Message]: ...

    @abstractmethod
    def count_by_status(self, campaign_id: int) -> dict: ...


class SmsSender(Protocol):
    async def send(self, phone: str, text: str) -> tuple[bool, str]: ...
