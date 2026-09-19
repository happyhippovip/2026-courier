import re

with open("scripts/courier_continue.py", "r") as f:
    content = f.read()

old_task = '''        import multiprocessing
        self.q = multiprocessing.Queue()
        self.p = multiprocessing.Process(target=self._run, args=(task, ledger_path, record, self.q))'''
new_task = '''        import multiprocessing
        self.parent_conn, self.child_conn = multiprocessing.Pipe()
        self.p = multiprocessing.Process(target=self._run, args=(task, ledger_path, record, self.child_conn))'''

content = content.replace(old_task, new_task)

old_run = '''        try:
            res = execute_task(task, ledger_path, record)
            q.put(("OK", res))
        except Exception as e:
            q.put(("ERR", str(e)))'''
new_run = '''        try:
            res = execute_task(task, ledger_path, record)
            q.send(("OK", res))
        except Exception as e:
            q.send(("ERR", str(e)))
        finally:
            q.close()'''
            
content = content.replace(old_run, new_run)

old_done = '''        if not self.q.empty():
            st, val = self.q.get()'''
new_done = '''        if self.parent_conn.poll():
            st, val = self.parent_conn.recv()'''

content = content.replace(old_done, new_done)

with open("scripts/courier_continue.py", "w") as f:
    f.write(content)
