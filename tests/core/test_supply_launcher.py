import hashlib
from courier_core.supply_chain import BundleVerifier
from courier_core.launcher_contract import LauncherContract, LauncherCommand

def test_bundle_verifier():
    data = b"print('hello')"
    file_hash = hashlib.sha256(data).hexdigest()
    
    manifest = {"app.py": file_hash}
    actual = {"app.py": data}
    
    assert BundleVerifier.verify_manifest(manifest, actual) is True
    
    # Missing file
    assert BundleVerifier.verify_manifest(manifest, {}) is False
    
    # Bad hash
    assert BundleVerifier.verify_manifest(manifest, {"app.py": b"bad"}) is False

def test_launcher_contract():
    valid = LauncherCommand("bin/courier.exe", ["--core-v1", "--enable-hub", "--port", "0"])
    assert LauncherContract.verify_launch_intent(valid) is True
    
    missing_hub = LauncherCommand("bin/courier", ["--core-v1"])
    assert LauncherContract.verify_launch_intent(missing_hub) is False
    
    bad_exe = LauncherCommand("python", ["--core-v1", "--enable-hub"])
    assert LauncherContract.verify_launch_intent(bad_exe) is False
