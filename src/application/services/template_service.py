from typing import Optional
from src.domain.entities import Template
from src.domain.interfaces import TemplateRepository


class TemplateService:
    def __init__(self, repo: TemplateRepository):
        self._repo = repo

    def add(self, template: Template) -> Template:
        return self._repo.add(template)

    def update(self, template: Template) -> bool:
        return self._repo.update(template)

    def delete(self, template_id: int) -> bool:
        return self._repo.delete(template_id)

    def get_all(self) -> list[Template]:
        return self._repo.get_all()

    def get_by_id(self, template_id: int) -> Optional[Template]:
        return self._repo.get_by_id(template_id)
