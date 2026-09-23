import pytest
from scripts.cannon_motor import CannonMotor, MotorError
import multiprocessing

def worker_hold(state_dir, ready_event):
    motor = CannonMotor(state_dir)
    ready_event.set()
    import time
    time.sleep(5)

def test_a9_singleton_lock(tmp_path):
    ready = multiprocessing.Event()
    p = multiprocessing.Process(target=worker_hold, args=(str(tmp_path), ready))
    p.start()
    
    # Wait for the first motor to initialize and take the lock
    ready.wait(timeout=2.0)
    
    # Now try to create a second motor in the same state_dir
    with pytest.raises(MotorError) as exc_info:
        motor_b = CannonMotor(str(tmp_path))
        
    assert "SINGLETON_LOCK_FAILED" in str(exc_info.value)
    
    p.terminate()
    p.join()
    
    # After termination, lock should be released, so we can create it
    motor_c = CannonMotor(str(tmp_path))
    assert motor_c is not None

def test_a9_different_state_dirs(tmp_path):
    # Zwei Cannons auf verschiedenen State-Ordnern
    dir1 = tmp_path / "state1"
    dir2 = tmp_path / "state2"
    
    motor1 = CannonMotor(str(dir1))
    motor2 = CannonMotor(str(dir2))
    
    assert motor1 is not None
    assert motor2 is not None
