# LinkedIn / X Technical Founder Post
**Topic:** Batch Task Anti-Stall Architecture  
**Format:** Short-Form Thought Leadership (150-250 words)  

---

Most developers try to solve reliability by adding more retry loops. That's a mistake.

Here is what we learned from fixing silent agent stalls in production:

1. **Kernel Truth Over Heartbeat Logs:** Never assume a process is alive just because a timestamp exists. Check `os.kill(pid, 0)`.
2. **POSIX Lease Locking:** Manual lock files stay behind on `SIGKILL`. Kernel-level `fcntl.flock()` drops automatically the millisecond a process dies.
3. **Fail-Closed Default:** If state is ambiguous, pause safely rather than burning API quota.

Reliability isn't about hoping workers don't crash. It's about designing crash recovery that requires zero human cleanup.
