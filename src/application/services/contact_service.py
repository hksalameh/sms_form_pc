import re
from typing import Optional
from src.domain.entities import Contact
from src.domain.enums import ContactImportSource
from src.domain.interfaces import ContactRepository


class ContactService:
    def __init__(self, repo: ContactRepository):
        self._repo = repo

    def add(self, contact: Contact) -> Contact:
        return self._repo.add(contact)

    def update(self, contact: Contact) -> bool:
        return self._repo.update(contact)

    def delete(self, contact_id: int) -> bool:
        return self._repo.delete(contact_id)

    def delete_all(self) -> int:
        return self._repo.delete_all()

    def delete_group(self, group_name: str) -> int:
        return self._repo.delete_group(group_name)

    def get_all(self, group: Optional[str] = None) -> list[Contact]:
        return self._repo.get_all(group)

    def get_by_id(self, contact_id: int) -> Optional[Contact]:
        return self._repo.get_by_id(contact_id)

    def get_groups(self) -> list[str]:
        return self._repo.get_groups()

    def count(self, group: Optional[str] = None) -> int:
        return self._repo.count(group)

    def search(self, q: str) -> list[Contact]:
        return self._repo.search(q)

    def import_from_txt(self, file_path: str,
                        default_group: str = "عام") -> tuple[int, list[str]]:
        contacts = []
        errors = []
        unnamed_counter = 0
        with open(file_path, encoding="utf-8-sig") as f:
            for line_no, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "," in line:
                    parts = [p.strip() for p in line.split(",", 1)]
                    raw_phone = parts[0]
                    name = parts[1]
                elif "\t" in line:
                    parts = [p.strip() for p in line.split("\t", 1)]
                    raw_phone = parts[0]
                    name = parts[1]
                else:
                    raw_phone = line
                    name = ""
                phone = re.sub(r"[^0-9]", "", raw_phone)
                if not phone:
                    errors.append(f"سطر {line_no}: رقم هاتف فارغ ({raw_phone})")
                    continue
                if not phone.startswith("0"):
                    phone = "0" + phone
                if not name:
                    unnamed_counter += 1
                    name = f"رقم {unnamed_counter}"
                contact = Contact(name=name, phone=phone, group_name=default_group,
                                  import_source=ContactImportSource.TXT)
                val_errors = contact.validate()
                if val_errors:
                    errors.append(f"سطر {line_no}: {', '.join(val_errors)} (رقم: {phone})")
                    continue
                contacts.append(contact)
        if contacts:
            self._repo.bulk_add(contacts)
        return len(contacts), errors
