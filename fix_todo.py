with open("scripts/run_content_production_pipeline.py", "r") as f:
    content = f.read()

orig = """            if ans.strip().lower() in ["y", "yes"]:
                print("Approval granted. Ready for publisher agent.")
                # TODO: Trigger publish_youtube_package.py
            else:"""

new = """            if ans.strip().lower() in ["y", "yes"]:
                print("Approval granted. Triggering publisher agent...")
                try:
                    import subprocess
                    script_path = Path(__file__).parent / "publish_youtube_package.py"
                    subprocess.check_call([sys.executable, str(script_path), "--mission", manifest["mission_id"]])
                    print("Publishing triggered successfully.")
                except Exception as e:
                    print(f"Failed to trigger publish_youtube_package.py: {e}")
                    sys.exit(1)
            else:"""

content = content.replace(orig, new)

with open("scripts/run_content_production_pipeline.py", "w") as f:
    f.write(content)
