/**
 * COURIER SYMPHONY - MUSE WINDOW LEDGER CLIENT
 * 
 * This script allows any local HTML file (Muse Window) to instantly connect 
 * to the Courier Universal Ledger and react to cross-platform AI events 
 * (from ChatGPT, Claude, Google, etc.) in real-time.
 */

class MuseLedgerClient {
    constructor(serverUrl = "http://localhost:8198") {
        this.serverUrl = serverUrl;
        this.eventSource = null;
        this.listeners = {};
    }

    // Connect to the Real-Time SSE Stream
    connect() {
        if (this.eventSource) {
            console.warn("MuseLedgerClient is already connected.");
            return;
        }

        console.log(`Connecting Muse Window to Universal Ledger at ${this.serverUrl}...`);
        this.eventSource = new EventSource(`${this.serverUrl}/ledger/stream`);

        this.eventSource.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                this._dispatch(payload.type, payload.data);
            } catch (err) {
                console.error("Error parsing Ledger Event:", err);
            }
        };

        this.eventSource.onerror = (err) => {
            console.error("Ledger Stream Disconnected. Reconnecting...", err);
        };
    }

    // Subscribe to specific ledger events
    on(eventType, callback) {
        if (!this.listeners[eventType]) {
            this.listeners[eventType] = [];
        }
        this.listeners[eventType].push(callback);
    }

    _dispatch(eventType, data) {
        console.log(`[LEDGER EVENT] ${eventType}:`, data);
        if (this.listeners[eventType]) {
            this.listeners[eventType].forEach(cb => cb(data));
        }
        // Also fire a wildcard event
        if (this.listeners["*"]) {
            this.listeners["*"].forEach(cb => cb(eventType, data));
        }
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            console.log("Muse Window disconnected from Universal Ledger.");
        }
    }
}

// Export for usage
window.MuseLedgerClient = MuseLedgerClient;
