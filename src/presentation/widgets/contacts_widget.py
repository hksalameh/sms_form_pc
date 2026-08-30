from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.application.services.contact_service import ContactService
from src.domain.entities import Contact
from src.domain.enums import ContactImportSource


class ContactsWidget(QWidget):
    def __init__(self, service: ContactService):
        super().__init__()
        self._service = service
        self._extra_groups: set[str] = set()
        self._visible_contacts: list[Contact] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        summary = QHBoxLayout()
        summary.setSpacing(10)
        total_card, self._total_value = self._build_summary_card("إجمالي جهات الاتصال", "0")
        groups_card, self._groups_value = self._build_summary_card("المجموعات", "0")
        visible_card, self._visible_value = self._build_summary_card("الظاهر حاليًا", "0")
        summary.addWidget(total_card)
        summary.addWidget(groups_card)
        summary.addWidget(visible_card)
        layout.addLayout(summary)

        filter_card = QFrame()
        filter_card.setObjectName("contactToolbarCard")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(14, 12, 14, 12)
        filter_layout.setSpacing(10)

        filters = QHBoxLayout()
        filters.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("contactSearch")
        self._search_input.setPlaceholderText("بحث بالاسم أو رقم الهاتف أو المجموعة...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._apply_filters)
        filters.addWidget(self._search_input, 1)

        filters.addWidget(QLabel("المجموعة:"))
        self._group_combo = QComboBox()
        self._group_combo.setMinimumWidth(190)
        self._group_combo.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(self._group_combo)

        clear_filter = QPushButton("مسح الفلاتر")
        clear_filter.setObjectName("secondaryAction")
        clear_filter.clicked.connect(self._clear_filters)
        filters.addWidget(clear_filter)
        filter_layout.addLayout(filters)

        primary_actions = QHBoxLayout()
        primary_actions.setSpacing(8)

        btn_add = QPushButton("+  إضافة جهة اتصال")
        btn_add.clicked.connect(self._add_contact)
        primary_actions.addWidget(btn_add)

        btn_edit = QPushButton("تعديل")
        btn_edit.setObjectName("secondaryAction")
        btn_edit.clicked.connect(self._edit_contact)
        primary_actions.addWidget(btn_edit)

        btn_move = QPushButton("نقل المحدد إلى مجموعة")
        btn_move.setObjectName("secondaryAction")
        btn_move.clicked.connect(self._move_selected_to_group)
        primary_actions.addWidget(btn_move)

        btn_delete = QPushButton("حذف المحدد")
        btn_delete.setObjectName("btnDanger")
        btn_delete.clicked.connect(self._delete_selected_contacts)
        primary_actions.addWidget(btn_delete)

        primary_actions.addStretch()

        btn_import_excel = QPushButton("استيراد Excel")
        btn_import_excel.setObjectName("secondaryAction")
        btn_import_excel.clicked.connect(self._import_excel)
        primary_actions.addWidget(btn_import_excel)

        btn_import_text = QPushButton("استيراد TXT / CSV")
        btn_import_text.setObjectName("secondaryAction")
        btn_import_text.clicked.connect(self._import_txt)
        primary_actions.addWidget(btn_import_text)
        filter_layout.addLayout(primary_actions)

        group_actions = QHBoxLayout()
        group_actions.setSpacing(8)
        btn_add_group = QPushButton("+ مجموعة جديدة")
        btn_add_group.setObjectName("secondaryAction")
        btn_add_group.clicked.connect(self._add_group)
        group_actions.addWidget(btn_add_group)

        btn_delete_group = QPushButton("حذف المجموعة الحالية")
        btn_delete_group.setObjectName("btnDanger")
        btn_delete_group.clicked.connect(self._delete_group)
        group_actions.addWidget(btn_delete_group)

        group_actions.addStretch()

        import_hint = QLabel(
            "ملاحظة: عند الاستيراد، إذا كان الرقم ناقص الصفر الأول فسيتم إضافته تلقائيًا."
        )
        import_hint.setObjectName("importHint")
        group_actions.addWidget(import_hint)
        filter_layout.addLayout(group_actions)

        layout.addWidget(filter_card)

        self._table = QTableWidget()
        self._table.setObjectName("contactsTable")
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["الاسم", "رقم الهاتف", "المجموعة", "المصدر", "ملاحظات"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.itemSelectionChanged.connect(self._update_selection_status)
        self._table.doubleClicked.connect(self._edit_contact)
        layout.addWidget(self._table, 1)

        footer = QHBoxLayout()
        self._count_label = QLabel("")
        self._count_label.setObjectName("contactFooter")
        footer.addWidget(self._count_label)

        footer.addStretch()
        self._selection_label = QLabel("المحدد: 0")
        self._selection_label.setObjectName("contactFooter")
        footer.addWidget(self._selection_label)

        btn_delete_all = QPushButton("حذف جميع جهات الاتصال")
        btn_delete_all.setObjectName("btnDanger")
        btn_delete_all.clicked.connect(self._delete_all)
        footer.addWidget(btn_delete_all)
        layout.addLayout(footer)

    def _build_summary_card(self, title: str, value: str):
        card = QFrame()
        card.setObjectName("contactSummaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("contactSummaryTitle")
        card_layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("contactSummaryValue")
        card_layout.addWidget(value_label)
        return card, value_label

    def _all_group_names(self) -> list[str]:
        groups = set(self._extra_groups)
        groups.update(group for group in self._service.get_groups() if group)
        return sorted(groups)

    def refresh_groups(self):
        current = self._group_combo.currentData() if self._group_combo.count() else None
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        self._group_combo.addItem("كل المجموعات", None)
        for group in self._all_group_names():
            self._group_combo.addItem(group, group)
        index = self._group_combo.findData(current)
        self._group_combo.setCurrentIndex(index if index >= 0 else 0)
        self._group_combo.blockSignals(False)

    def refresh(self):
        self.refresh_groups()
        self._apply_filters()
        self._refresh_summary()

    def _refresh_summary(self):
        groups = self._all_group_names()
        self._total_value.setText(str(self._service.count()))
        self._groups_value.setText(str(len(groups)))
        self._visible_value.setText(str(len(self._visible_contacts)))

    def _apply_filters(self, *_):
        query = self._search_input.text().strip() if hasattr(self, "_search_input") else ""
        group = self._group_combo.currentData() if self._group_combo.count() else None

        contacts = self._service.search(query) if query else self._service.get_all(group)
        if query and group:
            contacts = [contact for contact in contacts if contact.group_name == group]

        self._visible_contacts = contacts
        self._render_contacts(contacts)
        if hasattr(self, "_visible_value"):
            self._visible_value.setText(str(len(contacts)))

    def _render_contacts(self, contacts: list[Contact]):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(contacts))
        source_names = {
            ContactImportSource.MANUAL: "يدوي",
            ContactImportSource.TXT: "TXT",
            ContactImportSource.CSV: "ملف / Excel",
        }

        for row, contact in enumerate(contacts):
            name_item = QTableWidgetItem(contact.name)
            name_item.setData(Qt.UserRole, contact.id)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(contact.phone))
            self._table.setItem(row, 2, QTableWidgetItem(contact.group_name))
            self._table.setItem(
                row,
                3,
                QTableWidgetItem(source_names.get(contact.import_source, "غير معروف")),
            )
            self._table.setItem(row, 4, QTableWidgetItem(contact.notes))

        self._table.setSortingEnabled(True)
        prefix = "نتائج البحث" if self._search_input.text().strip() else "جهات الاتصال"
        self._count_label.setText(f"{prefix}: {len(contacts)}")
        self._update_selection_status()

    def _clear_filters(self):
        self._search_input.clear()
        self._group_combo.setCurrentIndex(0)
        self._apply_filters()

    def _selected_contact_ids(self) -> list[int]:
        ids: list[int] = []
        for index in self._table.selectionModel().selectedRows():
            item = self._table.item(index.row(), 0)
            if item:
                contact_id = item.data(Qt.UserRole)
                if contact_id is not None:
                    ids.append(contact_id)
        return ids

    def _update_selection_status(self):
        if hasattr(self, "_selection_label"):
            self._selection_label.setText(f"المحدد: {len(self._selected_contact_ids())}")

    def _add_contact(self):
        dialog = ContactDialog(self, groups=self._all_group_names())
        if dialog.exec() != QDialog.Accepted:
            return
        contact = dialog.contact
        errors = contact.validate()
        if errors:
            QMessageBox.warning(self, "خطأ", "\n".join(errors))
            return
        self._service.add(contact)
        self.refresh()

    def _edit_contact(self, *_):
        contact_ids = self._selected_contact_ids()
        if len(contact_ids) != 1:
            QMessageBox.warning(self, "تنبيه", "اختر جهة اتصال واحدة للتعديل")
            return
        contact = self._service.get_by_id(contact_ids[0])
        if not contact:
            return

        dialog = ContactDialog(self, contact, groups=self._all_group_names())
        if dialog.exec() != QDialog.Accepted:
            return

        updated = dialog.contact
        errors = updated.validate()
        if errors:
            QMessageBox.warning(self, "خطأ", "\n".join(errors))
            return
        updated.id = contact.id
        updated.import_source = contact.import_source
        self._service.update(updated)
        self.refresh()

    def _delete_selected_contacts(self):
        contact_ids = self._selected_contact_ids()
        if not contact_ids:
            QMessageBox.warning(self, "تنبيه", "حدد جهة اتصال واحدة أو أكثر")
            return

        confirm = QMessageBox.question(
            self,
            "تأكيد الحذف",
            f"هل تريد حذف {len(contact_ids)} جهة اتصال محددة؟",
        )
        if confirm != QMessageBox.Yes:
            return

        deleted = 0
        for contact_id in contact_ids:
            if self._service.delete(contact_id):
                deleted += 1
        self.refresh()
        self._count_label.setText(f"تم حذف {deleted} جهة اتصال")

    def _move_selected_to_group(self):
        contact_ids = self._selected_contact_ids()
        if not contact_ids:
            QMessageBox.warning(self, "تنبيه", "حدد جهة اتصال واحدة أو أكثر")
            return

        groups = self._all_group_names()
        group_name, ok = QInputDialog.getItem(
            self,
            "نقل إلى مجموعة",
            "اختر المجموعة أو اكتب اسم مجموعة جديدة:",
            groups,
            0,
            True,
        )
        group_name = group_name.strip()
        if not ok or not group_name:
            return

        self._extra_groups.add(group_name)
        moved = 0
        for contact_id in contact_ids:
            contact = self._service.get_by_id(contact_id)
            if not contact:
                continue
            contact.group_name = group_name
            if self._service.update(contact):
                moved += 1

        self.refresh()
        QMessageBox.information(self, "تم", f"تم نقل {moved} جهة اتصال إلى '{group_name}'")

    def _import_txt(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "اختيار ملف جهات الاتصال",
            "",
            "Text / CSV (*.txt *.csv);;All files (*.*)",
        )
        if not path:
            return

        group = self._group_combo.currentData() or "عام"
        try:
            count, notes = self._service.import_from_txt(path, default_group=group)
        except Exception as exc:
            QMessageBox.critical(self, "خطأ في الاستيراد", str(exc))
            return
        self._show_import_result(count, notes)

    def _import_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "اختيار ملف Excel",
            "",
            "Excel (*.xlsx *.xlsm)",
        )
        if not path:
            return

        group = self._group_combo.currentData() or "عام"
        try:
            count, notes = self._service.import_from_excel(path, default_group=group)
        except Exception as exc:
            QMessageBox.critical(self, "خطأ في استيراد Excel", str(exc))
            return
        self._show_import_result(count, notes)

    def _show_import_result(self, count: int, notes: list[str]):
        message = f"تم استيراد {count} جهة اتصال بنجاح."
        if notes:
            message += f"\n\nملاحظات الاستيراد: {len(notes)}"
            preview = "\n".join(notes[:8])
            message += f"\n{preview}"
            if len(notes) > 8:
                message += f"\n... وهناك {len(notes) - 8} ملاحظة أخرى"
        QMessageBox.information(self, "نتيجة الاستيراد", message)
        self.refresh()

    def _delete_all(self):
        confirm = QMessageBox.question(
            self,
            "تأكيد حذف الكل",
            "هل أنت متأكد من حذف جميع جهات الاتصال؟\nلا يمكن التراجع عن هذا الإجراء.",
        )
        if confirm == QMessageBox.Yes:
            count = self._service.delete_all()
            QMessageBox.information(self, "حذف", f"تم حذف {count} جهة اتصال")
            self.refresh()

    def _add_group(self):
        name, ok = QInputDialog.getText(self, "إضافة مجموعة", "اسم المجموعة الجديدة:")
        name = name.strip()
        if ok and name:
            self._extra_groups.add(name)
            self.refresh_groups()
            index = self._group_combo.findData(name)
            if index >= 0:
                self._group_combo.setCurrentIndex(index)
            self._refresh_summary()

    def _delete_group(self):
        group = self._group_combo.currentData()
        if not group:
            QMessageBox.warning(self, "تنبيه", "اختر مجموعة أولاً")
            return

        count = self._service.count(group)
        confirm = QMessageBox.question(
            self,
            "تأكيد حذف المجموعة",
            f"هل تريد حذف مجموعة '{group}'؟\nسيتم حذف {count} جهة اتصال بداخلها.",
        )
        if confirm != QMessageBox.Yes:
            return

        self._extra_groups.discard(group)
        deleted = self._service.delete_group(group)
        self.refresh()
        QMessageBox.information(self, "حذف المجموعة", f"تم حذف {deleted} جهة اتصال")


