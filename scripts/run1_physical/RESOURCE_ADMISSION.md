# RESOURCE ADMISSION CHECKS & PROOFS

## Requirements
To ensure predictable physical execution without OOM kills or thrashing, physical RUN scripts must measure system capacity and abort before booting if the host is overloaded.

## Core Checks
1. Available physical RAM > 1.5GB
2. System load average < 4.0
3. Available disk space on `/tmp` > 5GB

## Validation Proof Script
```bash
#!/usr/bin/env bash
# Resource Admission Control

if [ $(uname) == "Darwin" ]; then
    # RAM Check
    FREE_PAGES=$(vm_stat | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
    INACTIVE_PAGES=$(vm_stat | grep "Pages inactive" | awk '{print $3}' | sed 's/\.//')
    PAGE_SIZE=$(pagesize)
    AVAILABLE_RAM=$(( (FREE_PAGES + INACTIVE_PAGES) * PAGE_SIZE / 1024 / 1024 ))
    
    if [ "$AVAILABLE_RAM" -lt 1500 ]; then
        echo "CRITICAL: Insufficient RAM. Only ${AVAILABLE_RAM}MB available, 1500MB required."
        exit 1
    fi
    
    # Load Check
    LOAD=$(sysctl -n vm.loadavg | awk '{print $2}')
    if ( $(echo "$LOAD > 4.0" | bc -l) ); then
        echo "CRITICAL: System load too high ($LOAD). Aborting physical run."
        exit 1
    fi
fi
```
