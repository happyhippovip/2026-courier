import pytest
import os
import time
from scripts.gate import gate

def test_a10_limits_time(monkeypatch):
    monkeypatch.setenv("LIMIT_ZEIT", "10")
    # if start time was 11 seconds ago, it should stop
    assert gate(time.time() - 11, 0, 0) == "LIMIT_ZEIT_REACHED"
    # if start time was 5 seconds ago, it should pass
    assert gate(time.time() - 5, 0, 0) is None

def test_a10_limits_kontingent(monkeypatch):
    monkeypatch.setenv("LIMIT_KONTINGENT", "5")
    assert gate(time.time(), 5, 0) == "LIMIT_KONTINGENT_REACHED"
    assert gate(time.time(), 4, 0) is None

def test_a10_limits_serienfehler(monkeypatch):
    monkeypatch.setenv("SERIENFEHLER", "3")
    assert gate(time.time(), 0, 3) == "SERIENFEHLER_REACHED"
    assert gate(time.time(), 0, 2) is None

def test_a10_limits_idle(monkeypatch):
    monkeypatch.setenv("IDLE_SECONDS", "60")
    assert gate(time.time(), 0, 0, idle_seconds=60) == "IDLE_SECONDS_REACHED"
    assert gate(time.time(), 0, 0, idle_seconds=59) is None

def test_a10_limits_task(monkeypatch):
    monkeypatch.setenv("TASK_SECONDS", "300")
    assert gate(time.time(), 0, 0, task_seconds=300) == "TASK_SECONDS_REACHED"
    assert gate(time.time(), 0, 0, task_seconds=299) is None

def test_a10_limits_edge_cases(monkeypatch):
    # Invalid values should be ignored
    monkeypatch.setenv("LIMIT_ZEIT", "invalid")
    monkeypatch.setenv("LIMIT_KONTINGENT", "-5")
    monkeypatch.setenv("SERIENFEHLER", "0")
    
    assert gate(time.time() - 1000, 1000, 1000, 1000, 1000) is None