class ContactDialog(QDialog):
    def __init__(self, parent=None, contact: Contact = None, groups: list[str] = None):
        super().__init__(parent)
        self._contact = contact or Contact()
        self._groups = groups or []
        self.setWindowTitle("بيانات جهة الاتصال")
        self.setMinimumWidth(430)
        self._build_ui()

    def _build_ui(self):
        from PySide6.QtWidgets import QDialogButtonBox, QFormLayout

        layout = QFormLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self._name_input = QLineEdit(self._contact.name)
        self._name_input.setPlaceholderText("اسم جهة الاتصال")
        layout.addRow("الاسم:", self._name_input)

        self._phone_input = QLineEdit(self._contact.phone)
        self._phone_input.setPlaceholderText("مثال: 0791234567")
        layout.addRow("رقم الهاتف:", self._phone_input)

        self._group_input = QComboBox()
        self._group_input.setEditable(True)
        self._group_input.addItems(self._groups)
        index = self._group_input.findText(self._contact.group_name)
        if index >= 0:
            self._group_input.setCurrentIndex(index)
        else:
            self._group_input.setEditText(self._contact.group_name)
        layout.addRow("المجموعة:", self._group_input)

        self._notes_input = QLineEdit(self._contact.notes)
        self._notes_input.setPlaceholderText("ملاحظات اختيارية")
        layout.addRow("ملاحظات:", self._notes_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("حفظ")
        buttons.button(QDialogButtonBox.Cancel).setText("إلغاء")
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
