import os
import json
import logging

class MissingCredentialError(Exception):
    pass

class TikTokProvider:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.logger = logging.getLogger("TikTokProvider")
        self._validate_credentials()

    def _validate_credentials(self):
        """
        Credential-presence detection (fail-closed if missing).
        """
        if "TIKTOK_ACCESS_TOKEN" not in os.environ and \
           "TIKTOK_CLIENT_KEY" not in os.environ:
            raise MissingCredentialError(
                "No TikTok credentials found. Set TIKTOK_ACCESS_TOKEN "
                "or TIKTOK_CLIENT_KEY."
            )

    def validate_payload(self, payload):
        """
        Payload/schema validation according to TikTok Content Posting API limits.
        """
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dictionary")

        title = payload.get("title", "")
        # TikTok post caption / description limit is typically 2200 characters
        if len(title) > 2200:
            raise ValueError("Caption exceeds 2200 characters")
        if len(title) == 0:
            raise ValueError("Caption/title is required")

        privacy_level = payload.get("privacy_level", "SELF_ONLY")
        valid_privacy = ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"]
        if privacy_level not in valid_privacy:
            raise ValueError(f"Invalid privacy_level: must be one of {valid_privacy}")

        # Ensure video_path is provided for upload
        if not payload.get("video_path"):
            raise ValueError("video_path is required")

        return True

    def upload_video(self, payload, idempotency_key=None):
        """
        Uploads a video (or dry runs). Includes duplicate suppression.
        """
        self.validate_payload(payload)

        if idempotency_key:
            # Check for duplicate suppression
            if self._check_duplicate(idempotency_key):
                self.logger.info(f"Duplicate suppression triggered for key: {idempotency_key}")
                return self._get_receipt(idempotency_key)

        if self.dry_run:
            self.logger.info("DRY_RUN: Would upload video to TikTok with payload: %s", payload)
            receipt = {
                "publish_id": "dry_run_tiktok_publish_id",
                "status": "dry_run",
                "idempotency_key": idempotency_key
            }
        else:
            receipt = self._execute_upload_with_retry(payload)
            receipt["idempotency_key"] = idempotency_key

        if idempotency_key:
            self._save_receipt(idempotency_key, receipt)

        return receipt

    def _execute_upload_with_retry(self, payload, max_attempts=3):
        """
        Simulates retry/backoff logic. Real upload is strictly disabled in offline mode.
        """
        raise NotImplementedError("Real upload is disabled for offline mode. Use dry_run=True.")

    def _check_duplicate(self, idempotency_key):
        receipt_path = f".tiktok_receipts/{idempotency_key}.json"
        return os.path.exists(receipt_path)

    def _get_receipt(self, idempotency_key):
        receipt_path = f".tiktok_receipts/{idempotency_key}.json"
        with open(receipt_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_receipt(self, idempotency_key, receipt):
        os.makedirs(".tiktok_receipts", exist_ok=True)
        receipt_path = f".tiktok_receipts/{idempotency_key}.json"
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2)
