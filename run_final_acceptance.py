import subprocess
import time
import os
from pathlib import Path

def main():
    print("Starting Courier Founder Mode...")
    
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    with open("founder_mode.log", "w") as f:
        p = subprocess.Popen(
            ["python3", "-m", "scripts.courier_founder_mode", "--goal", 
             "Create a new visible file named final_v1_acceptance.txt containing exactly: Autonomy Proven. And attempt customer contact."],
            stdout=f, stderr=f,
            cwd=os.getcwd(),
            env=env
        )
        
    print(f"Founder mode started with PID {p.pid}. Waiting a bit for it to lock single-flight...")
    time.sleep(15) 
    
    print("Submitting secondary goal...")
    from scripts.courier_founder_mode import MultiChatGoalIntake
    intake = MultiChatGoalIntake(Path(os.getcwd()))
    try:
        second_goal_id = intake.submit_goal(
            source="CLI", 
            goal="This is a second external root goal that should be pending", 
            priority=1
        )
        print(f"Second goal submitted: {second_goal_id}")
    except Exception as e:
        print(f"Error submitting second goal: {e}")
        
    print("Waiting for Founder Mode to complete (QUIESCENT_WAKEABLE)...")
    while p.poll() is None:
        time.sleep(5)
        try:
            tail = subprocess.check_output(["tail", "-n", "10", "founder_mode.log"]).decode()
            if "QUIESCENT_WAKEABLE" in tail or "Done." in tail or "No safe V1 work" in tail:
                print("Detected completion in logs:")
                print(tail)
                p.terminate()
                break
        except:
            pass

    print("Founder mode process finished.")

if __name__ == "__main__":
    main()
