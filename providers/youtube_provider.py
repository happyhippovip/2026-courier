import os
import json
import logging

class MissingCredentialError(Exception):
    pass

class YouTubeProvider:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.logger = logging.getLogger("YouTubeProvider")
        self._validate_credentials()

    def _validate_credentials(self):
        """
        Credential-presence detection (fail-closed if missing).
        """
        # For offline preparation, we just check if the env vars are set.
        # Do NOT initiate OAuth. Do NOT make API calls.
        if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ and \
           "YOUTUBE_OAUTH_CLIENT_SECRET_PATH" not in os.environ:
            raise MissingCredentialError(
                "No Google/YouTube credentials found. Set GOOGLE_APPLICATION_CREDENTIALS "
                "or YOUTUBE_OAUTH_CLIENT_SECRET_PATH."
            )

    def validate_payload(self, payload):
        """
        Payload/schema validation according to YouTube Data API limits.
        """
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dictionary")
            
        title = payload.get("title", "")
        if len(title) > 100:
            raise ValueError("Title exceeds 100 characters")
        if len(title) == 0:
            raise ValueError("Title is required")
            
        description = payload.get("description", "")
        if len(description) > 5000:
            raise ValueError("Description exceeds 5000 characters")
            
        tags = payload.get("tags", [])
        if sum(len(tag) for tag in tags) > 500:
            raise ValueError("Total length of tags exceeds 500 characters")
            
        privacy_status = payload.get("privacy_status", "private")
        if privacy_status not in ["private", "public", "unlisted"]:
            raise ValueError("Invalid privacy_status")
            
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
            self.logger.info("DRY_RUN: Would upload video with payload: %s", payload)
            receipt = {
                "video_id": "dry_run_video_id",
                "status": "dry_run",
                "idempotency_key": idempotency_key
            }
        else:
            # Fake retry/backoff logic for offline simulation
            receipt = self._execute_upload_with_retry(payload)
            receipt["idempotency_key"] = idempotency_key
            
        if idempotency_key:
            self._save_receipt(idempotency_key, receipt)
            
        return receipt

    def _execute_upload_with_retry(self, payload, max_attempts=3):
        """
        Simulates retry/backoff logic. In a real scenario, this would
        use googleapiclient.http.MediaFileUpload and execute() with retries.
        """
        # This is where the real API call would go.
        # Since we are strictly OFFLINE, we raise NotImplementedError if not in dry_run.
        raise NotImplementedError("Real upload is disabled for offline mode. Use dry_run=True.")

    def _check_duplicate(self, idempotency_key):
        # Offline duplicate suppression using a local registry
        receipt_path = f".youtube_receipts/{idempotency_key}.json"
        return os.path.exists(receipt_path)

    def _get_receipt(self, idempotency_key):
        receipt_path = f".youtube_receipts/{idempotency_key}.json"
        with open(receipt_path, "r") as f:
            return json.load(f)

    def _save_receipt(self, idempotency_key, receipt):
        os.makedirs(".youtube_receipts", exist_ok=True)
        receipt_path = f".youtube_receipts/{idempotency_key}.json"
        with open(receipt_path, "w") as f:
            json.dump(receipt, f)
