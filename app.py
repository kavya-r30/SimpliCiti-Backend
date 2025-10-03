import asyncio
import json
import os
import uuid
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from evaluator import ResumeEvaluator
from storage import DatabaseManager
from models import *

# === Globals ===
meetings_db = []

# Sample test meetings
test_meetings = [
    {
        "id": "abc123",
        "title": "Technical Interview - Frontend",
        "participant": "John Doe",
        "created_at": datetime.now().isoformat(),
        "status": "scheduled"
    },
    {
        "id": "meet456",
        "title": "HR Discussion",
        "participant": "Jane Smith",
        "created_at": datetime.now().isoformat(),
        "status": "scheduled"
    },
    {
        "id": "int789",
        "title": "Final Round - Backend",
        "participant": "Mike Johnson",
        "created_at": datetime.now().isoformat(),
        "status": "scheduled"
    }
]

meetings_db.extend(test_meetings)

# === WebSocket Connection Manager ===
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, meeting_id: str):
        await websocket.accept()
        if meeting_id not in self.active_connections:
            self.active_connections[meeting_id] = []
        self.active_connections[meeting_id].append(websocket)

        # Notify others
        await self.broadcast_to_meeting(meeting_id, {
            "type": "user-joined",
            "user": "Participant"
        }, exclude=websocket)

    def disconnect(self, websocket: WebSocket, meeting_id: str):
        if meeting_id in self.active_connections:
            self.active_connections[meeting_id].remove(websocket)
            if not self.active_connections[meeting_id]:
                del self.active_connections[meeting_id]
        asyncio.create_task(self.broadcast_to_meeting(meeting_id, {
            "type": "user-left",
            "user": "Participant"
        }))

    async def broadcast_to_meeting(self, meeting_id: str, message: dict, exclude: WebSocket = None):
        if meeting_id in self.active_connections:
            for connection in self.active_connections[meeting_id]:
                if connection != exclude:
                    try:
                        await connection.send_text(json.dumps(message))
                    except:
                        pass

manager = ConnectionManager()

# === FastAPI Setup ===
load_dotenv()

