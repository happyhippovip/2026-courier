import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from device_state_memory import DeviceStateMemory, SensitiveDataException

def test_valid_device_state_serialization():
    mem = DeviceStateMemory(
        device_id="WIN-BUILD-AGENT-01",
        os_name="Windows 11 Pro",
        os_version="10.0.22631",
        runtime_capabilities=["hyper-v", "wsl2", "powershell-7"],
        installed_courier_version="4.0.0-rc1",
        verified_dependencies={
            "python": "3.12.10",
            "git": "2.44.0"
        },
        last_clean_shutdown_ts=1728135800,
        supported_recovery_capabilities=["TERMINAL_HOST_FAILED", "STALE_LOCK_DELETION"]
    )
    
    # Serialization should succeed
    json_payload = mem.to_json()
    assert "WIN-BUILD-AGENT-01" in json_payload
    
    # Deserialization should succeed
    restored = DeviceStateMemory.from_json(json_payload)
    assert restored.installed_courier_version == "4.0.0-rc1"
    assert "hyper-v" in restored.runtime_capabilities

def test_secret_filtering_prevents_serialization():
    mem = DeviceStateMemory(
        device_id="WIN-BUILD-AGENT-01",
        os_name="Windows",
        os_version="10",
        runtime_capabilities=["api_key_enabled"], # FORBIDDEN STRING
        installed_courier_version="1.0",
        verified_dependencies={},
        last_clean_shutdown_ts=None,
        supported_recovery_capabilities=[]
    )
    
    with pytest.raises(SensitiveDataException, match="api_key"):
        mem.to_json()

def test_secret_filtering_prevents_deserialization():
    malicious_json = '''
    {
      "device_id": "WIN-1",
      "os_name": "Windows",
      "os_version": "10",
      "runtime_capabilities": [],
      "installed_courier_version": "1.0",
      "verified_dependencies": {"github_token": "ghp_12345"},
      "last_clean_shutdown_ts": null,
      "supported_recovery_capabilities": []
    }
    '''
    
    with pytest.raises(SensitiveDataException, match="token"):
        DeviceStateMemory.from_json(malicious_json)
