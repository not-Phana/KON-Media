"""Secure Google Drive OAuth 2.0 authentication manager.

Guarantees:
- Uses Google's official InstalledAppFlow with browser consent.
- Enforces narrow drive.file scope.
- Never stores secrets in code or git (stored in .gdrive_credentials/ which is gitignored).
- Safely reports missing credentials without throwing unhandled exceptions.
- Zero secret logging.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from kon_search.gdrive.config import (
    CLIENT_SECRETS_FILE,
    DEFAULT_CREDENTIALS_DIR,
    DRIVE_SCOPES,
    TOKEN_STORAGE_FILE,
)

log = logging.getLogger("kon_search_gdrive_auth")


class GoogleDriveAuthManager:
    """Manages local user credentials for Google Drive API."""

    def __init__(
        self,
        credentials_dir: Optional[Path] = None,
        client_secrets_file: Optional[Path] = None,
        token_file: Optional[Path] = None,
    ):
        self.credentials_dir = credentials_dir or DEFAULT_CREDENTIALS_DIR
        self.client_secrets_file = client_secrets_file or (self.credentials_dir / "credentials.json")
        self.token_file = token_file or (self.credentials_dir / "token.json")
        self.credentials_dir.mkdir(parents=True, exist_ok=True)

    def get_auth_status(self) -> Dict[str, Any]:
        """Check authentication readiness without prompting or blocking."""
        has_client_secrets = self.client_secrets_file.exists() and self.client_secrets_file.stat().st_size > 0
        has_token = self.token_file.exists() and self.token_file.stat().st_size > 0

        is_valid = False
        can_refresh = False
        user_email = None

        if has_token:
            try:
                from google.oauth2.credentials import Credentials

                creds = Credentials.from_authorized_user_file(str(self.token_file), DRIVE_SCOPES)
                is_valid = creds.valid
                can_refresh = creds.expired and bool(creds.refresh_token)
            except Exception as e:
                log.debug("Token inspection error: %s", e)

        return {
            "authenticated": is_valid or can_refresh,
            "has_client_secrets": has_client_secrets,
            "has_token": has_token,
            "is_valid": is_valid,
            "can_refresh": can_refresh,
            "client_secrets_path": str(self.client_secrets_file),
            "token_path": str(self.token_file),
            "scopes": DRIVE_SCOPES,
        }

    def get_credentials(self, interactive: bool = False) -> Tuple[Optional[Any], Optional[str]]:
        """Retrieve valid Google Credentials or None with explanation."""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = None
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), DRIVE_SCOPES)
            except Exception as e:
                log.warning("Could not load stored token: %s", e)

        if creds and creds.valid:
            return creds, None

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(self.token_file, "w", encoding="utf-8") as token_out:
                    token_out.write(creds.to_json())
                log.info("Successfully refreshed Google OAuth token.")
                return creds, None
            except Exception as e:
                log.warning("Token refresh failed: %s", e)

        if not interactive:
            if not self.client_secrets_file.exists():
                return (
                    None,
                    f"Missing OAuth client credentials file at: {self.client_secrets_file}. "
                    "Download client secret JSON from Google Cloud Console (Desktop application type).",
                )
            return None, "Google Drive authorization required. Run authorization flow in interactive mode."

        # Interactive login via official browser consent screen
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            if not self.client_secrets_file.exists():
                return None, f"Cannot launch login: {self.client_secrets_file} not found."

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secrets_file),
                DRIVE_SCOPES,
            )
            creds = flow.run_local_server(port=0, prompt="consent")
            with open(self.token_file, "w", encoding="utf-8") as token_out:
                token_out.write(creds.to_json())

            log.info("OAuth authorization successful! Token saved privately.")
            return creds, None
        except Exception as e:
            return None, f"OAuth authorization flow encountered error: {e}"
