import os
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from evaluator import ResumeEvaluator
# from email_composer import EmailComposer
from storage import DatabaseManager
from models import *

load_dotenv()

app = FastAPI(title="Resume Matcher API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

evaluator = ResumeEvaluator()
# email_composer = EmailComposer()
db = DatabaseManager()

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

# @app.on_event("startup")
# async def startup():
#     for job_data in JOBS.values():
#         db.save_job(JobPosition(**job_data))

@app.get("/")
async def root():
    return {"message": "Resume Matcher API", "version": "1.0.0"}

@app.post("/analyze")
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
        # Evaluate resume
        result = await evaluator.evaluate_resume(
            file_bytes=file_bytes,
            filename=file.filename,
            job_requirements=JOBS[job_id]["requirements"],
            user_id=user_id,
            job_id=job_id
        )
        
        # # Generate email
        # email_data = email_composer.generate_email(
        #     result, JOBS[job_id], result.extracted_data.get("personal_details", {})
        # )
        # result.email_subject = email_data["subject"]
        # result.email_body = email_data["body"]
        
        # Save to database
        db.save_resume(user_id, file.filename, result.extracted_data)
        db.save_analysis(result)
        
        # # Send email if requested
        email_sent = False
        # if send_email and candidate_email:
            # email_sent = email_composer.send_email(candidate_email, email_data)
        
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
                "sent": email_sent
            },
            "extracted_data": result.extracted_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs")
async def get_jobs():
    """Get available job positions"""
    return {"jobs": JOBS}

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get specific job details"""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]

@app.get("/user/{user_id}/history")
async def get_user_history(user_id: str):
    """Get user's analysis history"""
    history = db.get_user_history(user_id)
    return {"history": history}

@app.get("/user/{user_id}/resumes")
async def get_user_resumes(user_id: str):
    """Get user's uploaded resumes"""
    resumes = db.get_user_resumes(user_id)
    return {"resumes": resumes}

@app.get("/job/{job_id}/analytics")
async def get_job_analytics(job_id: str):
    """Get analytics for a job position"""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    
    analytics = db.get_job_analytics(job_id)
    return {
        "job_title": JOBS[job_id]["title"],
        "analytics": analytics
    }

@app.post("/match")
async def match_existing_resume(user_id: str = Form(...), job_id: str = Form(...)):
    """Match existing resume to different job"""
    
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
    
    # Generate email
    # email_data = email_composer.generate_email(
    #     result, JOBS[job_id], result.extracted_data.get("personal_details", {})
    # )
    # result.email_subject = email_data["subject"]
    # result.email_body = email_data["body"]
    
    # Save analysis
    db.save_analysis(result)
    
    return {
        "success": True,
        "job_title": JOBS[job_id]["title"],
        "overall_score": result.overall_score,
        "performance_tier": result.performance_tier,
        "match_reasons": result.match_reasons,
        "suggestions": result.suggestions
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)