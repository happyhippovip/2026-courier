import sys
content = open("scripts/magazine.py").read()
if "PRAGMA journal_mode=WAL" not in content:
    content = content.replace(
        "self.init_db()",
        "self.get_conn().execute('PRAGMA journal_mode=WAL')\n        self.get_conn().execute('PRAGMA synchronous=NORMAL')\n        self.init_db()"
    )
    open("scripts/magazine.py", "w").write(content)
