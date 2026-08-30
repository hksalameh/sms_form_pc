import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from src.presentation import app as app_module


def test_application_reaches_event_loop_without_startup_exception():
    """Build the real main window and stop just before entering the Qt event loop."""
    with patch.object(QApplication, "exec", return_value=0):
        with pytest.raises(SystemExit) as exit_info:
            app_module.run()

    assert exit_info.value.code == 0
