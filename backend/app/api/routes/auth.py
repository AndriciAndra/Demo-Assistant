from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models.database import User
from app.services.google_auth import GoogleAuthService
from app.services.jwt import create_access_token, TokenResponse, ACCESS_TOKEN_EXPIRE_MINUTES
from app.api.deps import get_current_user
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

google_auth = GoogleAuthService()


@router.get("/google/login")
async def google_login(redirect_url: Optional[str] = None):
    """
    Initiate Google OAuth login flow.
    Returns the authorization URL to redirect the user to.
    """
    # DEBUG
    print("=" * 50)
    print("DEBUG - google_auth.client_id:", google_auth.client_id if google_auth.client_id else "EMPTY!")
    print("DEBUG - google_auth.redirect_uri:", google_auth.redirect_uri)
    print("=" * 50)

    # Use redirect_url as state to redirect after login
    state = redirect_url or "http://localhost:3000"
    authorization_url, state = google_auth.get_authorization_url(state=state)

    return {
        "authorization_url": authorization_url,
        "state": state
    }


@router.get("/google/callback")
async def google_callback(
        code: str,
        state: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback.
    Creates or updates user and returns JWT token.
    """
    try:
        # Exchange code for tokens and user info
        result = await google_auth.exchange_code(code)
        user_info = result["user_info"]
        tokens = result["tokens"]

        # Find or create user
        user = db.query(User).filter(User.email == user_info["email"]).first()

        if user:
            # Update existing user
            user.name = user_info.get("name") or user.name
            user.google_access_token = tokens["access_token"]
            user.google_refresh_token = tokens["refresh_token"]
            if tokens["token_expiry"]:
                user.google_token_expiry = datetime.fromisoformat(tokens["token_expiry"])
        else:
            # Create new user
            user = User(
                email=user_info["email"],
                name=user_info.get("name"),
                google_access_token=tokens["access_token"],
                google_refresh_token=tokens["refresh_token"],
                google_token_expiry=datetime.fromisoformat(tokens["token_expiry"]) if tokens["token_expiry"] else None,
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        # Create JWT token
        access_token = create_access_token(
            data={"user_id": user.id, "email": user.email}
        )

        # Redirect to frontend with token
        redirect_url = state or "http://localhost:3000"

        # Add token as URL parameter (frontend will extract it)
        separator = "&" if "?" in redirect_url else "?"
        redirect_with_token = f"{redirect_url}{separator}token={access_token}"

        return RedirectResponse(url=redirect_with_token)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Google: {str(e)}"
        )


@router.post("/google/token", response_model=TokenResponse)
async def google_token_exchange(
        code: str,
        db: Session = Depends(get_db)
):
    """
    Alternative endpoint for SPA: exchange code for JWT token directly.
    Use this if you handle the OAuth redirect in frontend.
    """
    try:
        result = await google_auth.exchange_code(code)
        user_info = result["user_info"]
        tokens = result["tokens"]

        # Find or create user
        user = db.query(User).filter(User.email == user_info["email"]).first()

        if user:
            user.name = user_info.get("name") or user.name
            user.google_access_token = tokens["access_token"]
            user.google_refresh_token = tokens["refresh_token"]
            if tokens["token_expiry"]:
                user.google_token_expiry = datetime.fromisoformat(tokens["token_expiry"])
        else:
            user = User(
                email=user_info["email"],
                name=user_info.get("name"),
                google_access_token=tokens["access_token"],
                google_refresh_token=tokens["refresh_token"],
                google_token_expiry=datetime.fromisoformat(tokens["token_expiry"]) if tokens["token_expiry"] else None,
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        # Create JWT token
        access_token = create_access_token(
            data={"user_id": user.id, "email": user.email}
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "picture": user_info.get("picture"),
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate: {str(e)}"
        )


@router.get("/me")
async def get_current_user_info(
        current_user: User = Depends(get_current_user)
):
    """Get current authenticated user info."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "jira_connected": bool(current_user.jira_api_token),
        "google_connected": bool(current_user.google_access_token),
        "scheduler_enabled": current_user.scheduler_enabled,
        "created_at": current_user.created_at,
    }


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint.
    Note: JWT tokens can't be truly invalidated server-side without a blacklist.
    Frontend should delete the token.
    """
    return {"message": "Successfully logged out"}


@router.post("/refresh")
async def refresh_token(
        current_user: User = Depends(get_current_user)
):
    """Refresh JWT token."""
    access_token = create_access_token(
        data={"user_id": current_user.id, "email": current_user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }