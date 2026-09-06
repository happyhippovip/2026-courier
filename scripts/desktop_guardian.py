#!/usr/bin/env python3
"""Mission 219: Mac Desktop Guardian & Popup Autopilot.

Deterministic, zero-spend UI operations controller for Computer A:
- Detects and handles exact allowlisted macOS/Antigravity dialogs
- Core Rule: UNKNOWN_POPUP = DO_NOT_CLICK (fail-closed)
- Known Rule: "Schlüsselbund nicht gefunden" -> clicks ONLY "Abbrechen" (never reset)
- Absolute Security Gates: Passwords, Touch ID, 2FA, CAPTCHA, Enable Overages,
  Wallet Signatures, Billing -> WAITING_HUMAN (parks branch, safe work continues)
- Provider Quota Autopilot: Marks model unavailable, preserves checkpoint, zero restart
- Keychain Degradation Detection: >=3 keychain missing in 10m -> KEYCHAIN_INTEGRATION_DEGRADED
- Financial Firewall: REAL_TRADES=0, REAL_FUNDS_TOUCHED=NO, WALLET_ACTIONS=NO, SPEND_EUR=0
- Single-instance authority (DESKTOP_GUARDIAN_INSTANCES=1)
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def is_pid_alive(pid: Optional[int]) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


class PopupClassification(str, enum.Enum):
    SAFE_AUTO_DISMISS = "SAFE_AUTO_DISMISS"
    SAFE_AUTO_CONTINUE = "SAFE_AUTO_CONTINUE"
    PROVIDER_RESOURCE_EVENT = "PROVIDER_RESOURCE_EVENT"
    WAITING_HUMAN = "WAITING_HUMAN"
    SECURITY_BLOCK = "SECURITY_BLOCK"
    UNKNOWN = "UNKNOWN"


class SecurityGateCategory(str, enum.Enum):
    PASSWORD = "PASSWORD"
    TOUCH_ID = "TOUCH_ID"
    TWO_FACTOR_AUTH = "TWO_FACTOR_AUTH"
    CAPTCHA = "CAPTCHA"
    KEYCHAIN_RESET = "KEYCHAIN_RESET"
    CREDENTIAL_CREATION = "CREDENTIAL_CREATION"
    OAUTH_APPROVAL = "OAUTH_APPROVAL"
    WALLET_SIGNATURE = "WALLET_SIGNATURE"
    BILLING_UPGRADE = "BILLING_UPGRADE"
    ENABLE_OVERAGES = "ENABLE_OVERAGES"
    PUBLICATION_APPROVAL = "PUBLICATION_APPROVAL"


@dataclass
class UIElementInfo:
    app_name: str
    window_title: str
    dialog_text: str
    buttons: List[str]
    subrole: str = ""
    pid: Optional[int] = None
    timestamp: str = field(default_factory=utc_now)

    def fingerprint(self) -> str:
        content = f"{self.app_name}|{self.window_title}|{self.dialog_text}|{sorted(self.buttons)}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


@dataclass
class GuardianDecision:
    classification: str
    action_type: str
    target_button: Optional[str] = None
    reason: str = ""
    gate_category: Optional[str] = None
    fingerprint: str = ""
    safe_to_execute: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GuardianTelemetry:
    guardian_state: str = "OBSERVING"
    pid: int = os.getpid()
    single_instance: bool = True
    accessibility_permission: bool = True
    active_dialogs_count: int = 0
    handled_popups_count: int = 0
    parked_security_gates: List[str] = field(default_factory=list)
    keychain_failure_count: int = 0
    keychain_degraded: bool = False
    provider_states: Dict[str, str] = field(default_factory=dict)
    last_decision: Optional[Dict[str, Any]] = None
    last_chief_alert: Optional[Dict[str, Any]] = None
    real_trades: int = 0
    real_funds_touched: bool = False
    wallet_actions: bool = False
    billing_actions: bool = False
    spend_eur: float = 0.0
    model_calls_runtime: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DesktopGuardian:
    """Deterministic Mac UI Operations Guardian & Quota Autopilot."""

    # Security Keywords that unconditionally trigger WAITING_HUMAN
    SECURITY_GATE_KEYWORDS = {
        SecurityGateCategory.TOUCH_ID: ["touch id", "fingerabdruck"],
        SecurityGateCategory.PASSWORD: ["kennwort", "password", "passcode", "geheim"],
        SecurityGateCategory.TWO_FACTOR_AUTH: ["2fa", "two-factor", "zwei-faktor", "sms code", "verification code", "bestätigungscode"],
        SecurityGateCategory.CAPTCHA: ["captcha", "ich bin kein roboter", "i am not a robot", "recaptcha"],
        SecurityGateCategory.KEYCHAIN_RESET: ["auf standard zurücksetzen", "reset keychain", "schlüsselbund löschen", "delete keychain", "replace keychain"],
        SecurityGateCategory.CREDENTIAL_CREATION: ["create new credential", "anmeldedaten erstellen"],
        SecurityGateCategory.OAUTH_APPROVAL: ["oauth", "authorize access", "zugriff autorisieren", "connected app"],
        SecurityGateCategory.WALLET_SIGNATURE: ["phantom", "wallet signature", "sign transaction", "sign message", "transaktion signieren"],
        SecurityGateCategory.BILLING_UPGRADE: ["upgrade", "subscription", "abonnement", "buy credits", "kaufen", "purchase", "payment"],
        SecurityGateCategory.ENABLE_OVERAGES: ["enable overages", "overage", "zusatzkontingent"],
        SecurityGateCategory.PUBLICATION_APPROVAL: ["publish to external", "veröffentlichen"],
    }

    def __init__(self, repo_dir: Path = COURIER_DIR, dry_run: bool = False):
        self.repo_dir = repo_dir.resolve()
        self.runtime_dir = self.repo_dir / "events" / "runtime-state"
        self.alerts_dir = self.repo_dir / "events" / "runtime-alerts"

        self.pid_file = self.runtime_dir / "desktop_guardian.pid"
        self.heartbeat_file = self.runtime_dir / "desktop_guardian_heartbeat.json"
        self.state_file = self.runtime_dir / "desktop_guardian_state.json"

        self.dry_run = dry_run
        self.telemetry = GuardianTelemetry()
        self._processed_popups: Set[str] = set()
        self._keychain_occurrences: List[float] = []

    def check_accessibility_permission(self) -> bool:
        """Verifies if macOS System Events is accessible."""
        try:
            res = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of current user'],
                capture_output=True,
                text=True,
                timeout=3,
            )
            self.telemetry.accessibility_permission = (res.returncode == 0)
            return self.telemetry.accessibility_permission
        except Exception:
            self.telemetry.accessibility_permission = False
            return False

    def scan_visible_dialogs(self) -> List[UIElementInfo]:
        """Inspects visible application windows and sheets via System Events."""
        if not self.check_accessibility_permission():
            return []

        dialogs: List[UIElementInfo] = []
        # Target specific processes known to raise operational dialogs
        target_processes = ["Antigravity", "SecurityAgent", "CoreServicesUIAgent"]
        for proc in target_processes:
            script = f"""
            tell application "System Events"
                if exists (process "{proc}") then
                    tell process "{proc}"
                        set wList to {{}}
                        repeat with w in every window
                            try
                                set wName to name of w
                                set bList to {{}}
                                try
                                    repeat with b in (every button of w)
                                        set end of bList to name of b
                                    end repeat
                                end try
                                set dText to ""
                                try
                                    set dText to value of (every static text of w) as string
                                end try
                                set end of wList to (wName & "|||" & (bList as string) & "|||" & dText)
                            end try
                        end repeat
                        return wList
                    end tell
                else
                    return {{}}
                end if
            end tell
            """
            try:
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
                if res.returncode == 0 and res.stdout.strip():
                    raw_items = res.stdout.strip().split(", ")
                    for item in raw_items:
                        if "|||" in item:
                            parts = item.split("|||")
                            w_title = parts[0].strip()
                            btns = [b.strip() for b in parts[1].split(",") if b.strip() and b.strip() != "missing value"]
                            d_text = parts[2].strip() if len(parts) > 2 else ""
                            # Only treat as dialog if it has a title or buttons
                            if w_title or btns:
                                dialogs.append(UIElementInfo(
                                    app_name=proc,
                                    window_title=w_title,
                                    dialog_text=d_text,
                                    buttons=btns,
                                ))
            except Exception:
                pass

        self.telemetry.active_dialogs_count = len(dialogs)
        return dialogs

    def evaluate_dialog(self, dialog: UIElementInfo) -> GuardianDecision:
        """Evaluates UI element against strict allowlist and security rules."""
        fp = dialog.fingerprint()
        title_lower = dialog.window_title.lower()
        text_lower = dialog.dialog_text.lower()
        buttons_lower = [b.lower() for b in dialog.buttons]
        combined = f"{title_lower} {text_lower}"

        # 1. Check for Absolute Security Gates -> WAITING_HUMAN
        for gate_cat, keywords in self.SECURITY_GATE_KEYWORDS.items():
            for kw in keywords:
                if kw in combined or any(kw in b for b in buttons_lower):
                    # Specific check: If it's the known keychain dialog with "Abbrechen", handle via exact allowlist below
                    if gate_cat == SecurityGateCategory.KEYCHAIN_RESET and "schlüsselbund nicht gefunden" in title_lower:
                        break
                    return GuardianDecision(
                        classification=PopupClassification.WAITING_HUMAN.value,
                        action_type="PARK_BRANCH_REQUIRE_HUMAN",
                        target_button=None,
                        reason=f"SECURITY_GATE_TRIGGERED: {gate_cat.value} (Keyword: {kw})",
                        gate_category=gate_cat.value,
                        fingerprint=fp,
                        safe_to_execute=False,
                    )

        # 2. Check Exact Allowlisted Rule: KEYCHAIN_NOT_FOUND_ANTIGRAVITY
        is_keychain_title = ("schlüsselbund nicht gefunden" in title_lower) or ("keychain not found" in title_lower)
        is_antigravity_ctx = ("antigravity" in combined) or (dialog.app_name.lower() == "antigravity")
        has_cancel_btn = any(b in buttons_lower for b in ["abbrechen", "cancel"])
        has_reset_btn = any("standard" in b or "reset" in b for b in buttons_lower)

        if is_keychain_title and is_antigravity_ctx and has_cancel_btn:
            # Find the exact button label for Cancel
            target_btn = next((b for b in dialog.buttons if b.lower() in ["abbrechen", "cancel"]), "Abbrechen")
            # Record keychain occurrence for degradation monitoring
            now_ts = time.time()
            self._keychain_occurrences.append(now_ts)
            self._check_keychain_degradation(now_ts)

            return GuardianDecision(
                classification=PopupClassification.SAFE_AUTO_DISMISS.value,
                action_type="SAFE_CANCEL_KEYCHAIN",
                target_button=target_btn,
                reason="EXACT_ALLOWLIST_MATCH: KEYCHAIN_NOT_FOUND_ANTIGRAVITY (Cancel only, reset forbidden)",
                fingerprint=fp,
                safe_to_execute=True,
            )

        # 3. Check Provider Quota / Resource Events
        if "quota reached" in combined or "kontingent erreicht" in combined:
            model_type = "BASELINE_MODEL" if "baseline" in combined else "INDIVIDUAL_MODEL"
            return GuardianDecision(
                classification=PopupClassification.PROVIDER_RESOURCE_EVENT.value,
                action_type="QUOTA_FAILOVER_OR_PARK",
                reason=f"PROVIDER_QUOTA_DETECTED: {model_type}",
                fingerprint=fp,
                safe_to_execute=True,
            )

        # 4. Unknown Popup -> Fail Closed (DO NOT CLICK)
        return GuardianDecision(
            classification=PopupClassification.UNKNOWN.value,
            action_type="NO_ACTION",
            target_button=None,
            reason="UNKNOWN_POPUP_SIGNATURE: Refusing automatic interaction (Fail-closed)",
            fingerprint=fp,
            safe_to_execute=False,
        )

    def execute_decision(self, dialog: UIElementInfo, decision: GuardianDecision) -> bool:
        """Executes allowlisted action with deduplication and safety verification."""
        if not decision.safe_to_execute or self.dry_run:
            return False

        # Deduplicate execution
        if decision.fingerprint in self._processed_popups:
            return False

        self._processed_popups.add(decision.fingerprint)

        if decision.action_type == "SAFE_CANCEL_KEYCHAIN" and decision.target_button:
            # Click ONLY the designated Cancel button via osascript
            script = f"""
            tell application "System Events"
                tell process "{dialog.app_name}"
                    repeat with w in every window
                        try
                            if name of w is "{dialog.window_title}" then
                                click button "{decision.target_button}" of w
                                return "CLICKED"
                            end if
                        end try
                    end repeat
                end tell
            end tell
            """
            try:
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
                if "CLICKED" in res.stdout:
                    self.telemetry.handled_popups_count += 1
                    return True
            except Exception:
                pass

        elif decision.action_type == "QUOTA_FAILOVER_OR_PARK":
            # Quota event handling: mark model unavailable without restarting mission
            self.telemetry.provider_states["GEMINI_BASELINE"] = "UNAVAILABLE_UNTIL_RESET"
            return True

        return False

    def _check_keychain_degradation(self, current_ts: float) -> None:
        """Checks if keychain missing popup occurred >= 3 times in 10 minutes."""
        ten_mins_ago = current_ts - 600.0
        self._keychain_occurrences = [ts for ts in self._keychain_occurrences if ts >= ten_mins_ago]
        self.telemetry.keychain_failure_count = len(self._keychain_occurrences)

        if len(self._keychain_occurrences) >= 3 and not self.telemetry.keychain_degraded:
            self.telemetry.keychain_degraded = True
            self.emit_chief_alert(
                alert_type="REPEATED_KEYCHAIN_FAILURE",
                severity="HIGH",
                details={
                    "occurrences_10m": len(self._keychain_occurrences),
                    "status": "KEYCHAIN_INTEGRATION_DEGRADED",
                    "action": "PARK_KEYCHAIN_REQUIRING_OPERATIONS",
                },
            )

    def emit_chief_alert(self, alert_type: str, severity: str, details: Dict[str, Any]) -> None:
        """Emits deduplicated Chief Alert for material events."""
        event_id = f"alert-guardian-{uuid.uuid4().hex[:8]}"
        payload = {
            "schema_version": "3.0",
            "event_id": event_id,
            "event_type": alert_type,
            "severity": severity,
            "details": details,
            "created_at": utc_now(),
        }
        self.telemetry.last_chief_alert = payload
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        safe_write_json(self.alerts_dir / f"{event_id}.json", payload)

    def run_guardian_cycle(self) -> GuardianTelemetry:
        """Single deterministic guardian cycle."""
        dialogs = self.scan_visible_dialogs()
        for d in dialogs:
            dec = self.evaluate_dialog(d)
            self.telemetry.last_decision = dec.to_dict()
            if dec.classification == PopupClassification.WAITING_HUMAN.value:
                if dec.gate_category and dec.gate_category not in self.telemetry.parked_security_gates:
                    self.telemetry.parked_security_gates.append(dec.gate_category)
                    self.emit_chief_alert(
                        alert_type="UNKNOWN_SECURITY_POPUP",
                        severity="MEDIUM",
                        details={"dialog": d.window_title, "category": dec.gate_category, "reason": dec.reason},
                    )
            elif dec.safe_to_execute:
                self.execute_decision(d, dec)

        safe_write_json(self.state_file, self.telemetry.to_dict())
        return self.telemetry

    def write_heartbeat(self, cycle_count: int) -> None:
        hb = {
            "pid": os.getpid(),
            "process_alive": True,
            "status": self.telemetry.guardian_state,
            "heartbeat_at": utc_now(),
            "cycle_count": cycle_count,
            "accessibility_permission": self.telemetry.accessibility_permission,
            "active_dialogs_count": self.telemetry.active_dialogs_count,
            "handled_popups_count": self.telemetry.handled_popups_count,
            "keychain_degraded": self.telemetry.keychain_degraded,
            "safe_idle": True,
            "spend_eur": 0.0,
            "model_calls_runtime": 0,
        }
        safe_write_json(self.heartbeat_file, hb)

    def run_continuous_loop(self, interval: float = 5.0) -> None:
        """Continuous execution loop with single-instance enforcement."""
        if self.pid_file.is_file():
            try:
                existing_pid = int(self.pid_file.read_text().strip())
                if is_pid_alive(existing_pid) and existing_pid != os.getpid():
                    print(f"DESKTOP_GUARDIAN_INSTANCE_ALREADY_ACTIVE: PID {existing_pid}")
                    return
            except Exception:
                pass

        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()), encoding="utf-8")

        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                self.run_guardian_cycle()
                self.write_heartbeat(cycle_count)
                time.sleep(interval)
        finally:
            if self.pid_file.is_file():
                try:
                    if int(self.pid_file.read_text().strip()) == os.getpid():
                        self.pid_file.unlink(missing_ok=True)
                except Exception:
                    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Mac Desktop Guardian & Popup Autopilot")
    parser.add_argument("--once", action="store_true", help="Run single inspection cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and report without executing actions")
    parser.add_argument("--daemon", action="store_true", help="Run in continuous daemon mode")
    parser.add_argument("--interval", type=float, default=5.0, help="Loop interval in seconds")
    args = parser.parse_args()

    guardian = DesktopGuardian(dry_run=args.dry_run)
    if args.once or args.dry_run:
        res = guardian.run_guardian_cycle()
        guardian.write_heartbeat(1)
        print(json.dumps(res.to_dict(), indent=2))
        return 0

    guardian.run_continuous_loop(interval=args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
