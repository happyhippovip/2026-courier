import os
import pytest
from app.cannon_yolo import has_secret, redact

def test_has_secret_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret-key-12345")
    
    text = "Here is my token: super-secret-key-12345, do not share."
    assert has_secret(text) == True
    
    clean_text = "Here is my token: nothing, do not share."
    assert has_secret(clean_text) == False

def test_redact_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "super-secret-github-token")
    
    text = "Login with super-secret-github-token to continue."
    redacted = redact(text)
    
    assert "super-secret-github-token" not in redacted
    assert "***REDACTED***" in redacted
    
def test_has_secret_pattern():
    text = "My github token is ghp_123456789012345678901234567890123456"
    assert has_secret(text) == True
    
def test_redact_pattern():
    text = "My openai key is sk-123456789012345678901234567890123456789012345678 and that is all."
    redacted = redact(text)
    
    assert "sk-1234567890" not in redacted
    assert "***REDACTED***" in redacted

def test_redact_safe_text():
    text = "Just a normal log line without any secrets."
    assert redact(text) == text

def test_has_secret_dynamic_env(monkeypatch):
    monkeypatch.setenv("MY_CUSTOM_PASSWORD_PROD", "very-secret-123")
    assert has_secret("Checking very-secret-123 login") == True
    assert redact("Checking very-secret-123 login") == "Checking ***REDACTED*** login"

def test_has_secret_ignores_short_values(monkeypatch):
    monkeypatch.setenv("API_KEY", "123")
    assert has_secret("The number is 12345") == False
    assert redact("The number is 12345") == "The number is 12345"

def test_has_secret_aws():
    assert has_secret("My AWS ID is AKIAIOSFODNN7EXAMPLE") == True
    assert redact("My AWS ID is AKIAIOSFODNN7EXAMPLE") == "My AWS ID is ***REDACTED***"

def test_has_secret_bearer():
    assert has_secret("Authorization: Bearer my-long-token-12345-abcde==") == True
    assert redact("Authorization: Bearer my-long-token-12345-abcde==") == "Authorization: ***REDACTED***"

def test_has_secret_pem():
    pem = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBg\n-----END PRIVATE KEY-----"
    assert has_secret(f"Here is the cert:\n{pem}\nUse it wisely.") == True
    assert redact(f"Here is the cert:\n{pem}\nUse it wisely.") == "Here is the cert:\n***REDACTED***\nUse it wisely."

def test_has_secret_env_assignments():
    assert has_secret("DB_PASSWORD=supersecret123") == True
    assert redact("DB_PASSWORD=supersecret123") == "DB_PASSWORD = ***REDACTED***"
    
    assert has_secret('api_key : "my-api-key-1234"') == True
    assert redact('api_key : "my-api-key-1234"') == "api_key : ***REDACTED***"
