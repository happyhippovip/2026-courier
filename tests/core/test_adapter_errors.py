import pytest
from courier_core.adapter_errors import (
    MissingElementError, ProviderAuthError, ErrorSeverity, ProcessStormError
)

def test_missing_element_is_transient():
    err = MissingElementError("submit_button")
    assert err.severity == ErrorSeverity.TRANSIENT

def test_auth_error_requires_user():
    err = ProviderAuthError()
    assert err.severity == ErrorSeverity.REQUIRES_USER

def test_process_storm_is_fatal():
    err = ProcessStormError("Electron")
    assert err.severity == ErrorSeverity.FATAL
