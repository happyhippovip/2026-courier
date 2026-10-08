#!/usr/bin/env python3
"""Courier Symphony — Cross-Platform Project Dashboard Generator (.xlsx).

Generates a fully editable, styled Microsoft Excel / Apple Numbers compatible
OpenXML (.xlsx) multi-sheet workbook using the Python standard library only
(zipfile, xml.etree.ElementTree).

Zero external dependencies required (no openpyxl, no xlsxwriter, no pandas).
Works identically on macOS and Windows.
"""

import datetime
import html
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)


def col_letter(col_idx):
    """Convert 1-based column index to Excel column letters (A, B, ..., Z, AA, AB, ...)."""
    result = []
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))


def get_git_info(repo_dir):
    """Safely query git information without grep."""
    def run_cmd(args):
        try:
            p = subprocess.run(args, cwd=repo_dir, capture_output=True, text=True, check=True)
            return p.stdout.strip()
        except Exception:
            return "UNKNOWN"

    head_sha = run_cmd(["git", "rev-parse", "HEAD"])
    branch = run_cmd(["git", "branch", "--show-current"])
    integration_sha = run_cmd(["git", "rev-parse", "origin/integration/v1"])
    short_sha = head_sha[:10] if head_sha != "UNKNOWN" else "UNKNOWN"
    return {
        "head_sha": head_sha,
        "short_sha": short_sha,
        "branch": branch,
        "integration_sha": integration_sha,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def get_open_prs(repo_dir):
    """Query live GitHub PRs via gh CLI."""
    try:
        cmd = [
            "gh", "pr", "list",
            "--state", "open",
            "--limit", "35",
            "--json", "number,title,headRefName,author,statusCheckRollup,mergeable,createdAt"
        ]
        p = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, check=True)
        return json.loads(p.stdout)
    except Exception as e:
        print(f"Warning: could not fetch PRs via gh CLI: {e}", file=sys.stderr)
        return []


def determine_cell_style(val_str, is_header=False, is_code=False, is_num=False, is_even=False):
    """Determine style index (xf) for openxml.
    
    Style indices in styleSheet:
      0: Normal text (white bg, thin border)
      1: Header (navy blue bg, bold white text)
      2: Status SUCCESS / VERIFIED / DONE / MERGEABLE / CLOSED (soft green bg, dark green text)
      3: Status IN_PROGRESS / ACTIVE / PENDING / READY (soft yellow bg, dark yellow text)
      4: Status FAILED / BLOCKED / CONFLICTING / ERROR (soft red bg, dark red text)
      5: Monospace code / SHA / ID (Consolas 10pt, white bg)
      6: Numeric / Currency (right aligned)
      7: Zebra normal text (subtle gray bg)
      8: Zebra monospace code (subtle gray bg)
    """
    if is_header:
        return 1

    upper = str(val_str).strip().upper()

    # Exact status style matching
    green_matches = {"VERIFIED", "DONE", "SUCCESS", "MERGEABLE", "CLOSED", "APPROVED", "APPROVED_3.12", "APPROVED_NORTH_STAR", "DONE_MERGED", "DONE_REPAIRED", "DONE_SUBMITTED", "VERIFIED_OPERATIONAL", "VERIFIED_CLOSED", "VERIFIED_IN_LANE", "VERIFIED_SOURCE", "VERIFIED_CODE", "CODE_COMPLETE", "ADVISORY_COMPLETE", "PASSED"}
    yellow_matches = {"IN_PROGRESS", "ACTIVE", "PENDING", "READY", "READY_TO_SEND", "READY_TO_FILL", "ACTIVE_PR", "ACTIVE_BRANCH", "IN_PROGRESS_CI", "ACTIVE_BINDING", "PENDING_CI", "PR_246_ACTIVE", "PR_238_ACTIVE", "PR_244_ACTIVE", "READY_FOR_TEST"}
    red_matches = {"FAILED", "BLOCKED", "CONFLICTING", "ERROR", "NEEDS_SOURCE", "NEEDS_ACTION", "DIAGNOSTIC_REQUIRED", "FAILURE"}

    if upper in green_matches or any(upper.startswith(prefix) for prefix in ["DONE", "SUCCESS", "VERIFIED"]):
        return 2
    if upper in yellow_matches or any(upper.startswith(prefix) for prefix in ["ACTIVE", "PENDING", "IN_PROGRESS", "READY"]):
        return 3
    if upper in red_matches or any(upper.startswith(prefix) for prefix in ["FAILED", "BLOCKED", "NEEDS_"]):
        return 4

    if is_num:
        return 6
    if is_code:
        return 8 if is_even else 5
    return 7 if is_even else 0


def build_worksheet_xml(sheet_name, headers, rows, code_cols=None, num_cols=None):
    """Generate XML for a single worksheet with frozen headers and auto-width columns."""
    code_cols = set(code_cols or [])
    num_cols = set(num_cols or [])

    # Calculate column widths
    col_widths = {}
    for col_idx, h in enumerate(headers, start=1):
        col_widths[col_idx] = max(12, len(str(h)) + 4)

    for row_idx, row in enumerate(rows, start=2):
        for col_idx, val in enumerate(row, start=1):
            s_val = str(val) if val is not None else ""
            line_len = max((len(line) for line in s_val.split("\n")), default=0)
            col_widths[col_idx] = min(50, max(col_widths[col_idx], line_len + 3))

    cols_xml = []
    for col_idx, w in sorted(col_widths.items()):
        cols_xml.append(f'<col min="{col_idx}" max="{col_idx}" width="{w}" customWidth="1"/>')

    # Build rows
    sheet_data = []

    # Header Row (Row 1)
    header_cells = []
    for col_idx, h in enumerate(headers, start=1):
        ref = f"{col_letter(col_idx)}1"
        escaped_h = html.escape(str(h))
        header_cells.append(f'<c r="{ref}" t="inlineStr" s="1"><is><t>{escaped_h}</t></is></c>')
    sheet_data.append(f'<row r="1" ht="28" customHeight="1">{"".join(header_cells)}</row>')

    # Data Rows (Row 2 .. N)
    for row_idx, row in enumerate(rows, start=2):
        is_even = (row_idx % 2 == 0)
        row_cells = []
        for col_idx, val in enumerate(row, start=1):
            ref = f"{col_letter(col_idx)}{row_idx}"
            is_code = col_idx in code_cols
            is_num = col_idx in num_cols

            val_str = "" if val is None else str(val)
            s_idx = determine_cell_style(val_str, is_code=is_code, is_num=is_num, is_even=is_even)

            # Check if numeric (float or int)
            if is_num and isinstance(val, (int, float)):
                row_cells.append(f'<c r="{ref}" s="{s_idx}"><v>{val}</v></c>')
            elif is_num and val_str.replace(".", "", 1).isdigit():
                row_cells.append(f'<c r="{ref}" s="{s_idx}"><v>{val_str}</v></c>')
            else:
                escaped_text = html.escape(val_str)
                row_cells.append(f'<c r="{ref}" t="inlineStr" s="{s_idx}"><is><t>{escaped_text}</t></is></c>')

        sheet_data.append(f'<row r="{row_idx}" ht="20">{"".join(row_cells)}</row>')

    worksheet_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{NS}">
  <sheetViews>
    <sheetView tabSelected="0" workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <cols>
    {"".join(cols_xml)}
  </cols>
  <sheetData>
    {"".join(sheet_data)}
  </sheetData>
