with open("app/server.py", "r") as f:
    text = f.read()

text = text.replace("    except OSError as e:\n        print(repr(e))\n            return", "        except OSError:\n            return")
text = text.replace("    except OSError as e:\n        print(repr(e))\n            self.reply(404", "        except OSError:\n            self.reply(404")
text = text.replace("    except OSError as e:\n        print(repr(e))\n            self.reply(503", "        except OSError:\n            self.reply(503")
text = text.replace("    except OSError as e:\n        # Reuse", "    except OSError:\n        # Reuse")

with open("app/server.py", "w") as f:
    f.write(text)
