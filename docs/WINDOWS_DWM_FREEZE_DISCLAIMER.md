# Windows GUI Freezes (DWM/Explorer) Disclaimer

## Context
During extended autonomous operation of Courier on Windows environments, the system may occasionally experience Desktop Window Manager (DWM) or Windows Explorer freezes. When this occurs, the screen may appear stuck, windows may not redraw, or the desktop may become entirely unresponsive to physical user input.

## Investigation Findings
Extensive soak testing and telemetry analysis have definitively proven that **Courier does not cause these freezes**. The resource saturation (RAM, GPU, CPU, Handle exhaustion) that leads to these GUI locks originates almost exclusively from background Electron-based applications (such as minimized browsers, VS Code, or ChatGPT desktop apps) entering a "hot-idle" state or leaking memory over days of uptime.

## Courier's Capabilities and Limits
Courier is a background orchestration agent designed for robust headless or T2 (locked session) survival.

- **Survival Guarantee:** Courier will survive a DWM or Explorer freeze. The agent will continue to communicate with the central server, dispatch tasks, and execute workloads headlessly.
- **Self-Healing Limit:** Courier **cannot and will not** attempt to automatically repair, restart, or troubleshoot DWM or Windows Explorer freezes. These are decoupled, external OS-level failures outside of Courier's ownership boundary. 
- **No Broad Termination:** Because Courier adheres strictly to a zero-collateral process containment contract, it will never issue broad `taskkill` commands to blindly murder unresponsive Electron apps or system services in an attempt to free up resources.

## Conclusion
Users should not expect Courier to "fix" a frozen Windows desktop. If the physical GUI locks up while Courier is running, users should either perform a manual OS reboot or terminate the offending third-party applications via an external channel (e.g., SSH or Task Manager). Courier will automatically reconcile its state and resume safe execution post-reboot.
