# google_meet_interaction.py
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import traceback

# -----------------------------
# DEV FIX: Allow OAuth over HTTP for localhost
# -----------------------------
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

router = APIRouter()

GOOGLE_CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "google_client_secret.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# -----------------------------
# Step 1: Authorize
# -----------------------------
@router.get("/authorize")
async def authorize(request: Request):
    try:
        flow = Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=str(request.url_for("oauth2callback"))
        )

        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true"
        )

        # Store state in session
        if not hasattr(request, "session") or request.session is None:
            request.session = {}
        request.session["state"] = state

        return RedirectResponse(authorization_url)

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Step 2: OAuth2 callback
# -----------------------------
@router.get("/oauth2callback")
async def oauth2callback(request: Request, state: str, code: str = None):
    try:
        flow = Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRET_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=str(request.url_for("oauth2callback"))
        )

        # Exchange code for credentials
        flow.fetch_token(authorization_response=str(request.url))
        credentials = flow.credentials

        # Save credentials in session as dict
        if not hasattr(request, "session") or request.session is None:
            request.session = {}
        request.session["credentials"] = credentials_to_dict(credentials)

        return RedirectResponse(url="/google/create_meet")

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------
# Step 3: Create Google Meet
# -----------------------------
@router.get("/create_meet", response_class=HTMLResponse)
async def create_meet(request: Request):
    try:
        creds_data = getattr(request, "session", {}).get("credentials")
        if not creds_data:
            return RedirectResponse("/google/authorize")

        creds = Credentials(**creds_data)
        service = build("calendar", "v3", credentials=creds)

        event = {
            "summary": "Recruiter Meeting",
            "conferenceData": {
                "createRequest": {
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    "requestId": "simpli-meet-001"
                }
            },
            "start": {"dateTime": "2025-10-04T10:00:00+05:30"},
            "end": {"dateTime": "2025-10-04T11:00:00+05:30"},
        }

        created_event = service.events().insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1
        ).execute()

        meet_link = created_event.get("hangoutLink", "No link generated")
        return HTMLResponse(f"<h3>Google Meet Created:</h3><a href='{meet_link}'>{meet_link}</a>")

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Helper: Convert credentials to dict
# -----------------------------
def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
