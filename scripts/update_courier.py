import stat
#!/usr/bin/env python3
import os
import sys
import shutil
import zipfile
import subprocess
import time
import argparse
import tempfile
import platform

def run_command(cmd):
    return subprocess.run(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)

def get_current_version(app_dir):
    vf = os.path.join(app_dir, "version.txt")
    if os.path.exists(vf):
        with open(vf, "r") as f:
            return f.read().strip()
    return "1.0.0"

def get_update_version(extract_dir):
    vf = os.path.join(extract_dir, "version.txt")
    if os.path.exists(vf):
        with open(vf, "r") as f:
            return f.read().strip()
    return "UNKNOWN"

def restart_service():
    if platform.system() == "Windows":
        run_command(["powershell", "-Command", "Stop-ScheduledTask -TaskName CourierWindowsWorker -ErrorAction SilentlyContinue"])
        # Give it a moment to stop
        time.sleep(2)
        run_command(["powershell", "-Command", "Start-ScheduledTask -TaskName CourierWindowsWorker"])
    else:
        run_command(["systemctl", "restart", "courier"])

def health_check(app_dir):
    hc = os.path.join(app_dir, "scripts", "product_health_check.py")
    if os.path.exists(hc):
        res = run_command([sys.executable, hc])
        if res.returncode == 0 and b"HEALTHY" in res.stdout:
            return True
    return False

def remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def main():
    parser = argparse.ArgumentParser(description="Courier Product Updater")
    parser.add_argument("update_package", help="Path to the update .zip package")
    args = parser.parse_args()

    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    update_pkg = args.update_package

    if not os.path.exists(update_pkg):
        print(f"Error: Update package {update_pkg} not found.")
        sys.exit(1)

    print("[1] Detecting current version...")
    current_version = get_current_version(app_dir)
    print(f"    Current version: {current_version}")

    with tempfile.TemporaryDirectory() as temp_dir:
        print("[2] Extracting update and checking compatibility...")
        with zipfile.ZipFile(update_pkg, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        update_version = get_update_version(temp_dir)
        print(f"    Update version: {update_version}")
        
        # Simple compatibility check: cannot downgrade major versions if we implemented one, 
        # but for now, any version is considered compatible in this prototype.

        print("[3] Checkpointing state...")
        backup_dir = app_dir + "_backup_" + str(int(time.time()))
        shutil.copytree(app_dir, backup_dir, dirs_exist_ok=True)
        print(f"    State backed up to {backup_dir}")

        try:
            print("[4] Installing update...")
            # Copy all files from temp_dir to app_dir
            for item in os.listdir(temp_dir):
                s = os.path.join(temp_dir, item)
                d = os.path.join(app_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

            print("[5] Running migrations...")
            migration_script = os.path.join(app_dir, "scripts", "migrate.py")
            if os.path.exists(migration_script):
                res = run_command([sys.executable, migration_script])
                if res.returncode != 0:
                    raise Exception("Migration failed: " + res.stderr.decode())

            print("[6] Restarting Courier...")
            restart_service()
            time.sleep(3) # Wait for startup

            print("[7] Running health check...")
            if not health_check(app_dir):
                raise Exception("Health check failed after update.")

            print("\n[SUCCESS] Update applied successfully!")


        except Exception as e:
            print(f"\n[ERROR] Update failed: {e}")
            print("[8] Rolling back to previous state...")
            # Rollback
            for item in os.listdir(app_dir):
                item_path = os.path.join(app_dir, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, onerror=remove_readonly)
                    else:
                        os.remove(item_path)
                except Exception:
                    pass
            shutil.copytree(backup_dir, app_dir, dirs_exist_ok=True)
            restart_service()
            print("    Rollback complete.")
            sys.exit(1)

if __name__ == "__main__":
    main()



