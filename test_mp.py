import multiprocessing

class TaskFuture:
    def __init__(self):
        self.parent_conn, self.child_conn = multiprocessing.Pipe()
        self.p = multiprocessing.Process(target=self._run, args=(self.child_conn,))
        self.p.daemon = True
        self.p.start()

    def _run(self, q):
        q.send(("OK", "done"))

if __name__ == "__main__":
    t = TaskFuture()
    t.p.join()
    print("Success")
