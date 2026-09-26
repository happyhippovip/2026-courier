import os
import json
import logging
import time

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_TOKEN_PATH = os.path.join(".secrets", "token.json")
DEFAULT_CLIENT_SECRET_PATH = os.path.join(".secrets", "client_secret.json")


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
        Dry-run only requires that a credential reference is configured.
        Live mode performs strict validation at upload time.
        """
        # For offline preparation, we just check if the env vars are set.
        # Do NOT initiate OAuth. Do NOT make API calls.
        if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ and \
           "YOUTUBE_OAUTH_CLIENT_SECRET_PATH" not in os.environ:
            raise MissingCredentialError(
                "No Google/YouTube credentials found. Set GOOGLE_APPLICATION_CREDENTIALS "
                "or YOUTUBE_OAUTH_CLIENT_SECRET_PATH."
            )

    def _credential_paths(self):
        token_path = os.environ.get("YOUTUBE_OAUTH_TOKEN_PATH", DEFAULT_TOKEN_PATH)
        secret_ref = os.environ.get(
            "YOUTUBE_OAUTH_CLIENT_SECRET_PATH",
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_CLIENT_SECRET_PATH),
        )
        return token_path, secret_ref

    def _load_credentials(self):
        """Load valid OAuth user credentials, refreshing when possible.

        Raises MissingCredentialError when libraries, token, or client-secret
        files are absent/invalid. Never starts an interactive browser flow.
        """
        try:
            from google.auth.exceptions import RefreshError  # noqa: F401
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise MissingCredentialError(
                "Google auth libraries are not installed. Run "
                "`pip install -r requirements.txt` (needs google-api-python-client, "
                "google-auth-oauthlib, google-auth-httplib2)."
            ) from exc

        token_path, secret_ref = self._credential_paths()

        if token_path and os.path.isfile(token_path):
            try:
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            except (ValueError, OSError) as exc:
                raise MissingCredentialError(
                    f"Stored OAuth token is unreadable/invalid (path from "
                    f"YOUTUBE_OAUTH_TOKEN_PATH). Re-run the OAuth consent flow to "
                    f"generate a new token."
                ) from exc
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as exc:
                    raise MissingCredentialError(
                        "Stored OAuth token is expired and refresh failed. "
                        "Re-run the OAuth consent flow."
                    ) from exc
            if creds.valid:
                return creds
            raise MissingCredentialError(
                "Stored OAuth token is not valid (missing refresh token or wrong "
                "scopes). Re-run the OAuth consent flow with the youtube.upload scope."
            )

        # No usable token: tell the operator exactly what to create.
        # secret_ref may be a path or a keychain reference label.
        if secret_ref and os.path.isfile(secret_ref):
            raise MissingCredentialError(
                "OAuth client secret exists but no valid user token was found. "
                "Complete the one-time browser consent (InstalledAppFlow with "
                "youtube.upload scope) to create .secrets/token.json."
            )
        raise MissingCredentialError(
            "No valid YouTube OAuth token found. Provide a token file via "
            "YOUTUBE_OAUTH_TOKEN_PATH (default .secrets/token.json) or set "
            "YOUTUBE_OAUTH_CLIENT_SECRET_PATH to the OAuth client-secret JSON "
            "and complete the consent flow."
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
            receipt = self._execute_upload_with_retry(payload)
            receipt["idempotency_key"] = idempotency_key

        if idempotency_key:
            self._save_receipt(idempotency_key, receipt)

        return receipt

    def _execute_upload_with_retry(self, payload, max_attempts=3):
        """
        Real YouTube Data API v3 resumable upload with bounded retries.
        Requires valid OAuth user credentials from _load_credentials().
        """
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise MissingCredentialError(
                "Google API client libraries are not installed. Run "
                "`pip install -r requirements.txt`."
            ) from exc

        creds = self._load_credentials()

        video_path = payload.get("video_path", "")
        if not os.path.isfile(video_path):
            raise ValueError(f"Video file not found: {video_path}")

        body = {
            "snippet": {
                "title": payload.get("title", ""),
                "description": payload.get("description", ""),
                "tags": payload.get("tags", []),
            },
            "status": {"privacyStatus": payload.get("privacy_status", "private")},
        }
        media = MediaFileUpload(video_path, resumable=True)

        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                service = build("youtube", "v3", credentials=creds)
                request = service.videos().insert(
                    part="snippet,status", body=body, media_body=media
                )
                response = request.execute()
                return {
                    "video_id": response.get("id", ""),
                    "status": "uploaded",
                }
            except Exception as exc:  # HttpError + transport errors are retriable
                last_error = exc
                retriable = False
                status = getattr(getattr(exc, "resp", None), "status", None)
                if status is not None and int(status) >= 500:
                    retriable = True
                elif "HttpError" not in type(exc).__name__:
                    # Transport-level failure: retry bounded times.
                    retriable = True
                self.logger.warning(
                    "YouTube upload attempt %d/%d failed: %s",
                    attempt, max_attempts, exc,
                )
                if attempt < max_attempts and retriable:
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise RuntimeError(f"YouTube upload failed after {max_attempts} attempts: {last_error}")

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
