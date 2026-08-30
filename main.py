#!/usr/bin/env python
"""
SMSCaster - نظام إرسال الرسائل الجماعية عبر الهاتف
SMSCaster Clone - Bulk SMS Sending System
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.presentation.app import run

if __name__ == "__main__":
    run()
