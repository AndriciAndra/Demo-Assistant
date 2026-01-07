from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
from typing import Optional
import json

from app.config import get_settings

settings = get_settings()

# OAuth scopes needed
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleAuthService:
    """Service for Google OAuth authentication."""

    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri

    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate Google OAuth authorization URL.
        Returns (authorization_url, state)
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=SCOPES,
        )
        flow.redirect_uri = self.redirect_uri

        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )

        return authorization_url, state

    async def exchange_code(self, code: str) -> dict:
        """
        Exchange authorization code for tokens.
        Returns user info and tokens.
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=SCOPES,
        )
        flow.redirect_uri = self.redirect_uri

        # Exchange code for tokens
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get user info
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {credentials.token}"}
            )
            user_info = response.json()

        return {
            "user_info": {
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
            },
            "tokens": {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            }
        }

    def get_credentials(
            self,
            access_token: str,
            refresh_token: str,
            token_expiry: Optional[datetime] = None
    ) -> Credentials:
        """Create Credentials object from stored tokens."""
        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            expiry=token_expiry,
        )

    async def refresh_credentials(self, credentials: Credentials) -> Credentials:
        """Refresh expired credentials."""
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        return credentials

    def is_token_expired(self, token_expiry: datetime) -> bool:
        """Check if token is expired or about to expire."""
        if not token_expiry:
            return True
        # Consider expired if less than 5 minutes remaining
        return datetime.utcnow() >= token_expiry - timedelta(minutes=5)