app = FastAPI(title="SimpliCiti Recruitment Platform", version="2.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

evaluator = ResumeEvaluator()
db = DatabaseManager()

# === Job Data ===
JOBS = {
    "frontend_dev": {
        "job_id": "frontend_dev",
        "title": "Frontend Developer",
        "company": "TechCorp",
        "location": "Remote",
        "requirements": {
            "technical_skills": ["React", "JavaScript", "TypeScript", "CSS", "HTML"],
            "experience_years": 2,
            "education_level": "Bachelor's or equivalent",
            "soft_skills": ["Communication", "Problem Solving", "Teamwork"],
            "weights": {"technical": 40, "experience": 25, "education": 15, "soft_skills": 15, "location": 5}
        }
    },
    "backend_dev": {
        "job_id": "backend_dev",
        "title": "Backend Developer",
        "company": "DataCorp",
        "location": "New York",
        "requirements": {
            "technical_skills": ["Python", "Django", "SQL", "Docker", "AWS"],
            "experience_years": 3,
            "education_level": "Bachelor's in CS",
            "soft_skills": ["System Design", "Problem Solving", "Code Review"],
            "weights": {"technical": 45, "experience": 30, "education": 10, "soft_skills": 10, "location": 5}
        }
    },
    "data_scientist": {
        "job_id": "data_scientist",
        "title": "Data Scientist",
        "company": "AI Corp",
        "location": "Boston",
        "requirements": {
            "technical_skills": ["Python", "R", "ML", "Statistics", "SQL", "Pandas"],
            "experience_years": 2,
            "education_level": "Master's in Data Science",
            "soft_skills": ["Analytics", "Communication", "Business Acumen"],
            "weights": {"technical": 50, "experience": 20, "education": 20, "soft_skills": 8, "location": 2}
        }
    }
}

# === UI Routes ===
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/meetings")
async def meetings_page(request: Request):
    return templates.TemplateResponse("meetings.html", {"request": request})

@app.get("/jobs")
async def jobs_page(request: Request):
    return templates.TemplateResponse("jobs.html", {"request": request, "jobs": JOBS})

@app.get("/analytics")
async def analytics_page(request: Request):
    return templates.TemplateResponse("analytics.html", {"request": request})

# === Meeting API ===
@app.post("/api/meetings")
async def create_meeting(meeting_data: dict):
    meeting_id = str(uuid.uuid4())[:8]
    meeting = {
        "id": meeting_id,
        "title": meeting_data.get("title", "Interview Meeting"),
        "participant": meeting_data.get("participant", "Candidate"),
        "created_at": datetime.now().isoformat(),
        "status": "scheduled"
    }
    meetings_db.append(meeting)
    return meeting

@app.get("/api/meetings")
async def get_meetings():
    return meetings_db

@app.get("/api/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    for meeting in meetings_db:
        if meeting["id"] == meeting_id:
            return meeting
    raise HTTPException(status_code=404, detail="Meeting not found")

# === WebSocket Endpoint ===
@app.websocket("/ws/{meeting_id}")
async def websocket_endpoint(websocket: WebSocket, meeting_id: str):
    await manager.connect(websocket, meeting_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Broadcast signaling messages to other participants
            if message['type'] in ['offer', 'answer', 'ice-candidate']:
                await manager.broadcast_to_meeting(meeting_id, message, exclude=websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket, meeting_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, meeting_id)

# === API Endpoints ===
@app.get("/api/")
async def api_root():
    return {"message": "SimpliCiti Recruitment API", "version": "2.0.0"}

@app.post("/api/analyze")
async def analyze_resume(
    user_id: str = Form(...),
    job_id: str = Form(...),
    file: UploadFile = File(...),
    send_email: bool = Form(False),
    candidate_email: str = Form(None)
):
    file_bytes = await file.read()

    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        result = await evaluator.evaluate_resume(
            file_bytes=file_bytes,
            filename=file.filename,
            job_requirements=JOBS[job_id]["requirements"],
            user_id=user_id,
            job_id=job_id
        )

        db.save_resume(user_id, file.filename, result.extracted_data)
        db.save_analysis(result)

        return {
            "success": True,
            "user_id": result.user_id,
            "job_id": result.job_id,
            "job_title": JOBS[job_id]["title"],
            "overall_score": result.overall_score,
            "performance_tier": result.performance_tier,
            "individual_scores": {
                "technical_skills": result.technical_skills,
                "experience": result.experience,
                "education": result.education,
                "soft_skills": result.soft_skills,
                "location_match": result.location_match,
                "certifications": result.certifications,
                "language_proficiency": result.language_proficiency
            },
            "match_reasons": result.match_reasons,
            "suggestions": result.suggestions,
            "red_flags": result.red_flags,
            "email": {
                "subject": result.email_subject,
                "body": result.email_body,
                "sent": False
            },
            "extracted_data": result.extracted_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs")
async def get_jobs():
    return {"jobs": JOBS}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]

@app.get("/api/user/{user_id}/history")
async def get_user_history(user_id: str):
    history = db.get_user_history(user_id)
    return {"history": history}

@app.get("/api/user/{user_id}/resumes")
async def get_user_resumes(user_id: str):
    resumes = db.get_user_resumes(user_id)
    return {"resumes": resumes}

@app.get("/api/job/{job_id}/analytics")
async def get_job_analytics(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    analytics = db.get_job_analytics(job_id)
    return {
        "job_title": JOBS[job_id]["title"],
        "analytics": analytics
    }

@app.post("/api/match")
async def match_existing_resume(user_id: str = Form(...), job_id: str = Form(...)):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    resumes = db.get_user_resumes(user_id)
    if not resumes:
        raise HTTPException(status_code=404, detail="No resumes found")

    latest_resume = resumes[0]

    result = await evaluator.evaluate_extracted_data(
        latest_resume["extracted_data"],
        JOBS[job_id]["requirements"],
        user_id,
        job_id
    )

    db.save_analysis(result)

    return {
        "success": True,
        "job_title": JOBS[job_id]["title"],
        "overall_score": result.overall_score,
        "performance_tier": result.performance_tier,
        "match_reasons": result.match_reasons,
        "suggestions": result.suggestions
    }

# === Entry Point ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
