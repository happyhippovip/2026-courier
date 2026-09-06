# 5-Slide Visual Carousel Deck Specification
**Topic:** Batch Task Anti-Stall Architecture  
**Target Platform:** LinkedIn / X Carousels  

---

### Slide 1 (Hook / Title)
- **Visual:** Minimal dark theme with bold white accent text.
- **Copy:** Why 90% of Autonomous Background Agents Freeze in Production (And the 5-Line Fix).

### Slide 2 (The Trap)
- **Visual:** Diagram of orphan `lock.json` file left on disk after unhandled crash.
- **Copy:** The Stale File Lock Problem: When a worker crashes abruptly, the lock file stays forever.

### Slide 3 (The Solution)
- **Visual:** OS Kernel boundary diagram showing POSIX flock management.
- **Copy:** Kernel-Level File Fencing: Use `fcntl.flock()`. The OS automatically drops locks on process exit.

### Slide 4 (The Code)
- **Visual:** Clean 5-line Python code snippet with syntax highlighting.
- **Copy:**
  ```python
  import fcntl
  with open('state.lock', 'w') as f:
      fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
      # Atomic work safely executed here
  ```

### Slide 5 (Call to Action)
- **Visual:** Clean checklist box.
- **Copy:** Save this post to make your background agents crash-proof.
