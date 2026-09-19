with open("app/server.py", "r") as f:
    text = f.read()
import re
text = re.sub(r'    except OSError as e:\n        print\(repr\(e\)\)\n', r'    except OSError:\n', text)
text = text.replace('    except OSError:\n', '    except OSError as e:\n        print(repr(e))\n')
with open("app/server.py", "w") as f:
    f.write(text)
