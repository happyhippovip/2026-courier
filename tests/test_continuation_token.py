import sys
import base64
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from continuation_token import ContinuationContext, ContinuationToken, ContinuationTokenError

def get_valid_context():
    return ContinuationContext(
        project="Courier",
        workkey="H1",
        sha="a1b2c3d",
        session_id="session-999",
        checkpoint_state="VERIFIED"
    )

def test_serialize_and_deserialize():
    context = get_valid_context()
    token = ContinuationToken(context)
    
    token_str = token.serialize()
    assert isinstance(token_str, str)
    
    deserialized = ContinuationToken.deserialize(token_str)
    assert deserialized.context.project == "Courier"
    assert deserialized.context.workkey == "H1"
    assert deserialized.context.sha == "a1b2c3d"
    assert deserialized.context.session_id == "session-999"
    assert deserialized.context.checkpoint_state == "VERIFIED"

def test_tamper_detection():
    context = get_valid_context()
    token = ContinuationToken(context)
    token_str = token.serialize()
    
    # Tamper with the token (change SHA from a1b2c3d to a1b2c3e)
    json_str = base64.urlsafe_b64decode(token_str.encode('utf-8')).decode('utf-8')
    payload = json.loads(json_str)
    payload["sha"] = "a1b2c3e" # Malicious change!
    
    tampered_str = base64.urlsafe_b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
    
    with pytest.raises(ContinuationTokenError, match="hash verification failed"):
        ContinuationToken.deserialize(tampered_str)

def test_missing_fields():
    context = get_valid_context()
    token = ContinuationToken(context)
    token_str = token.serialize()
    
    json_str = base64.urlsafe_b64decode(token_str.encode('utf-8')).decode('utf-8')
    payload = json.loads(json_str)
    del payload["session_id"]
    
    # Recalculate hash so hash check doesn't fail first (simulating an improperly generated old token)
    tampered_str = base64.urlsafe_b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')
    
    with pytest.raises(ContinuationTokenError, match="missing required context fields"):
        ContinuationToken.deserialize(tampered_str)

def test_invalid_base64():
    with pytest.raises(ContinuationTokenError, match="Invalid token format"):
        ContinuationToken.deserialize("not-a-base64-string!!!")