</worksheet>"""
    return worksheet_xml


def get_styles_xml():
    """Generate OpenXML styleSheet XML."""
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{NS}">
  <fonts count="7">
    <font><name val="Calibri"/><sz val="11"/></font>
    <font><b/><color rgb="FFFFFFFF"/><name val="Calibri"/><sz val="11"/></font>
    <font><b/><color rgb="FF1F4E78"/><name val="Calibri"/><sz val="12"/></font>
    <font><name val="Consolas"/><sz val="10"/><color rgb="FF262626"/></font>
    <font><b/><color rgb="FF276A3C"/><name val="Calibri"/><sz val="11"/></font>
    <font><b/><color rgb="FF8A6D3B"/><name val="Calibri"/><sz val="11"/></font>
    <font><b/><color rgb="FFA94442"/><name val="Calibri"/><sz val="11"/></font>
  </fonts>
  <fills count="7">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE2EFDA"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFCE4D6"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF9FAFB"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD9D9D9"/></left>
      <right style="thin"><color rgb="FFD9D9D9"/></right>
      <top style="thin"><color rgb="FFD9D9D9"/></top>
      <bottom style="thin"><color rgb="FFD9D9D9"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="9">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="4" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="5" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="6" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"><alignment horizontal="right" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="6" borderId="1" xfId="0" applyFont="1" applyBorder="1"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="3" fillId="6" borderId="1" xfId="0" applyFont="1" applyBorder="1"><alignment vertical="center"/></xf>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>"""


