# Courier External Worker Bootstrap

This package lets any Windows or Mac machine attach to a Courier Server as a replaceable worker.

## Requirements
- Python 3.10+
- Internet access to the Courier server
- No inbound ports required

## Configuration

Set the following environment variables before starting:

```bash
# Required
export COURIER_SERVER_URL="https://courier.example.com"
export COURIER_WORKER_TOKEN="your-secure-token"

# Optional
export COURIER_WORKER_ID="mac-m2-worker-1" # defaults to anonymous-worker
export COURIER_CAPABILITIES="windows,docker,gpu" # defaults to generic
export COURIER_WORKER_STATE="~/.courier_worker" # defaults to ~/.courier_worker
```

## Running the Worker

### Windows (PowerShell)
```powershell
$env:COURIER_SERVER_URL="https://courier.example.com"
$env:COURIER_WORKER_TOKEN="your-secure-token"
python deploy\worker_bootstrap.py
```

### Mac / Linux (Bash/Zsh)
```bash
export COURIER_SERVER_URL="https://courier.example.com"
export COURIER_WORKER_TOKEN="your-secure-token"
python3 deploy/worker_bootstrap.py
```

## Protocol (COMMON_PROTOCOL)
The worker polls the server using standard HTTP POST:
- `POST /api/v1/worker/poll`: Fetches a bounded TaskPacket. Returns 404 if queue is empty.
- `POST /api/v1/worker/submit`: Submits the actual DurableResult with PASS/FAIL payload.

## Resiliency (AUTO_RECONNECT)
- Implements exponential backoff (1s to 30s) on network failures or empty queues.
- bounded local logs stored in `COURIER_WORKER_STATE/worker.log` (1MB rotating).
- No hardcoded IPs or credentials.