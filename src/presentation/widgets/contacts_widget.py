from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QLineEdit, QComboBox, QMessageBox,
    QHeaderView, QGroupBox, QFileDialog, QDialog, QInputDialog,
)
from src.domain.entities import Contact
from src.application.services.contact_service import ContactService
from src.domain.enums import ContactImportSource


class ContactsWidget(QWidget):
    def __init__(self, service: ContactService):
        super().__init__()
        self._service = service
        self._current_filter = None
        self._extra_groups = set()
        self._build_ui()
        self._load_contacts()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("بحث بالاسم أو الرقم...")
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)

        self._group_combo = QComboBox()
        self._group_combo.addItem("كل المجموعات", None)
        self._group_combo.currentIndexChanged.connect(self._on_group_filter)
        toolbar.addWidget(QLabel("المجموعة:"))
        toolbar.addWidget(self._group_combo)

        layout.addLayout(toolbar)

        actions = QHBoxLayout()
        btn_add = QPushButton("إضافة جهة اتصال")
        btn_add.clicked.connect(self._add_contact)
        actions.addWidget(btn_add)

        btn_edit = QPushButton("تعديل")
        btn_edit.clicked.connect(self._edit_contact)
        actions.addWidget(btn_edit)

        btn_delete = QPushButton("حذف")
        btn_delete.setObjectName("btnDanger")
        btn_delete.clicked.connect(self._delete_contact)
        actions.addWidget(btn_delete)

        btn_import = QPushButton("استيراد من TXT")
        btn_import.clicked.connect(self._import_txt)
        actions.addWidget(btn_import)

        btn_delete_all = QPushButton("حذف الكل")
        btn_delete_all.setObjectName("btnDanger")
        btn_delete_all.clicked.connect(self._delete_all)
        actions.addWidget(btn_delete_all)

        btn_add_group = QPushButton("إضافة مجموعة")
        btn_add_group.clicked.connect(self._add_group)
        actions.addWidget(btn_add_group)

        btn_delete_group = QPushButton("حذف مجموعة")
        btn_delete_group.setObjectName("btnDanger")
        btn_delete_group.clicked.connect(self._delete_group)
        actions.addWidget(btn_delete_group)

        layout.addLayout(actions)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["الاسم", "رقم الهاتف", "المجموعة", "ملاحظات"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

    def _load_contacts(self):
        group = self._group_combo.currentData()
        contacts = self._service.get_all(group)
        self._table.setRowCount(len(contacts))
        for i, c in enumerate(contacts):
            self._table.setItem(i, 0, QTableWidgetItem(c.name))
            self._table.setItem(i, 1, QTableWidgetItem(c.phone))
            self._table.setItem(i, 2, QTableWidgetItem(c.group_name))
            self._table.setItem(i, 3, QTableWidgetItem(c.notes))
            self._table.item(i, 0).setData(256, c.id)
        self._count_label.setText(f"إجمالي جهات الاتصال: {len(contacts)}")

    def _all_group_names(self) -> list[str]:
        all_groups = list(self._extra_groups)
        for g in self._service.get_groups():
            if g not in all_groups:
                all_groups.append(g)
        return all_groups

    def refresh_groups(self):
        current = self._group_combo.currentData()
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        self._group_combo.addItem("كل المجموعات", None)
        for g in self._all_group_names():
            self._group_combo.addItem(g, g)
        idx = self._group_combo.findData(current)
        if idx >= 0:
            self._group_combo.setCurrentIndex(idx)
        self._group_combo.blockSignals(False)

    def refresh(self):
        self.refresh_groups()
        self._load_contacts()

    def _on_search(self, text: str):
        if not text.strip():
            self._load_contacts()
            return
        results = self._service.search(text)
        self._table.setRowCount(len(results))
        for i, c in enumerate(results):
            self._table.setItem(i, 0, QTableWidgetItem(c.name))
            self._table.setItem(i, 1, QTableWidgetItem(c.phone))
            self._table.setItem(i, 2, QTableWidgetItem(c.group_name))
            self._table.setItem(i, 3, QTableWidgetItem(c.notes))
            self._table.item(i, 0).setData(256, c.id)
        self._count_label.setText(f"نتائج البحث: {len(results)}")

    def _on_group_filter(self):
        self._load_contacts()

    def _add_contact(self):
        dialog = ContactDialog(self, groups=self._all_group_names())
        if dialog.exec() == QDialog.Accepted:
            contact = dialog.contact
            errors = contact.validate()
            if errors:
                QMessageBox.warning(self, "خطأ", "\n".join(errors))
                return
            self._service.add(contact)
            self.refresh()

    def _edit_contact(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار جهة اتصال")
            return
        contact_id = self._table.item(row, 0).data(256)
        contact = self._service.get_by_id(contact_id)
        if not contact:
            return
        dialog = ContactDialog(self, contact, groups=self._all_group_names())
        if dialog.exec() == QDialog.Accepted:
            updated = dialog.contact
            errors = updated.validate()
            if errors:
                QMessageBox.warning(self, "خطأ", "\n".join(errors))
                return
            updated.id = contact.id
            self._service.update(updated)
            self.refresh()

    def _delete_contact(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار جهة اتصال")
            return
        contact_id = self._table.item(row, 0).data(256)
        confirm = QMessageBox.question(self, "تأكيد", "هل أنت متأكد من حذف جهة الاتصال؟")
        if confirm == QMessageBox.Yes:
            self._service.delete(contact_id)
            self.refresh()

    def _import_txt(self):
        path, _ = QFileDialog.getOpenFileName(self, "اختيار ملف TXT", "", "Text (*.txt *.csv)")
        if not path:
            return
        group = self._group_combo.currentData() or "عام"
        count, errors = self._service.import_from_txt(path, default_group=group)
        msg = f"تم استيراد {count} جهة اتصال بنجاح"
        if errors:
            msg += f"\nالأخطاء ({len(errors)}):\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "نتيجة الاستيراد", msg)
        self.refresh()

    def _delete_all(self):
        confirm = QMessageBox.question(
            self, "تأكيد",
            "هل أنت متأكد من حذف جميع جهات الاتصال؟\nلا يمكن التراجع عن هذا الإجراء."
        )
        if confirm == QMessageBox.Yes:
            count = self._service.delete_all()
            QMessageBox.information(self, "حذف", f"تم حذف {count} جهة اتصال")
            self.refresh()

    def _add_group(self):
        name, ok = QInputDialog.getText(self, "إضافة مجموعة", "اسم المجموعة الجديدة:")
        if ok and name.strip():
            self._extra_groups.add(name.strip())
            self.refresh_groups()

    def _delete_group(self):
        group = self._group_combo.currentData()
        if not group:
            QMessageBox.warning(self, "تنبيه", "الرجاء اختيار مجموعة")
            return
        confirm = QMessageBox.question(self, "تأكيد",
                                        f"هل أنت متأكد من حذف مجموعة '{group}' بالكامل؟")
        if confirm == QMessageBox.Yes:
            self._extra_groups.discard(group)
            count = self._service.delete_group(group)
            QMessageBox.information(self, "حذف", f"تم حذف {count} جهة اتصال")
            self.refresh()


class ContactDialog(QDialog):
    def __init__(self, parent=None, contact: Contact = None, groups: list[str] = None):
        super().__init__(parent)
        self._contact = contact or Contact()
        self._groups = groups or []
        self.setWindowTitle("بيانات جهة الاتصال")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        from PySide6.QtWidgets import QFormLayout, QDialogButtonBox
        layout = QFormLayout(self)

        self._name_input = QLineEdit(self._contact.name)
        layout.addRow("الاسم:", self._name_input)

        self._phone_input = QLineEdit(self._contact.phone)
        layout.addRow("رقم الهاتف:", self._phone_input)

        self._group_input = QComboBox()
        self._group_input.setEditable(True)
        self._group_input.addItems(self._groups)
        idx = self._group_input.findText(self._contact.group_name)
        if idx >= 0:
            self._group_input.setCurrentIndex(idx)
        else:
            self._group_input.setEditText(self._contact.group_name)
        layout.addRow("المجموعة:", self._group_input)

        self._notes_input = QLineEdit(self._contact.notes)
        layout.addRow("ملاحظات:", self._notes_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def contact(self) -> Contact:
        return Contact(
            name=self._name_input.text().strip(),
            phone=self._phone_input.text().strip(),
            group_name=self._group_input.currentText().strip() or "عام",
            notes=self._notes_input.text().strip(),
        )
