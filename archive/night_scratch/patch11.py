import sys
content = open("scripts/courier_continue.py").read()
content = content.replace(
    'except Exception as e:\n                    if "meaningful change" in str(e):\n                        pass\n                    else:\n                        raise e',
    'except Exception as e:\n                    print(f"Exception in update_ledger: {type(e)} {e}")\n                    if "meaningful change" in str(e):\n                        pass\n                    else:\n                        raise e'
)
open("scripts/courier_continue.py", "w").write(content)
