from pathlib import Path
p = Path("scripts/windows_worker/daemon.py")
content = p.read_text()

replacement = """                elif e.code == 409 and "Task is not awaiting a result" in body:
                    print(f"[Windows Worker] Result rejected (task no longer active): {body}")
                    return
"""

# Insert it before the except Exception:
content = content.replace('            except Exception:', replacement + '            except Exception:')
p.write_text(content)
