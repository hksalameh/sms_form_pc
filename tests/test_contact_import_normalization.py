from src.application.services.contact_service import ContactService


def test_import_adds_missing_leading_zero():
    assert ContactService.normalize_import_phone("796123456") == "0796123456"


def test_import_preserves_existing_leading_zero():
    assert ContactService.normalize_import_phone("0796123456") == "0796123456"


def test_import_normalizes_jordan_international_number():
    assert ContactService.normalize_import_phone("+962 79 612 3456") == "0796123456"
    assert ContactService.normalize_import_phone("00962-79-612-3456") == "0796123456"


def test_import_handles_excel_numeric_phone():
    assert ContactService.normalize_import_phone(796123456) == "0796123456"
    assert ContactService.normalize_import_phone(796123456.0) == "0796123456"
