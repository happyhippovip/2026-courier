#!/usr/bin/env python3
"""Historical Resource Benchmark & Quota Observation Manager (Mission 175G, 177G, 179G).

Preserves and normalizes historical provider quota observations from 2026-08-31
with authoritative canonical reset segment resolution.

Primary Security & Authority Guarantees (Mission 179G / Codex 178C Remediation):
- Canonical Registry Authority: All delta calculations resolve observation identity against
  an immutable canonical registry. Caller-controlled segment IDs, timestamps, or percentage
  modifications are strictly rejected fail-closed (Zero Trust on caller metadata).
- Fail-Closed Reset Protection: Five-hour and weekly deltas cannot cross canonical reset boundaries
  even under adversarial forgery or replacement attempts.
- Dimension-Aware Segmentation: Five-hour resets and weekly resets maintain independent canonical segments.
- Strict Timestamp & Order Validation: Chronological order between parseable ISO timestamps is required.
  Observations with "UNKNOWN" timestamps or out-of-order timestamps return fail-closed validation errors.
- Energy Semantics: ENERGY = DISPLAYED_PROVIDER_RESOURCE_CAPACITY. Zero physical electricity/FLOPs inference.
- Non-Additive Quotas: Independent provider/account/model pools are never summed or converted.
- AUTONOMOUS_SPEND_LIMIT = 0 EUR.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
RESOURCE_INTEL_DIR = EVENTS_DIR / "resource-intelligence"
HISTORICAL_OBS_FILE = RESOURCE_INTEL_DIR / "historical_observations_2026-08-31.json"


# ==============================================================================
# Data Model
# ==============================================================================

@dataclass(frozen=True)
class HistoricalResourceObservation:
    observation_id: str
    provider: str  # OPENAI_CODEX | GOOGLE_GEMINI | GOOGLE_CLAUDE_GPT_POOL
    account_pool_id: str  # e.g. openai-account-plus-primary, google-account-pro-pool1, google-account-pro-pool2
    model_pool: str  # CHATGPT_PLUS_CODEX | GOOGLE_GEMINI | GOOGLE_CLAUDE_AND_GPT_MODELS
    observed_at: str  # ISO 8601 or "UNKNOWN"
    time_precision: str  # EXACT | APPROXIMATE | UNKNOWN
    weekly_remaining_pct: Optional[float]
    five_hour_remaining_pct: Optional[float]
    five_hour_segment_id: str = "DEFAULT_5H"
    weekly_segment_id: str = "DEFAULT_WEEKLY"
    reset_observation: Optional[Dict[str, Any]] = None
    source_type: str = "CHIEF_HISTORICAL_RECORD"  # SCREENSHOT | CHIEF_HISTORICAL_RECORD | BENCHMARK_REPORT | MISSION_REPORT
    benchmark_run: Optional[str] = None
    mission_id: Optional[str] = None
    prompt_sequence: Optional[List[int]] = None
    prompt_mapping_status: str = "PARTIAL"  # COMPLETE | PARTIAL | NONE
    useful_work_class: Optional[str] = None
    external_calls: int = 0
    spend_eur: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# Canonical Dataset: 2026-08-31 Historical Observations (28 Records)
# ==============================================================================

CANONICAL_2026_08_31_OBSERVATIONS: List[Dict[str, Any]] = [
    # 1. ~11:00 (APPROXIMATE) - Start Benchmark Run 002
    {
        "observation_id": "resobs-20260831-110000-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T11:00:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 99.0,
        "five_hour_remaining_pct": 95.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "BENCHMARK_REPORT",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Start of Resource Benchmark Run 002",
    },
    {
        "observation_id": "resobs-20260831-110000-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T11:00:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 47.0,
        "five_hour_remaining_pct": 95.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "BENCHMARK_REPORT",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark parallel comparison point ~11:00",
    },

    # 2. 11:11:51 (EXACT)
    {
        "observation_id": "resobs-20260831-111151-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T11:11:51+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 98.0,
        "five_hour_remaining_pct": 89.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 11:11:51",
    },
    {
        "observation_id": "resobs-20260831-111151-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T11:11:51+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 46.0,
        "five_hour_remaining_pct": 92.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 11:11:51",
    },

    # 3. 11:27:59 (EXACT)
    {
        "observation_id": "resobs-20260831-112759-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T11:27:59+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 97.0,
        "five_hour_remaining_pct": 79.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 11:27:59",
    },
    {
        "observation_id": "resobs-20260831-112759-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T11:27:59+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 46.0,
        "five_hour_remaining_pct": 88.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 11:27:59",
    },

    # 4. ~11:38 (APPROXIMATE)
    {
        "observation_id": "resobs-20260831-113800-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T11:38:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 96.0,
        "five_hour_remaining_pct": 73.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point ~11:38",
    },
    {
        "observation_id": "resobs-20260831-113800-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T11:38:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 44.0,
        "five_hour_remaining_pct": 76.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point ~11:38",
    },

    # 5. 11:51 (EXACT)
    {
        "observation_id": "resobs-20260831-115100-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T11:51:00+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 96.0,
        "five_hour_remaining_pct": 72.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 11:51",
    },
    {
        "observation_id": "resobs-20260831-115100-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T11:51:00+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 43.0,
        "five_hour_remaining_pct": 70.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 11:51",
    },

    # 6. 11:54:50 (EXACT)
    {
        "observation_id": "resobs-20260831-115450-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T11:54:50+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 94.0,
        "five_hour_remaining_pct": 62.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 11:54:50",
    },
    {
        "observation_id": "resobs-20260831-115450-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T11:54:50+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 43.0,
        "five_hour_remaining_pct": 70.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 11:54:50",
    },

    # 7. 12:02 (APPROXIMATE)
    {
        "observation_id": "resobs-20260831-120200-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T12:02:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 93.0,
        "five_hour_remaining_pct": 58.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 12:02",
    },
    {
        "observation_id": "resobs-20260831-120200-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T12:02:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 41.0,
        "five_hour_remaining_pct": 63.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 12:02",
    },

    # 8. 12:16 (APPROXIMATE)
    {
        "observation_id": "resobs-20260831-121600-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T12:16:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 93.0,
        "five_hour_remaining_pct": 55.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 12:16",
    },
    {
        "observation_id": "resobs-20260831-121600-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T12:16:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 40.0,
        "five_hour_remaining_pct": 54.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 12:16",
    },

    # 9. 13:24 (APPROXIMATE)
    {
        "observation_id": "resobs-20260831-132400-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T13:24:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 89.0,
        "five_hour_remaining_pct": 31.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 13:24",
    },
    {
        "observation_id": "resobs-20260831-132400-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T13:24:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 39.0,
        "five_hour_remaining_pct": 47.0,
        "five_hour_segment_id": "google-pool1-5h-seg1",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point 13:24",
    },

    # 10. ~14:21 (APPROXIMATE - GOOGLE 5-HOUR RESET BOUNDARY)
    {
        "observation_id": "resobs-20260831-142100-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T14:21:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 87.0,
        "five_hour_remaining_pct": 16.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point ~14:21",
    },
    {
        "observation_id": "resobs-20260831-142100-google-reset",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T14:21:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 34.0,
        "five_hour_remaining_pct": 100.0,
        "five_hour_segment_id": "google-pool1-5h-seg2",  # NEW CANONICAL 5H SEGMENT
        "weekly_segment_id": "google-pool1-weekly-seg1", # SAME WEEKLY SEGMENT
        "reset_observation": {
            "reset_type": "FIVE_HOUR_POOL_RESET",
            "reset_detected_at": "2026-08-31T14:21:00+02:00",
            "affected_dimension": "FIVE_HOUR",
        },
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Google five-hour pool reset to 100% at ~14:21 (starts google-pool1-5h-seg2)",
    },

    # 11. ~14:32 (APPROXIMATE)
    {
        "observation_id": "resobs-20260831-143200-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T14:32:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 86.0,
        "five_hour_remaining_pct": 9.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point ~14:32",
    },
    {
        "observation_id": "resobs-20260831-143200-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T14:32:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 34.0,
        "five_hour_remaining_pct": 97.0,
        "five_hour_segment_id": "google-pool1-5h-seg2",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Benchmark progress point ~14:32 (google-pool1-5h-seg2)",
    },

    # 12. LATER_CHECKPOINT_TIME_UNKNOWN (UNKNOWN TIMESTAMP)
    {
        "observation_id": "resobs-20260831-unknown-openai",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "UNKNOWN",
        "time_precision": "UNKNOWN",
        "weekly_remaining_pct": 84.0,
        "five_hour_remaining_pct": 0.0,
        "five_hour_segment_id": "openai-plus-5h-seg1",
        "weekly_segment_id": "openai-plus-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_PUBLICATION_PATH_ANALYSIS",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Later checkpoint time unknown; OpenAI 5-hour reached 0% in seg1",
    },
    {
        "observation_id": "resobs-20260831-unknown-google",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool1",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "UNKNOWN",
        "time_precision": "UNKNOWN",
        "weekly_remaining_pct": 34.0,
        "five_hour_remaining_pct": 97.0,
        "five_hour_segment_id": "google-pool1-5h-seg2",
        "weekly_segment_id": "google-pool1-weekly-seg1",
        "reset_observation": None,
        "source_type": "CHIEF_HISTORICAL_RECORD",
        "benchmark_run": "RESOURCE_BENCHMARK_RUN_002",
        "mission_id": "BENCHMARK_RUN_002",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "BENCHMARK_COMPARISON_WORKER",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Later checkpoint time unknown; Google capacity remained 34% / 97%",
    },

    # 13. ~21:35 Europe/Berlin (NEW GOOGLE ACCOUNT POOL 2 INITIAL)
    {
        "observation_id": "resobs-20260831-213500-google-pool2",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool2",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T21:35:00+02:00",
        "time_precision": "APPROXIMATE",
        "weekly_remaining_pct": 100.0,
        "five_hour_remaining_pct": None,
        "five_hour_segment_id": "google-pool2-5h-seg1",
        "weekly_segment_id": "google-pool2-weekly-seg1",
        "reset_observation": None,
        "source_type": "MISSION_REPORT",
        "benchmark_run": None,
        "mission_id": "MISSION_168G",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "MULTI_POOL_REGISTRY_TEST",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Initial capacity on new Google AI Pro Account Pool 2 (~21:35)",
    },

    # 14. 22:38 Europe/Berlin (EXACT LATEST SCREENSHOT CHECKPOINT)
    {
        "observation_id": "resobs-20260831-223800-openai-latest",
        "provider": "OPENAI_CODEX",
        "account_pool_id": "openai-account-plus-primary",
        "model_pool": "CHATGPT_PLUS_CODEX",
        "observed_at": "2026-08-31T22:38:00+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 66.0,
        "five_hour_remaining_pct": 83.0,
        "five_hour_segment_id": "openai-plus-5h-seg2",  # NEW CANONICAL 5H SEGMENT AFTER RESET
        "weekly_segment_id": "openai-plus-weekly-seg1", # SAME WEEKLY BILLING CYCLE
        "reset_observation": {
            "five_hour_reset_countdown_approx": "02:43",
            "weekly_reset_displayed": "07.09.2026 10:40",
            "credit_balance_eur": 0.0,
            "automatic_topup": False,
            "subscription_plan": "Plus (23 EUR/month displayed locally)",
            "affected_dimension": "FIVE_HOUR",
        },
        "source_type": "SCREENSHOT",
        "benchmark_run": None,
        "mission_id": "MISSION_173G_POST",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_FACTORY_CAPACITY_TEST",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Latest verified screenshot checkpoint for OpenAI Codex Plus (5h seg2)",
    },
    {
        "observation_id": "resobs-20260831-223800-google-gemini-latest",
        "provider": "GOOGLE_GEMINI",
        "account_pool_id": "google-account-pro-pool2",
        "model_pool": "GOOGLE_GEMINI",
        "observed_at": "2026-08-31T22:38:00+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 98.0,
        "five_hour_remaining_pct": 85.0,
        "five_hour_segment_id": "google-pool2-5h-seg1",
        "weekly_segment_id": "google-pool2-weekly-seg1",
        "reset_observation": {
            "weekly_reset_countdown": "6 days 23 hours",
            "five_hour_reset_countdown": "4 hours 3 minutes",
            "credit_overages": False,
        },
        "source_type": "SCREENSHOT",
        "benchmark_run": None,
        "mission_id": "MISSION_173G",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "CREATOR_FACTORY_DATA_HARDENING_M173G",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Latest verified screenshot checkpoint for Google AI Pro Gemini Pool (google-pool2)",
    },
    {
        "observation_id": "resobs-20260831-223800-google-claudegpt-latest",
        "provider": "GOOGLE_CLAUDE_GPT_POOL",
        "account_pool_id": "google-account-pro-pool2",
        "model_pool": "GOOGLE_CLAUDE_AND_GPT_MODELS",
        "observed_at": "2026-08-31T22:38:00+02:00",
        "time_precision": "EXACT",
        "weekly_remaining_pct": 100.0,
        "five_hour_remaining_pct": 100.0,
        "five_hour_segment_id": "google-pool2-claudegpt-5h-seg1",
        "weekly_segment_id": "google-pool2-claudegpt-weekly-seg1",
        "reset_observation": {
            "pool_nature": "SEPARATE_DISPLAYED_POOL_NOT_ADDITIVE",
        },
        "source_type": "SCREENSHOT",
        "benchmark_run": None,
        "mission_id": "MISSION_173G",
        "prompt_sequence": None,
        "prompt_mapping_status": "PARTIAL",
        "useful_work_class": "INDEPENDENT_MODEL_POOL_OBSERVATION",
        "external_calls": 0,
        "spend_eur": 0.0,
        "notes": "Google AI Pro Claude & GPT models pool remains separate; never summed",
    },
]


# ==============================================================================
# Manager & Delta Calculation Logic with Authoritative Canonical Resolution
# ==============================================================================

class ResourceBenchmarkManager:
    """Manages historical resource observations with authoritative canonical resolution.

    Guarantees:
    - Caller objects/IDs are always verified and resolved against canonical registry state.
    - Forged segment IDs or tampered observation fields fail closed immediately.
    - Cross-reset deltas are strictly denied.
    - Timestamp ordering is validated using parseable ISO timestamps. UNKNOWN or out-of-order
      timestamps return fail-closed validation errors.
    """

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.storage_file = repo_dir / "events" / "resource-intelligence" / "historical_observations_2026-08-31.json"

        # Authoritative canonical observation index
        self._canonical_index: Dict[str, HistoricalResourceObservation] = {
            item["observation_id"]: HistoricalResourceObservation(**item)
            for item in CANONICAL_2026_08_31_OBSERVATIONS
        }

        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.persist_canonical_observations()

    def persist_canonical_observations(self) -> None:
        self.storage_file.write_text(
            json.dumps(CANONICAL_2026_08_31_OBSERVATIONS, indent=2) + "\n",
            encoding="utf-8"
        )

    def load_observations(self) -> List[HistoricalResourceObservation]:
        return list(self._canonical_index.values())

    # --------------------------------------------------------------------------
    # Authoritative Canonical Resolution & Validation (Mission 179G)
    # --------------------------------------------------------------------------

    def resolve_canonical_observation(
        self,
        obs_or_id: Union[str, HistoricalResourceObservation, Dict[str, Any]],
    ) -> HistoricalResourceObservation:
        """Authoritatively resolves observation identity against the canonical registry.

        Rejects unknown IDs, forged segment IDs, tampered percentages, or malformed data fail-closed.
        """
        if isinstance(obs_or_id, str):
            obs_id = obs_or_id.strip()
            if obs_id not in self._canonical_index:
                raise ValueError(f"Unknown observation ID: '{obs_id}'")
            return self._canonical_index[obs_id]

        if isinstance(obs_or_id, dict):
            obs_id = obs_or_id.get("observation_id", "")
            if not obs_id or obs_id not in self._canonical_index:
                raise ValueError(f"Unknown or missing observation ID in dict: '{obs_id}'")
            canonical = self._canonical_index[obs_id]
            # Verify caller dict fields match canonical record
            for key in ("provider", "account_pool_id", "model_pool", "observed_at",
                        "weekly_remaining_pct", "five_hour_remaining_pct",
                        "five_hour_segment_id", "weekly_segment_id"):
                if key in obs_or_id and obs_or_id[key] != getattr(canonical, key):
                    raise ValueError(
                        f"Observation integrity violation: caller field '{key}' "
                        f"({obs_or_id[key]}) != canonical ({getattr(canonical, key)}) for ID '{obs_id}'"
                    )
            return canonical

        if isinstance(obs_or_id, HistoricalResourceObservation):
            obs_id = obs_or_id.observation_id
            if obs_id not in self._canonical_index:
                raise ValueError(f"Unknown observation ID: '{obs_id}'")
            canonical = self._canonical_index[obs_id]
            # Verify caller object has not forged segment IDs or tampered fields
            for key in ("provider", "account_pool_id", "model_pool", "observed_at",
                        "weekly_remaining_pct", "five_hour_remaining_pct",
                        "five_hour_segment_id", "weekly_segment_id"):
                caller_val = getattr(obs_or_id, key)
                canon_val = getattr(canonical, key)
                if caller_val != canon_val:
                    raise ValueError(
                        f"Observation integrity violation: caller field '{key}' "
                        f"({caller_val}) != canonical ({canon_val}) for ID '{obs_id}'"
                    )
            return canonical

        raise ValueError(f"Unsupported observation input type: {type(obs_or_id)}")

    def _validate_timestamp_ordering(
        self,
        start: HistoricalResourceObservation,
        end: HistoricalResourceObservation,
    ) -> None:
        """Validates chronological ordering between two canonical observations.

        Observations with 'UNKNOWN' timestamps or non-chronological order fail closed.
        """
        if start.observed_at == "UNKNOWN" or end.observed_at == "UNKNOWN":
            raise ValueError(
                f"Timestamp ordering cannot be established for UNKNOWN timestamp: "
                f"'{start.observed_at}' vs '{end.observed_at}'"
            )

        try:
            ts_start = dt.datetime.fromisoformat(start.observed_at.replace("Z", "+00:00"))
            ts_end = dt.datetime.fromisoformat(end.observed_at.replace("Z", "+00:00"))
        except Exception as e:
            raise ValueError(f"Unparseable timestamp: {e}")

        if ts_start >= ts_end:
            raise ValueError(
                f"Timestamps not in chronological order: start ({start.observed_at}) >= end ({end.observed_at})"
            )

    # --------------------------------------------------------------------------
    # Authoritative Delta Calculations
    # --------------------------------------------------------------------------

    def calculate_five_hour_delta(
        self,
        obs_start: Union[str, HistoricalResourceObservation, Dict[str, Any]],
        obs_end: Union[str, HistoricalResourceObservation, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Authoritatively calculates five-hour capacity delta strictly within the SAME canonical 5h reset segment."""
        c_start = self.resolve_canonical_observation(obs_start)
        c_end = self.resolve_canonical_observation(obs_end)

        self._validate_common_boundaries(c_start, c_end)
        self._validate_timestamp_ordering(c_start, c_end)

        if c_start.five_hour_segment_id != c_end.five_hour_segment_id:
            raise ValueError(
                f"Cross-five-hour-reset delta calculation DENIED: "
                f"segment '{c_start.five_hour_segment_id}' vs '{c_end.five_hour_segment_id}'"
            )

        if c_start.five_hour_remaining_pct is None or c_end.five_hour_remaining_pct is None:
            five_hour_delta = None
        else:
            five_hour_delta = c_end.five_hour_remaining_pct - c_start.five_hour_remaining_pct

        return {
            "provider": c_start.provider,
            "account_pool_id": c_start.account_pool_id,
            "model_pool": c_start.model_pool,
            "dimension": "FIVE_HOUR",
            "segment_id": c_start.five_hour_segment_id,
            "start_five_hour_pct": c_start.five_hour_remaining_pct,
            "end_five_hour_pct": c_end.five_hour_remaining_pct,
            "five_hour_capacity_delta_pct_points": five_hour_delta,
            "unit": "DISPLAYED_CAPACITY_PERCENTAGE_POINTS",
        }

    def calculate_weekly_delta(
        self,
        obs_start: Union[str, HistoricalResourceObservation, Dict[str, Any]],
        obs_end: Union[str, HistoricalResourceObservation, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Authoritatively calculates weekly capacity delta strictly within the SAME canonical weekly reset segment."""
        c_start = self.resolve_canonical_observation(obs_start)
        c_end = self.resolve_canonical_observation(obs_end)

        self._validate_common_boundaries(c_start, c_end)
        self._validate_timestamp_ordering(c_start, c_end)

        if c_start.weekly_segment_id != c_end.weekly_segment_id:
            raise ValueError(
                f"Cross-weekly-reset delta calculation DENIED: "
                f"segment '{c_start.weekly_segment_id}' vs '{c_end.weekly_segment_id}'"
            )

        if c_start.weekly_remaining_pct is None or c_end.weekly_remaining_pct is None:
            weekly_delta = None
        else:
            weekly_delta = c_end.weekly_remaining_pct - c_start.weekly_remaining_pct

        return {
            "provider": c_start.provider,
            "account_pool_id": c_start.account_pool_id,
            "model_pool": c_start.model_pool,
            "dimension": "WEEKLY",
            "segment_id": c_start.weekly_segment_id,
            "start_weekly_pct": c_start.weekly_remaining_pct,
            "end_weekly_pct": c_end.weekly_remaining_pct,
            "weekly_capacity_delta_pct_points": weekly_delta,
            "unit": "DISPLAYED_CAPACITY_PERCENTAGE_POINTS",
        }

    def calculate_delta(
        self,
        obs_start: Union[str, HistoricalResourceObservation, Dict[str, Any]],
        obs_end: Union[str, HistoricalResourceObservation, Dict[str, Any]],
        dimension: str = "both",
    ) -> Dict[str, Any]:
        """Authoritatively calculates displayed capacity delta fail-closed against any reset boundary."""
        dim = dimension.lower()
        if dim == "five_hour":
            return self.calculate_five_hour_delta(obs_start, obs_end)
        elif dim == "weekly":
            return self.calculate_weekly_delta(obs_start, obs_end)
        elif dim == "both":
            c_start = self.resolve_canonical_observation(obs_start)
            c_end = self.resolve_canonical_observation(obs_end)
            five_hour_res = self.calculate_five_hour_delta(c_start, c_end)
            weekly_res = self.calculate_weekly_delta(c_start, c_end)
            return {
                "provider": c_start.provider,
                "account_pool_id": c_start.account_pool_id,
                "model_pool": c_start.model_pool,
                "five_hour_segment_id": c_start.five_hour_segment_id,
                "weekly_segment_id": c_start.weekly_segment_id,
                "start_weekly_pct": c_start.weekly_remaining_pct,
                "end_weekly_pct": c_end.weekly_remaining_pct,
                "weekly_capacity_delta_pct_points": weekly_res["weekly_capacity_delta_pct_points"],
                "start_five_hour_pct": c_start.five_hour_remaining_pct,
                "end_five_hour_pct": c_end.five_hour_remaining_pct,
                "five_hour_capacity_delta_pct_points": five_hour_res["five_hour_capacity_delta_pct_points"],
                "unit": "DISPLAYED_CAPACITY_PERCENTAGE_POINTS",
                "physical_electricity_kwh": None,
                "tokens_inferred": None,
            }
        else:
            raise ValueError(f"Unknown dimension: {dimension}")

    def _validate_common_boundaries(
        self,
        obs_start: HistoricalResourceObservation,
        obs_end: HistoricalResourceObservation,
    ) -> None:
        if obs_start.provider != obs_end.provider:
            raise ValueError(f"Cross-provider delta calculation DENIED: {obs_start.provider} vs {obs_end.provider}")

        if obs_start.account_pool_id != obs_end.account_pool_id:
            raise ValueError(f"Cross-account delta calculation DENIED: {obs_start.account_pool_id} vs {obs_end.account_pool_id}")

        if obs_start.model_pool != obs_end.model_pool:
            raise ValueError(f"Cross-model-pool delta calculation DENIED: {obs_start.model_pool} vs {obs_end.model_pool}")

    # --------------------------------------------------------------------------
    # Chief Summary Generation
    # --------------------------------------------------------------------------

    def get_chief_summary(self) -> Dict[str, Any]:
        obs = self.load_observations()

        exact_count = sum(1 for o in obs if o.time_precision == "EXACT")
        approx_count = sum(1 for o in obs if o.time_precision == "APPROXIMATE")
        unknown_count = sum(1 for o in obs if o.time_precision == "UNKNOWN")

        return {
            "RESOURCE_HISTORY_AVAILABLE": True,
            "RESOURCE_HISTORY_DATE": "2026-08-31",
            "RESOURCE_OBSERVATION_COUNT": len(obs),
            "EXACT_TIMESTAMPS_COUNT": exact_count,
            "APPROXIMATE_TIMESTAMPS_COUNT": approx_count,
            "UNKNOWN_TIMESTAMPS_COUNT": unknown_count,
            "OPENAI_SEGMENTS": 2,  # 5-hour: seg1 (95%->0%), seg2 (83%)
            "GOOGLE_SEGMENTS": 3,  # Pool 1 Seg 1 (95%->47%), Pool 1 Seg 2 (100%->97%), Pool 2 Seg 1 (85%)
            "RESET_BOUNDARIES": 2,  # Google 5h reset at ~14:21; OpenAI 5h reset prior to 22:38
            "BENCHMARK_RUNS": ["RESOURCE_BENCHMARK_RUN_002"],
            "PROMPT_MAPPING_COMPLETENESS": "PARTIAL",
            "LATEST_RESOURCE_CHECKPOINT": {
                "timestamp": "2026-08-31T22:38:00+02:00",
                "openai_codex": "66 weekly / 83 five-hour",
                "google_gemini": "98 weekly / 85 five-hour",
                "google_claude_gpt_pool": "100 weekly / 100 five-hour",
            },
            "MONEY_FIREWALL": "0_EUR_AUTONOMOUS_SPEND_ENFORCED",
            "PHYSICAL_ENERGY_INFERENCE": "DENIED",
            "CROSS_PROVIDER_PERCENT_CONVERSION": "DENIED",
            "AUTOMATIC_ACCOUNT_ROTATION": "DENIED",
        }


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Historical Resource Benchmark Manager (Mission 179G)")
    parser.add_argument("--summary", action="store_true", help="Print compact Chief Brain summary")
    parser.add_argument("--dump", action="store_true", help="Print all normalized historical observations")
    args = parser.parse_args()

    mgr = ResourceBenchmarkManager()

    if args.summary or len(CANONICAL_2026_08_31_OBSERVATIONS) > 0:
        summary = mgr.get_chief_summary()
        print(json.dumps(summary, indent=2))

    if args.dump:
        obs = [o.to_dict() for o in mgr.load_observations()]
        print(json.dumps(obs, indent=2))


if __name__ == "__main__":
    main()
