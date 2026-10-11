import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.revenue_workbook_sample import clean_email

def test_clean_email_normal():
    assert clean_email("test@example.com") == "test@example.com"

def test_clean_email_uppercase():
    assert clean_email("TEST@EXAMPLE.COM") == "test@example.com"

def test_clean_email_with_spaces():
    assert clean_email("   test@example.com   ") == "test@example.com"

def test_clean_email_with_extra_text():
    assert clean_email("Contact: test@example.com please") == "test@example.com"

def test_clean_email_invalid():
    assert clean_email("not-an-email") == "not-an-email"

def test_clean_email_none():
    assert clean_email(None) is None

def test_clean_email_numeric():
    assert clean_email(12345) == 12345