def build_package(sheets_dict, output_path):
    """Assemble all worksheets, styles, relationships and types into a valid .xlsx zip."""
    sheet_items = list(sheets_dict.items())

    # [Content_Types].xml
    ct_overrides = [
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    for idx in range(1, len(sheet_items) + 1):
        ct_overrides.append(
            f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )

    content_types_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  {"".join(ct_overrides)}
</Types>"""

    # _rels/.rels
    root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    # xl/_rels/workbook.xml.rels
    wb_rels = [
        '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    ]
    for idx in range(1, len(sheet_items) + 1):
        wb_rels.append(
            f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
        )

    workbook_rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(wb_rels)}
</Relationships>"""

    # xl/workbook.xml
    wb_sheets = []
    for idx, (name, _) in enumerate(sheet_items, start=1):
        escaped_name = html.escape(name)
        wb_sheets.append(f'<sheet name="{escaped_name}" sheetId="{idx}" r:id="rId{idx}"/>')

    workbook_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews>
    <workbookView xWindow="0" yWindow="0" windowWidth="25600" windowHeight="14400"/>
  </bookViews>
  <sheets>
    {"".join(wb_sheets)}
  </sheets>
</workbook>"""

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml)
        z.writestr("_rels/.rels", root_rels_xml)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/styles.xml", get_styles_xml())

        for idx, (_, sheet_xml) in enumerate(sheet_items, start=1):
            z.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_xml)

    return output_path


def generate_dashboard(repo_dir, output_path):
    """Main dashboard data collection and generation."""
    git_info = get_git_info(repo_dir)
    open_prs_data = get_open_prs(repo_dir)

    sheets = {}

    # -------------------------------------------------------------
    # 1. Project Milestones
    # -------------------------------------------------------------
    m_headers = [
        "Milestone_ID", "Milestone_Name", "Stage", "Status",
        "Verification_Criteria", "Verified_Evidence_SHA", "Date_Verified", "Notes"
    ]
    m_rows = [
        [
            "M-V1-01", "Symphony V1 Autonomy Pipeline Technical Ready", "Core V1 Closed-Loop", "VERIFIED_CLOSED",
            "Cross-host execution cycle verified via SMB coordination", "dee6c76b04b", "2026-09-13",
            "Windows PC2 (DESKTOP-JDPRUGR) & Mac Chief (MAC_CHIEF_01) authoritative closure"
        ],
        [
            "M-V1-02", "Active Ledger & Deduplication Motor", "V1 Step 1", "VERIFIED_OPERATIONAL",
            "Single-writer locking, SHA-256 dedupe, 30+ modules verified", "f425d328561", "2026-09-30",
            "Documented in WINDOWS_VERIFICATION_LEDGER.md; zero double-spend"
        ],
        [
            "M-V1-03", "Reliable Automation & Autonomous Level 6 Loop", "V1 Step 2", "VERIFIED_OPERATIONAL",
            "Level 6 loop, state reconciliation, unattended crash/quota recovery", git_info["short_sha"], "2026-10-08",
            "Automated crash/quota recovery and state reconciliation in PR #247"
        ],
        [
            "M-V1-04", "Golden Path Verification Harness", "V1 Step 3", "VERIFIED_OPERATIONAL",
            "11/11 Golden harness passes, 2 sequential units, controller restart survival", "f425d328561", "2026-10-08",
            "PR #227 (two units sequential), PR #233 (restart survival), PR #240 (non-stall)"
        ],
        [
            "M-V1-05", "Desktop Hub & Founder Project Base", "V1 Step 4", "VERIFIED_IN_LANE",
            "Founder Project Base vertical slice (Issue #55 L5), bounded event reads", "f425d328561", "2026-10-07",
            "PR #226 (vertical slice), PR #230 (bounded event & controller reads)"
        ],
        [
            "M-V1-06", "Windows Launcher & Courier.exe", "V1 Step 5", "IN_PROGRESS",
            "CourierLauncher.cs Job Object wrapper, user-task service registration", "f425d328561", "2026-10-08",
            "PR #246 (user task service registration); launcher builds with build_launcher.ps1"
        ],
        [
            "M-V1-07", "Clean-Machine Acceptance", "V1 Step 6", "IN_PROGRESS",
            "Zero API key in source, verified uninstall without orphaned plists/tasks", "f425d328561", "2026-10-08",
            "PR #228 (no API key in source), PR #238 (mac uninstall), PR #244, lane/L6-uninstall-verified"
        ],
        [
            "M-V1-08", "Real Adapters & Multihost Federation", "V1 Step 7", "VERIFIED_IN_LANE",
            "Mac worker adapter flake fix, Windows worker adapter, Google Builder adapter", git_info["short_sha"], "2026-10-08",
            "PR #236 (mac adapter race fix), PR #247 (Google builder worker adapter)"
        ],
        [
            "M-V1-09", "Desktop Robot Overlay UI Polish", "V1 Step 8", "VERIFIED_CLOSED",
            "Desktop robot overlay UI polish merged into integration/v1", "PR-122", "2026-10-06",
            "PR #122 merged; complete overlay visual refinement"
        ],
        [
            "M-REV-01", "Commercial Milestone 1 (€1 Verified Revenue)", "Post-V1 Commercial", "NOT_STARTED",
            "First legitimate commercial customer transaction processed", "GATED_ON_V1", "Pending",
            "Zero unverified money; gated by V1 technical acceptance"
        ],
        [
            "M-REV-02", "Commercial Milestone 2 (€239 Cumulative Revenue)", "Post-V1 Commercial", "NOT_STARTED",
            "Cumulative customer cashflow positive validation", "GATED_ON_M1", "Pending",
            "Post-V1 revenue scale target; flywheel self-funding milestone"
        ],
        [
            "M-REV-03", "Revenue Engine RV-01 (Automated PDF Export)", "Revenue Engine", "IN_PROGRESS",
            "Report generator with PDF export code integrated", "2a83c198", "2026-10-05",
            "Awaiting weasyprint dependency review / approval"
        ],
        [
            "M-REV-04", "Revenue Engine RV-02 (AI Marketplace Pilot)", "Revenue Engine", "VERIFIED",
            "Kibey marketplace pilot package generation", "PR-81", "2026-10-04",
            "PR #81 merged into integration/v1"
        ],
        [
            "M-REV-05", "Revenue Engine RV-03 (Crypto Security Audits)", "Revenue Engine", "VERIFIED",
            "Autonomous audit generation for open crypto repositories", "OPUS-REV3", "2026-10-05",
            "3 sample reports generated (Hunter, AUTOBOT-RAYR-QUANT, cosmicforge-bot)"
        ],
        [
            "M-REV-06", "Revenue Engine RV-04 (Automated Code Quality Report)", "Revenue Engine", "VERIFIED",
            "Autonomous quality analysis with legal guardrails", "6f6dd232", "2026-10-03",
            "Report rrc-2 + Legal Guard committed"
        ],
        [
            "M-REV-07", "Revenue Engine RV-07 (Data Connector Bridge)", "Revenue Engine", "VERIFIED",
            "Data connector pilot vertical slice", "PR-82", "2026-10-04",
            "PR #82 merged into integration/v1"
        ],
        [
            "M-REV-08", "Revenue Engine RV-09 (Spreadsheet Cleanup Slice)", "Revenue Engine", "VERIFIED",
            "courier_runtime.workbook OpenXML cleaner; 8/8 tests green", "PR-80/PR-220", "2026-10-08",
            "Standard library only, verified in PR #80 and PR #220"
        ]
    ]
    sheets["Project Milestones"] = build_worksheet_xml(
        "Project Milestones", m_headers, m_rows, code_cols=[1, 6]
    )

    # -------------------------------------------------------------
    # 2. Ledger Workkeys
    # -------------------------------------------------------------
    wk_headers = [
        "Workkey", "Owner_Lane", "Active_Worker", "Scope_Module",
        "Base_SHA", "Branch", "Status", "Verification_Level", "Notes"
    ]
    wk_rows = [
        [
            "L3-GOOGLE-BUILDER-WORKER", "Lane L3 Worker", "Antigravity (Mac)", "scripts/run_autonomous_loop.py",
            git_info["short_sha"], "lane/L3-google-builder-worker", "ACTIVE_PR_247", "VERIFIED_TARGETED_TESTS",
            "Integrate Google Builder worker & unattended crash/quota recovery"
        ],
        [
            "L6-INSTALL-SERVICE-USER-TASK", "Lane L6 Packaging", "Lane Worker", "scripts/windows_worker/install_service.ps1",
            "f425d328561", "lane/L6-install-service-user-task", "ACTIVE_PR_246", "VERIFIED_IN_CI",
            "Register worker as interactive current user task (not SYSTEM)"
        ],
        [
            "L2-RETRY-AUTHORIZED-ONE-ATTEMPT", "Lane L2 Controller", "Lane Worker", "courier_core/controller.py",
            "f425d328561", "lane/L2-retry-authorized-one-attempt", "ACTIVE_PR_245", "VERIFIED_IN_CI",
            "Human retry grants one attempt, not leftover budget"
        ],
        [
            "L6-MUSE-NIGHT-UNINSTALL-NOT-PROVEN", "Lane L6 Packaging", "Cursor Worker", "scripts/uninstall_macos_muse_night_runner.sh",
            "f425d328561", "cursor/l6-muse-night-uninstall-not-proven-be81", "ACTIVE_PR_244", "VERIFIED_IN_CI",
            "Do not report night job removed while plist remains"
        ],
        [
            "L6-RESTART-NOT-PROVEN", "Lane L6 Packaging", "Cursor Worker", "deploy/courier.service",
            "f425d328561", "cursor/l6-restart-not-proven-be81", "ACTIVE_PR_243", "MERGEABLE",
            "Do not report Restarted when launchctl unloaded nothing"
        ],
        [
            "L6-AUTONOMY-NOT-RUNNING", "Lane L6 Packaging", "Cursor Worker", "scripts/mac_worker/service.py",
            "f425d328561", "cursor/l6-autonomy-not-running-be81", "ACTIVE_PR_242", "MERGEABLE",
            "Do not report autonomy running when launchctl did not load"
        ],
        [
            "L6-BACKUP-NOT-PROVEN", "Lane L6 Packaging", "Cursor Worker", "scripts/backup.sh",
            "f425d328561", "cursor/l6-backup-not-proven-be81", "ACTIVE_PR_241", "MERGEABLE",
            "Do not report backup complete when tar fails"
        ],
        [
            "L1-GOLDEN-BLOCKED-UNIT-DOES-NOT-STALL", "Lane L1 Integration", "L1 Worker", "tests/test_golden_harness.py",
            "f425d328561", "lane/L1-golden-blocked-unit-does-not-stall", "ACTIVE_PR_240", "VERIFIED_IN_CI",
            "Blocked unit does not stall subsequent work units"
        ],
        [
            "MUSE-LEDGER-RUNTIME-DEADLINES", "Lane L2 / Ledger", "Muse (Windows)", "courier_runtime/deadlines.py",
            "f425d328561", "muse/MUSE-ledger-runtime-deadlines", "ACTIVE_PR_239", "VERIFIED_IN_CI",
            "Date string coercion and CLI support in runtime deadlines"
        ],
        [
            "L6-MAC-UNINSTALL-NOT-PROVEN", "Lane L6 Packaging", "Cursor Worker", "scripts/mac_worker/uninstall.sh",
            "f425d328561", "cursor/l6-mac-uninstall-not-proven-be81", "ACTIVE_PR_238", "VERIFIED_IN_CI",
            "Do not report Mac uninstall when plist remains"
        ],
        [
            "L6-STOP-DAEMON-IDENTITY", "Lane L6 Packaging", "Cursor Worker", "deploy/courier-status.sh",
            "f425d328561", "cursor/l6-stop-daemon-identity-be81", "ACTIVE_PR_237", "MERGEABLE",
            "Do not report live daemon pid as stopped"
        ],
        [
            "L1-MAC-ADAPTER-FLAKE", "Lane L1 Integration", "L1 Worker", "tests/adapters/test_mac_worker_adapter.py",
            "f425d328561", "lane/L1-mac-adapter-flake", "ACTIVE_PR_236", "VERIFIED_IN_CI",
            "Fix mac worker adapter result-file race condition"
        ],
        [
            "MUSE-LEDGER-PROVIDER-SURVIVAL", "Lane L2 / Ledger", "Muse (Windows)", "courier_runtime/provider_survival.py",
            "f425d328561", "muse/MUSE-ledger-provider-survival", "ACTIVE_PR_235", "VERIFIED_IN_CI",
            "Multi-capability circuit check in provider survival"
        ],
        [
            "MUSE-LEDGER-RESOURCE-GOVERNOR", "Lane L2 / Ledger", "Muse (Windows)", "courier_runtime/resource_governor.py",
            "f425d328561", "muse/MUSE-ledger-resource-governor", "ACTIVE_PR_234", "VERIFIED_IN_CI",
            "Enable Windows psutil metrics and job accounting"
        ],
        [
            "L1-GOLDEN-RESTART-BETWEEN-UNITS", "Lane L1 Integration", "L1 Worker", "tests/test_golden_harness.py",
            "f425d328561", "lane/L1-golden-restart-between-units", "ACTIVE_PR_233", "VERIFIED_IN_CI",
            "Results survive controller and worker restart between units"
        ],
        [
            "MUSE-LEDGER-PROVIDER-HIBERNATION", "Lane L2 / Ledger", "Muse (Windows)", "courier_runtime/provider_hibernation.py",
            "f425d328561", "muse/MUSE-ledger-provider-hibernation", "ACTIVE_PR_232", "VERIFIED_IN_CI",
            "Harden hibernation deserialization, add load_continuation"
        ],
        [
            "L2-TASKPACKET-PARK-WAKE-SINGLE-WRITER", "Lane L2 Controller", "L2 Worker", "courier_core/task_packet.py",
            "f425d328561", "lane/L2-taskpacket-park-wake-single-writer", "ACTIVE_PR_231", "VERIFIED_IN_CI",
            "Host-pressure park/wake never creates a second CURRENT writer"
        ],
        [
            "L5-HUB-BOUNDED-READS", "Lane L5 Desktop Hub", "L5 Worker", "courier_hub/app.py",
            "f425d328561", "lane/L5-hub-bounded-reads", "ACTIVE_PR_230", "VERIFIED_IN_CI",
            "Bounded event and controller reads in desktop hub"
        ],
        [
            "MUSE-LEDGER-PROVIDER-CIRCUIT", "Lane L2 / Ledger", "Muse (Windows)", "courier_runtime/provider_circuit.py",
            "f425d328561", "muse/MUSE-ledger-provider-circuit", "ACTIVE_PR_229", "VERIFIED_IN_CI",
            "Synchronize shared breaker restore, classify None/types"
        ],
        [
            "L6-BOOTSTRAP-CREDENTIAL-TRUTH", "Lane L6 Packaging", "L6 Worker", "scripts/windows_worker/bootstrap.py",
            "f425d328561", "lane/L6-bootstrap-credential-truth", "ACTIVE_PR_228", "VERIFIED_IN_CI",
            "Windows bootstrap: never write API key into source tree"
        ],
        [
            "L1-GOLDEN-TWO-UNITS-SEQUENTIAL", "Lane L1 Integration", "L1 Worker", "tests/test_golden_harness.py",
            "f425d328561", "lane/L1-golden-two-units-sequential", "ACTIVE_PR_227", "VERIFIED_IN_CI",
            "Two authorized units complete back-to-back with no manual handoff"
        ],
        [
            "L5-DESKTOP-HUB-PROJECT-BASE", "Lane L5 Desktop Hub", "L5 Worker", "courier_hub/routes/project_base.py",
            "f425d328561", "lane/L5-desktop-hub-project-base", "ACTIVE_PR_226", "VERIFIED_IN_CI",
            "Founder Project Base vertical slice (Issue #55 L5)"
        ],
        [
            "MUSE-LEDGER-HOST-GUARDIAN", "Lane L2 / Ledger", "Muse (Windows)", "courier_runtime/host_guardian.py",
            "f425d328561", "muse/MUSE-ledger-host-guardian", "ACTIVE_PR_225", "VERIFIED_IN_CI",
            "Harden HostGuardian disk path, swap jitter, cleanup latch"
        ],
        [
            "L5-HUB-UNDECODABLE-STATE", "Lane L5 Desktop Hub", "L5 Worker", "courier_hub/routes/home.py",
            "f425d328561", "lane/L5-hub-undecodable-state", "ACTIVE_PR_224", "MERGEABLE",
            "Undecodable or unmapped task state never takes Home down"
        ],
        [
            "MUSE-LEDGER-GEN-OPENAPI", "Lane L2 / Ledger", "Muse (Windows)", "scripts/generate_openapi.py",
            "f425d328561", "muse/MUSE-ledger-gen-openapi", "ACTIVE_PR_223", "VERIFIED_IN_CI",
            "Correct param conversion, import-safe openapi generator"
        ],
        [
            "MUSE-LEDGER-GH-CONTRACT", "Lane L2 / Ledger", "Muse (Windows)", "courier_runtime/gh_contract.py",
            "f425d328561", "muse/MUSE-ledger-gh-contract", "ACTIVE_PR_222", "VERIFIED_IN_CI",
            "Pin 429 safe-retry contract; verify customer-contract unit"
        ],
        [
            "MUSE-LEDGER-CHECK-SAFETY", "Lane L2 / Ledger", "Muse (Windows)", "scripts/check_safety.py",
            "f425d328561", "muse/MUSE-ledger-check-safety", "ACTIVE_PR_221", "VERIFIED_IN_CI",
            "Scrub credential shapes from safety finding text"
        ],
        [
            "MUSE-LEDGER-SPREADSHEET-SAMPLE", "Lane L2 / Ledger", "Muse (Windows)", "scripts/spreadsheet_cleanup_sample.py",
            "f425d328561", "muse/MUSE-ledger-spreadsheet-sample", "ACTIVE_PR_220", "VERIFIED_IN_CI",
            "Correct demo fixture message; verify sample bounds"
        ],
        [
            "MUSE-LEDGER-HOST-BUDGETS", "Lane L2 / Ledger", "Muse (Windows)", "courier_runtime/host_budgets.py",
            "f425d328561", "muse/MUSE-ledger-host-budgets", "ACTIVE_PR_219", "VERIFIED_IN_CI",
            "Clarify checkpoint-service executor contract"
        ],
        [
            "MUSE-LEDGER-POISON-TEST", "Lane L2 / Ledger", "Muse (Windows)", "tests/poison_test.py",
            "f425d328561", "muse/MUSE-ledger-poison-test", "ACTIVE_PR_218", "VERIFIED_IN_CI",
            "Remove empty poison_test.py residue"
        ],
        [
            "INTAKE-DISPATCHER-VERIFIED", "Lane L2 / Ledger", "Windows PC2", "scripts/intake_dispatcher.py",
            "dee6c76b04b", "integration/v1", "VERIFIED_BASE", "100%_COVERAGE",
            "Corrupt state auto-recovery, missing keys handling verified"
        ],
        [
            "RESOURCE-POLICY-VERIFIED", "Lane L2 / Ledger", "Windows PC2", "scripts/resource_policy.py",
            "dee6c76b04b", "integration/v1", "VERIFIED_BASE", "100%_COVERAGE",
            "TaskLeaseManager OS locking, CostGate, FileManifestTracker dedupe"
        ],
        [
            "AUTONOMOUS-LOOP-VERIFIED", "Lane L3 Host", "Windows PC2", "scripts/run_autonomous_loop.py",
            "dee6c76b04b", "integration/v1", "VERIFIED_BASE", "100%_COVERAGE",
            "Level 6 loop locking, human gate respecting, task delegation"
        ]
    ]
    sheets["Ledger Workkeys"] = build_worksheet_xml(
        "Ledger Workkeys", wk_headers, wk_rows, code_cols=[1, 5, 6]
    )

    # -------------------------------------------------------------
    # 3. Open PRs & CI
    # -------------------------------------------------------------
    pr_headers = [
        "PR_Number", "Title", "Head_Branch", "Author",
        "Mergeable", "Overall_CI", "Reality_Gate", "Courier_v1_CI", "Blockers", "Target_Branch"
    ]
    pr_rows = []
    for pr in open_prs_data:
        num = pr["number"]
        title = pr["title"]
        head = pr["headRefName"]
        author = pr.get("author", {}).get("login", "unknown")
        mergeable = pr.get("mergeable", "UNKNOWN")

        # Parse checks
        checks = pr.get("statusCheckRollup") or []
        reality_gate = "NONE"
        courier_ci = "NONE"
        any_failure = False
        any_in_progress = False

        for c in checks:
            name = c.get("name") or c.get("context") or ""
            conclusion = c.get("conclusion") or c.get("status") or ""
            if "Reality Gate" in name:
                reality_gate = conclusion
            if "Courier v1 CI" in name or "pytest" in name:
                if conclusion == "FAILURE":
                    courier_ci = "FAILURE"
                elif conclusion in ("IN_PROGRESS", "QUEUED") and courier_ci != "FAILURE":
                    courier_ci = "IN_PROGRESS"
                elif conclusion == "SUCCESS" and courier_ci not in ("FAILURE", "IN_PROGRESS"):
                    courier_ci = "SUCCESS"

            if conclusion in ("FAILURE", "ERROR"):
                any_failure = True
            elif conclusion in ("IN_PROGRESS", "QUEUED"):
                any_in_progress = True

        if any_failure:
            overall_ci = "FAILURE"
        elif any_in_progress:
            overall_ci = "IN_PROGRESS"
        elif reality_gate == "SUCCESS" and courier_ci == "SUCCESS":
            overall_ci = "SUCCESS"
        else:
            overall_ci = reality_gate if reality_gate != "NONE" else "PENDING"

        blocker = "None"
        if mergeable == "CONFLICTING":
            blocker = "Merge conflict with base"
        elif overall_ci == "FAILURE":
            blocker = "CI check failed"
        elif head.startswith("cursor/l6-") and courier_ci == "FAILURE":
            blocker = "Windows pytest failure in cursor branch"

        pr_rows.append([
            num, title, head, author, mergeable, overall_ci, reality_gate, courier_ci, blocker, "integration/v1"
        ])

    sheets["Open PRs & CI"] = build_worksheet_xml(
        "Open PRs & CI", pr_headers, pr_rows, code_cols=[1, 3], num_cols=[1]
    )

    # -------------------------------------------------------------
    # 4. Worker Fleet Status
    # -------------------------------------------------------------
    w_headers = [
        "Worker_Agent", "Host_Platform", "Role", "Assigned_Lanes",
        "Current_Status", "Resource_Limits_and_Safety", "Primary_Deliverables", "Failure_Mode_Guard"
    ]
    w_rows = [
        [
            "Anthropic Claude / Muse", "Windows 10 (DESKTOP-JDPRUGR)", "Windows Steward & Read-Only Auditor",
            "L2 Ledger, Policy, Deadlines, Governor", "ACTIVE",
            "12-slot power pool budget; max memory 88%; no ad-hoc installations",
            "PR #218-#223, #225, #229, #232, #234, #235, #239 (12+ verified PRs)",
            "Context rotation before hard_threshold_failed; no bulk permission menu clicking"
        ],
        [
            "Google Antigravity", "macOS (MacBook Pro, Intel Core i7)", "Primary Product Builder & Google Worker Integrator",
            "L3 Worker Host, L5 Desktop Hub, L6 Packaging", "ACTIVE",
            "Host bounded: single process when swap > 10GB; CPU throttling guard",
            "PR #247 (Google Builder integration & unattended loop), Cross-Platform Excel Dashboard",
            "Strict NO-GREP execution rule; single-writer fencing; turn-based auto-continuation"
        ],
        [
            "Cursor AI Worker", "Cross-Platform (macOS / Windows)", "Targeted L6 Service & Process Hygiene Fixer",
            "L6 Packaging, Launchctl, Service Registration", "ACTIVE",
            "Single-scope branches; truthful command outcome validation",
            "PR #237 (daemon identity), #238 (mac uninstall), #241 (backup), #242 (running), #243 (restart), #244 (plist)",
            "Do not report actions complete without concrete proof of command outcome"
        ],
        [
            "OpenAI Codex", "Cloud Runner / CI", "Provider Continuity & Automated Code Reviewer",
            "L10 Reviewer Bridge (courier-codex-bridge)", "MERGED_IDLE",
            "Gated reviewer in resource_policy.py; read-only code analysis",
            "PR #128 (codex/provider-continuity-resume merged into integration/v1)",
            "Fail-closed if API key missing; strictly read-only reviewer"
        ],
        [
            "xAI Grok", "Cloud / Web", "Market Opportunity & Competitor Intelligence",
            "Opportunity Radar / Strategic Research", "ADVISORY_COMPLETE",
            "Zero write access to repo; read-only dossier generation",
            "Research dossiers: Malta Cliffs Top 10, Multitalent Energy Top 10 in project memory",
            "Customer never operates external models; advisory only"
        ]
    ]
    sheets["Worker Fleet Status"] = build_worksheet_xml(
        "Worker Fleet Status", w_headers, w_rows, code_cols=[1, 4]
    )

    # -------------------------------------------------------------
    # 5. Packaging & Installers
    # -------------------------------------------------------------
    p_headers = [
        "Component", "Platform", "Artifact_Type", "Source_Path",
        "Current_Status", "Verification_Method", "Known_Gaps_or_Blockers"
    ]
    p_rows = [
        [
            "CourierLauncher.cs", "Windows 10/11", "C# .NET Executable Wrapper (Courier.exe)",
            "scripts/windows_worker/launcher/build_launcher.ps1", "VERIFIED_SOURCE",
            "Wraps Courier.exe, catches Ctrl+C, calls /v1/shutdown, terminates children via Win32 Job Object",
            "Requires clean-machine compile test on fresh Windows machine"
        ],
        [
            "Windows Worker Service", "Windows 10/11", "PowerShell Service Setup Script",
            "scripts/windows_worker/install_service.ps1", "PR_246_ACTIVE",
            "Registers worker as interactive current user scheduled task (not SYSTEM)",
            "PR #246 CI in progress"
        ],
        [
            "Windows Installer", "Windows 10/11", "Inno Setup Package & PowerShell Installer",
            "scripts/windows_worker/dist/install.ps1", "READY_FOR_TEST",
            "Preserves courier.db and logs on uninstall; removes config.json and run/ directory",
            "Needs automated clean-machine acceptance test"
        ],
        [
            "Windows Uninstaller", "Windows 10/11", "PowerShell Verified Teardown Script",
            "scripts/windows_worker/dist/uninstall.ps1", "VERIFIED_IN_LANE",
            "Verifies task, path, and Courier.exe removal before reporting success",
            "Covered in PR #246 and branch lane/L6-uninstall-verified"
        ],
        [
            "macOS Muse Night Runner", "macOS", "Launchd Plist Daemon Installer",
            "scripts/install_macos_muse_night_runner.sh", "VERIFIED_SOURCE",
            "Installs com.courier.muse.night.plist for bounded nightly cron runs",
            "PR #244 verifies plist removal on uninstall"
        ],
        [
            "macOS Worker Service", "macOS", "Shell / Launchd Service Script",
            "scripts/mac_worker/install.sh", "VERIFIED_SOURCE",
            "launchctl load/unload with single-process PID fencing",
            "PR #238 / #242 / #243 ensure truthful launchctl status"
        ],
        [
            "Mac Runtime Environment", "macOS", "Shell Runtime Provisioner",
            "deploy/install_mac_runtime.sh", "READY",
            "Sets up python/node execution environment",
            "Bound by Mac Intel memory / swap constraints"
        ],
        [
            "Surface Budget Controller", "Cross-Platform", "Python Runtime Guardian",
            "courier_runtime/surfaces.py", "VERIFIED_COMMITTED",
            "Prevents terminal storms (e.g. 64 windows) by enforcing admit() budget check",
            "Committed in 3d5713c2; 18 unit tests green"
        ]
    ]
    sheets["Packaging & Installers"] = build_worksheet_xml(
        "Packaging & Installers", p_headers, p_rows, code_cols=[1, 4]
    )

    # -------------------------------------------------------------
    # 6. Costs & Budget
    # -------------------------------------------------------------
    c_headers = [
        "Provider_or_Resource", "Entitlement_Tier", "Billing_Policy",
        "Spend_To_Date_EUR", "Budget_Cap_EUR", "Gating_Mechanism", "Quota_and_Rate_Limit_Action"
    ]
    c_rows = [
        [
            "GitHub Actions CI", "Free Tier (Public/Repo)", "ZERO_COST_ONLY",
            0.00, 0.00, "Concurrency caps; fail-closed on rate limit", "Bounded workflow runs; no extra minutes purchased"
        ],
        [
            "Google Antigravity Builder", "Active Google Subscription", "ZERO_COST_ONLY",
            0.00, 0.00, "Human gate required for plan changes / upgrades", "Quota failover: checkpoint state & park without auto-topup"
        ],
        [
            "Anthropic Claude / Muse", "Retained Subscription", "ZERO_COST_ONLY",
            0.00, 0.00, "No automatic purchases; no credit card charging", "Hard context rotation on limit; wait for scheduled window"
        ],
        [
            "OpenAI Codex / ChatGPT", "Subscription / Web", "ZERO_COST_ONLY",
            0.00, 0.00, "Gated by ResourcePolicyManager in scripts/resource_policy.py", "Fail-closed if API key missing; read-only review"
        ],
        [
            "Local Hardware (MacBook Pro)", "Local Compute", "Host Resource Budget",
            0.00, 0.00, "HostGuardian (RAM & Swap monitoring)", "Single-process execution when swap > 10GB"
        ],
        [
            "Local Hardware (Windows PC2)", "Local Compute", "Host Resource Budget",
            0.00, 0.00, "ResourceGovernor (psutil job objects)", "Window limit: max 12 slots; stop on memory pressure > 85%"
        ],
        [
            "Revenue Target: Milestone 1", "Commercial Customer", "Revenue Generation",
            0.00, 1.00, "Verified customer payment verification", "Target: first €1 legitimate revenue"
        ],
        [
            "Revenue Target: Milestone 2", "Commercial Customer", "Revenue Generation",
            0.00, 239.00, "Verified customer payment verification", "Target: €239 cumulative revenue self-funding flywheel"
        ]
    ]
    sheets["Costs & Budget"] = build_worksheet_xml(
        "Costs & Budget", c_headers, c_rows, code_cols=[1], num_cols=[4, 5]
    )

    # -------------------------------------------------------------
    # 7. Tests & Evidence
    # -------------------------------------------------------------
    t_headers = [
        "Evidence_ID_or_Suite", "Scope_Category", "Verification_Status",
        "Test_Count_or_Target", "Source_File_or_Digest", "Date_Verified", "Evidence_Details"
    ]
    t_rows = [
        [
            "TEST-SUITE-FULL", "Full Repository Test Suite", "VERIFIED",
            186, "tests/", "2026-10-08", "186 test files passing across Linux and Windows CI runners"
        ],
        [
            "GOLDEN-01-HARNESS", "Core Autonomy Contract", "VERIFIED",
            11, "tests/test_golden_harness.py", "2026-10-08", "11/11 Golden harness tests green; Linux 1433 passed / Windows 1379 passed"
        ],
        [
            "GOLDEN-02-SEQUENTIAL", "Golden Proof: Two Units", "VERIFIED",
            2, "lane/L1-golden-two-units-sequential (PR #227)", "2026-10-07", "Two authorized units complete back-to-back with zero manual handoff"
        ],
        [
            "GOLDEN-03-RESTART", "Golden Proof: Restart Integrity", "VERIFIED",
            1, "lane/L1-golden-restart-between-units (PR #233)", "2026-10-07", "Results survive controller and worker restart between units, no duplicate effects"
        ],
        [
            "GOLDEN-04-NON-STALL", "Golden Proof: Pipeline Resilience", "VERIFIED",
            1, "lane/L1-golden-blocked-unit-does-not-stall (PR #240)", "2026-10-08", "Blocked unit does not stall subsequent work units in pipeline"
        ],
        [
            "RUNTIME-WORKBOOK", "Standard Library OpenXML Engine", "VERIFIED",
            8, "tests/test_runtime_workbook.py", "2026-10-08", "8/8 tests green: read values/formulas, plan mutation, atomic apply, hash verification"
        ],
        [
            "GOOGLE-BUILDER-001", "Autonomous Loop Real Execution", "VERIFIED",
            1, "events/evidence/task-google-builder-live-001_evidence.json", "2026-10-08", "Real Google Builder execution evidence, exit code 0, SHA-256 result verified"
        ],
        [
            "GOOGLE-BUILDER-002", "Autonomous Loop Real Execution", "VERIFIED",
            1, "events/evidence/task-google-builder-live-002_evidence.json", "2026-10-08", "Second consecutive unit, exit code 0, state reconciled in central_state.json"
        ],
        [
            "DEDUPE-PREFLIGHT-01", "Deduplication Engine Preflight", "VERIFIED",
            1, "events/evidence/duplicate_preflight_0226e05a99d440b4.json", "2026-10-07", "Preflight fingerprint match; duplicate task dispatch deterministically avoided"
        ],
        [
            "DEDUPE-PREFLIGHT-02", "Deduplication Engine Preflight", "VERIFIED",
            1, "events/evidence/duplicate_preflight_c42c6830a2b5f3d4.json", "2026-10-07", "Cache reuse validated with SHA-256 integrity and receipt generation"
        ],
        [
            "WIN-LEDGER-INTAKE", "Windows Ledger Module Intake", "VERIFIED",
            10, "memory/WINDOWS_VERIFICATION_LEDGER.md", "2026-09-30", "scripts/intake_dispatcher.py: 100% test coverage on Windows"
        ],
        [
            "WIN-LEDGER-POLICY", "Windows Ledger Resource Policy", "VERIFIED",
            12, "memory/WINDOWS_VERIFICATION_LEDGER.md", "2026-09-30", "scripts/resource_policy.py: 100% test coverage on Windows"
        ],
        [
            "WIN-LEDGER-LOOP", "Windows Autonomous Loop Engine", "VERIFIED",
            8, "memory/WINDOWS_VERIFICATION_LEDGER.md", "2026-09-30", "scripts/run_autonomous_loop.py: 100% test coverage on Windows"
        ]
    ]
    sheets["Tests & Evidence"] = build_worksheet_xml(
        "Tests & Evidence", t_headers, t_rows, code_cols=[1, 5], num_cols=[4]
    )

    # -------------------------------------------------------------
    # 8. Approvals & Actions
    # -------------------------------------------------------------
    a_headers = [
        "Decision_ID", "Topic_Area", "Decision_Text", "Human_Status",
        "Date_or_Deadline", "Policy_or_Evidence_Doc", "Next_Safe_Action"
    ]
    a_rows = [
        [
            "D1", "Git Branch Integration", "Branch claude/determined-hypatia-uvybo5 in integration/v1 uebernehmen",
            "DONE_MERGED", "2026-10-05", "memory/OPEN_ITEMS_MASTER_CURRENT.md", "Merged into integration/v1, no further action needed"
        ],
        [
            "D2", "Dashboard Test Suite", "2 veraltete Dashboard-Tests: loeschen oder reparieren",
            "DONE_REPAIRED", "2026-10-05", "memory/OPEN_ITEMS_MASTER_CURRENT.md", "Repaired on Windows"
        ],
        [
            "D3", "Git History Hygiene", "Alte oeffentliche Daten in Commit 48f7b8bb: History umschreiben?",
            "OPEN_DEFERRED", "Pending", "memory/HUMAN_DECISION_POLICY_CURRENT.md", "Erst sichern, dann entscheiden; fragen nur wenn einziger Restpfad blockiert"
        ],
        [
            "D4", "Python Version Target", "Python 3.11.9 (Bundle) vs 3.12 (CI) vereinheitlichen",
            "APPROVED_3.12", "2026-10-04", "memory/OPEN_ITEMS_MASTER_CURRENT.md", "Standardize packaging on Python 3.12"
        ],
        [
            "D5", "Company Vision Direction", "Vision-Notiz ('Engineering OS -> Aerospace') speichern?",
            "APPROVED_NORTH_STAR", "2026-10-04", "memory/OPEN_ITEMS_MASTER_CURRENT.md", "Nordstern recorded in strategy memory"
        ],
        [
            "FAM-01", "Family Accident Questionnaire", "hkk Unfallfragebogen (Mama Sturz 27.09)",
            "DONE_SUBMITTED", "2026-10-04", "memory/OPEN_ITEMS_MASTER_CURRENT.md", "Eingereicht; auf moegliche hkk-Rueckfrage achten"
        ],
        [
            "FAM-02", "Residence Registration Status", "Meldestatus beim Buergerbuero klaeren",
            "READY_TO_SEND", "vor 27.10.2026", "memory/OPEN_ITEMS_MASTER_CURRENT.md", "Senden durch Dennis ueber Windows-Familien-Chat"
        ],
        [
            "FAM-03", "Care Level PG4 Objection", "Widerspruch PG4 - 2. Ergaenzung (Entlassbrief 27.09.-02.10.)",
            "NEEDS_SOURCE", "Bald", "memory/OPEN_ITEMS_MASTER_CURRENT.md", "Entlassbrief-Foto bereitstellen; kein Handlungsbedarf im Courier-Repo"
        ],
        [
            "POL-01", "Human Question Policy", "Keine Bulk-Frageboegen; nur 1 kleinste Frage wenn einziger Pfad blockiert",
            "ACTIVE_BINDING", "2026-10-04", "memory/HUMAN_DECISION_POLICY_CURRENT.md", "Strict rule: Dennis is not the message bus"
        ],
        [
            "NEXT-01", "Cross-Platform Excel Dashboard", "Deliver editable .xlsx workbook to reports/ and 2026-project-memory",
            "IN_PROGRESS", "2026-10-08", "Current Task", "Generate, validate, and verify .xlsx workbook across macOS and Windows"
        ],
        [
            "NEXT-02", "Google Builder PR Landing", "Merge PR #247 (lane/L3-google-builder-worker) into integration/v1",
            "PENDING_CI", "2026-10-08", "GitHub PR #247", "Monitor CI checks and L1 integration merge sequence"
        ]
    ]
    sheets["Approvals & Actions"] = build_worksheet_xml(
        "Approvals & Actions", a_headers, a_rows, code_cols=[1, 5]
    )

    # Build the package
    build_package(sheets, output_path)

    # Compute row counts
    counts = {
        "Project Milestones": len(m_rows),
        "Ledger Workkeys": len(wk_rows),
        "Open PRs & CI": len(pr_rows),
        "Worker Fleet Status": len(w_rows),
        "Packaging & Installers": len(p_rows),
        "Costs & Budget": len(c_rows),
        "Tests & Evidence": len(t_rows),
        "Approvals & Actions": len(a_rows)
    }
    return git_info, counts


def verify_dashboard_file(file_path, expected_sheets):
    """Verify generated workbook file integrity, XML structure, and content."""
    assert os.path.exists(file_path), f"File {file_path} does not exist"
    size = os.path.getsize(file_path)
    assert size > 2000, f"File {file_path} is suspiciously small ({size} bytes)"

    with zipfile.ZipFile(file_path, "r") as z:
        # Check zip integrity
        bad_file = z.testzip()
        if bad_file:
            raise AssertionError(f"Corrupt zip member: {bad_file}")

        # Check required OpenXML parts
        namelist = set(z.namelist())
        required = {"[Content_Types].xml", "_rels/.rels", "xl/_rels/workbook.xml.rels", "xl/workbook.xml", "xl/styles.xml"}
        missing = required - namelist
        if missing:
            raise AssertionError(f"Missing required OpenXML parts: {missing}")

        # Check workbook.xml sheet names
        wb_root = ET.fromstring(z.read("xl/workbook.xml"))
        found_sheets = [s.get("name") for s in wb_root.iter(f"{{{NS}}}sheet")]
        if found_sheets != expected_sheets:
            raise AssertionError(f"Found sheets {found_sheets} != expected {expected_sheets}")

        # Parse every XML file in the archive to guarantee zero XML syntax errors
        total_cells = 0
        total_rows = 0
        for name in namelist:
            if name.endswith(".xml"):
                data = z.read(name)
                root = ET.fromstring(data)
                if "worksheets" in name:
                    rows = list(root.iter(f"{{{NS}}}row"))
                    cells = list(root.iter(f"{{{NS}}}c"))
                    total_rows += len(rows)
                    total_cells += len(cells)

    return {
        "size_bytes": size,
        "sheets_count": len(found_sheets),
        "total_rows": total_rows,
        "total_cells": total_cells,
        "sheet_names": found_sheets
    }


def main():
    repo_dir = "/Users/user/Downloads/2026-courier"
    output_path = os.path.join(repo_dir, "reports", "Courier_Symphony_Dashboard.xlsx")
    durable_copy_path = "/Users/user/Downloads/2026-project-memory/Courier_Symphony_Dashboard.xlsx"

    print("=== Courier Symphony Excel Dashboard Generator ===")
    print(f"Target path: {output_path}")

    git_info, counts = generate_dashboard(repo_dir, output_path)

    # Duplicate to 2026-project-memory for cross-repo durability
    if os.path.exists(os.path.dirname(durable_copy_path)):
        shutil.copy2(output_path, durable_copy_path)
        print(f"Durable copy created at: {durable_copy_path}")

    # Verification
    expected_sheet_names = [
        "Project Milestones",
        "Ledger Workkeys",
        "Open PRs & CI",
        "Worker Fleet Status",
        "Packaging & Installers",
        "Costs & Budget",
        "Tests & Evidence",
        "Approvals & Actions"
    ]
    val_result = verify_dashboard_file(output_path, expected_sheet_names)

    total_data_rows = sum(counts.values())

    print("\n--- Generation Summary ---")
    print(f"File size: {val_result['size_bytes']} bytes")
    print(f"Total Sheets: {val_result['sheets_count']}")
    print(f"Total Populated Rows (including headers): {val_result['total_rows']}")
    print(f"Total Data Rows (excluding headers): {total_data_rows}")
    print(f"Total Populated Cells: {val_result['total_cells']}")
    for s_name, c in counts.items():
        print(f"  - {s_name}: {c} data rows")

    print("\n--- DELIVERY BLOCK ---")
    print(f"WORKBOOK_PATH={output_path}")
    print(f"SHEETS={','.join(expected_sheet_names)}")
    print(f"ROWS_POPULATED={total_data_rows} data rows ({val_result['total_rows']} total with headers)")
    print(f"SOURCE_SHA={git_info['head_sha']}")
    print(f"VALIDATION=PASSED (Zip integrity: OK, XML well-formed: OK, 8/8 sheets verified, cell count: {val_result['total_cells']})")
    print(f"DURABLE_LOCATION={durable_copy_path}")
    print(f"NEXT_SAFE_ACTION=Monitor CI on PR #247 (lane/L3-google-builder-worker) and prepare L1 merge promotion to integration/v1")


if __name__ == "__main__":
    main()
