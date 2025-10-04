import os
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from evaluator import ResumeEvaluator
from email_composer import EmailComposer
from storage import DatabaseManager
from models import JobPosition

load_dotenv()

app = FastAPI(title="Resume Evaluation API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

evaluator = ResumeEvaluator()
email_composer = EmailComposer()
db = DatabaseManager()

# ============================================================================
# HEALTH & INFO
# ============================================================================

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy"}

# ============================================================================
# USER ROUTES
# ============================================================================

@app.post("/users/upload-resume", tags=["Users"])
async def upload_resume(
    user_id: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        file_content = await file.read()
        extracted_data = await evaluator.extract_resume_data(file_content, file.filename)
        
        personal = extracted_data.get("personal_details", {})
        social = extracted_data.get("social_profiles", {})
        
        user_saved = db.save_user(
            user_id=user_id,
            email=personal.get("email"),
            name=personal.get("name"),
            phone=personal.get("phone"),
            location=personal.get("location"),
            github_url=social.get("github"),
            linkedin_url=social.get("linkedin"),
            leetcode_url=social.get("leetcode"),
            portfolio_url=social.get("portfolio")
        )
        
        resume_id = db.save_resume(user_id, file.filename, extracted_data)
        
        return {
            "success": True,
            "user_id": user_id,
            "resume_id": resume_id,
            "personal_details": personal,
            "social_profiles": social,
            "skills": extracted_data.get("skills", {}),
            "experience": extracted_data.get("experience", []),
            "education": extracted_data.get("education", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/profile", tags=["Users"])
async def get_user_profile(user_id: str):
    """Get user profile"""
    try:
        user = db.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        resumes = db.get_user_resumes(user_id)
        applications = db.get_user_applications(user_id)
        
        return {
            "user": user,
            "latest_resume": resumes[0] if resumes else None,
            "total_resumes": len(resumes),
            "total_applications": len(applications)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/applications", tags=["Users"])
async def get_user_applications(
    user_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    sort_by: str = Query("created_at", description="Sort by field"),
    order: str = Query("desc", description="asc or desc")
):
    """Get user's applications"""
    try:
        applications = db.get_user_applications(user_id, status, sort_by, order)
        
        for app in applications:
            job = db.get_job_by_id(app['job_id'])
            if job:
                app['job_title'] = job['title']
                app['company'] = job['company']
        
        return {
            "user_id": user_id,
            "total": len(applications),
            "applications": applications
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/resumes", tags=["Users"])
async def get_user_resumes(user_id: str):
    """Get user's resumes"""
    try:
        resumes = db.get_user_resumes(user_id)
        return {"user_id": user_id, "total": len(resumes), "resumes": resumes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/search", tags=["Users"])
async def search_users(
    q: Optional[str] = Query(None, description="Search query"),
    skill: Optional[str] = Query(None, description="Filter by skill"),
    location: Optional[str] = Query(None, description="Filter by location"),
    min_score: Optional[int] = Query(None, description="Minimum avg score"),
    has_github: Optional[bool] = Query(None, description="Must have GitHub"),
    limit: int = Query(20, le=100)
):
    """Search users"""
    try:
        users = db.search_users(q, skill, location, min_score, has_github, limit)
        return {"total": len(users), "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# JOB ROUTES
# ============================================================================

@app.get("/jobs", tags=["Jobs"])
async def list_jobs(
    company: Optional[str] = None,
    location: Optional[str] = None,
    active_only: bool = True
):
    """List all jobs"""
    try:
        jobs = db.get_all_jobs(company, location, active_only)
        return {"total": len(jobs), "jobs": jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}", tags=["Jobs"])
async def get_job(job_id: str):
    """Get job by ID"""
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jobs", tags=["Jobs"])
async def create_job(
    job_id: str = Form(...),
    title: str = Form(...),
    company: str = Form(...),
    location: str = Form(...),
    description: str = Form(None),
    technical_skills: str = Form(...),
    experience_years: int = Form(...),
    education_level: str = Form(...),
    soft_skills: str = Form(None),
    certifications: str = Form(None),
    technical_weight: int = Form(40),
    experience_weight: int = Form(25),
    education_weight: int = Form(15),
    soft_skills_weight: int = Form(15),
    projects_weight: int = Form(5)
):
    """Create new job"""
    try:
        existing = db.get_job_by_id(job_id)
        if existing:
            raise HTTPException(status_code=400, detail="Job ID already exists")
        
        job_data = JobPosition(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            description=description,
            requirements={
                "technical_skills": [s.strip() for s in technical_skills.split(',')],
                "experience_years": experience_years,
                "education_level": education_level,
                "soft_skills": [s.strip() for s in soft_skills.split(',')] if soft_skills else [],
                "certifications_preferred": [s.strip() for s in certifications.split(',')] if certifications else [],
                "weights": {
                    "technical_skills": technical_weight,
                    "experience": experience_weight,
                    "education": education_weight,
                    "soft_skills": soft_skills_weight,
                    "projects": projects_weight,
                    "certifications": 5,
                    "location_match": 5,
                    "language_proficiency": 5
                }
            }
        )
        
        success = db.save_job(job_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save job")
        
        return {"success": True, "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/jobs/{job_id}", tags=["Jobs"])
async def update_job(
    job_id: str,
    title: str = Form(None),
    company: str = Form(None),
    location: str = Form(None),
    description: str = Form(None),
    technical_skills: str = Form(None)
):
    """Update job"""
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        update_data = {}
        if title:
            update_data['title'] = title
        if company:
            update_data['company'] = company
        if location:
            update_data['location'] = location
        if description:
            update_data['description'] = description
        if technical_skills:
            update_data['requirements'] = job['requirements']
            update_data['requirements']['technical_skills'] = [s.strip() for s in technical_skills.split(',')]
        
        success = db.update_job(job_id, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update job")
        
        return {"success": True, "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/jobs/{job_id}", tags=["Jobs"])
async def delete_job(job_id: str):
    """Delete job"""
    try:
        success = db.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"success": True, "message": f"Job {job_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}/applicants", tags=["Jobs"])
async def get_job_applicants(
    job_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    sort_by: str = Query("overall_score", description="Sort by field"),
    order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, le=200)
):
    """Get job applicants"""
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        applicants = db.get_job_applicants(job_id, status, sort_by, order, limit)
        
        for app in applicants:
            user = db.get_user_profile(app['user_id'])
            if user:
                app['name'] = user.get('name')
                app['email'] = user.get('email')
                app['github_url'] = user.get('github_url')
        
        status_counts = db.get_job_status_counts(job_id)
        
        return {
            "job_id": job_id,
            "job_title": job['title'],
            "total": len(applicants),
            "status_counts": status_counts,
            "applicants": applicants
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}/analytics", tags=["Jobs"])
async def get_job_analytics(job_id: str):
    """Get job analytics"""
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        analytics = db.get_job_analytics(job_id)
        return {
            "job_id": job_id,
            "job_title": job["title"],
            "analytics": analytics
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# APPLICATION ROUTES
# ============================================================================

@app.post("/applications/submit", tags=["Applications"])
async def submit_application(
    user_id: str = Form(...),
    job_id: str = Form(...),
    file: UploadFile = File(None),
    resume_id: str = Form(None),
    send_email: bool = Form(False),
    candidate_email: str = Form(None)
):
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        existing_app = db.get_application_by_user_and_job(user_id, job_id)
        if existing_app:
            raise HTTPException(
                status_code=400, 
                detail=f"Application already exists with ID: {existing_app['id']}"
            )
        
        if file:
            upload_response = await upload_resume(user_id=user_id, file=file)
            saved_resume_id = upload_response["resume_id"]
            
            resume = db.get_resume_by_id(saved_resume_id)
            if not resume:
                raise HTTPException(status_code=404, detail="Resume not found")
            
            if resume['user_id'] != user_id:
                raise HTTPException(status_code=403, detail="Resume does not belong to this user")
            
            extracted_data = resume['extracted_data']
            analysis = await evaluator.evaluate_extracted_data(
                extracted_data=extracted_data,
                job_requirements=job["requirements"],
                user_id=user_id,
                job_id=job_id
            )
            
            saved_resume_id = resume_id
            personal_details = extracted_data.get("personal_details", {})
        
        elif resume_id:
            resume = db.get_resume_by_id(resume_id)
            if not resume:
                raise HTTPException(status_code=404, detail="Resume not found")
            
            if resume['user_id'] != user_id:
                raise HTTPException(status_code=403, detail="Resume does not belong to this user")
            
            extracted_data = resume['extracted_data']
            analysis = await evaluator.evaluate_extracted_data(
                extracted_data=extracted_data,
                job_requirements=job["requirements"],
                user_id=user_id,
                job_id=job_id
            )
            
            saved_resume_id = resume_id
            personal_details = extracted_data.get("personal_details", {})
        
        else:
            resumes = db.get_user_resumes(user_id)
            if not resumes:
                raise HTTPException(
                    status_code=400, 
                    detail="No resume found. Please upload a resume or provide resume_id"
                )
            
            latest_resume = resumes[0]
            extracted_data = latest_resume['extracted_data']
            
            analysis = await evaluator.evaluate_extracted_data(
                extracted_data=extracted_data,
                job_requirements=job["requirements"],
                user_id=user_id,
                job_id=job_id
            )
            
            saved_resume_id = latest_resume['id']
            personal_details = extracted_data.get("personal_details", {})
        
        email_data = email_composer.generate_email(analysis, job, personal_details)
        analysis.email_subject = email_data["subject"]
        analysis.email_body = email_data["body"]
        
        status = db.determine_application_status(analysis.overall_score, analysis.performance_tier)
        analysis.application_status = status
        
        application_id = db.save_application(analysis, saved_resume_id)
        
        email_sent = False
        if send_email and candidate_email:
            email_sent = email_composer.send_email(candidate_email, email_data)
        
        return {
            "success": True,
            "application_id": application_id,
            "resume_id": saved_resume_id,
            "user_id": user_id,
            "job_id": job_id,
            "job_title": job["title"],
            "overall_score": analysis.overall_score,
            "performance_tier": analysis.performance_tier,
            "status": status,
            "individual_scores": {
                "technical_skills": analysis.technical_skills,
                "experience": analysis.experience,
                "education": analysis.education,
                "soft_skills": analysis.soft_skills,
                "projects": analysis.projects,
                "location_match": analysis.location_match,
                "certifications": analysis.certifications,
                "language_proficiency": analysis.language_proficiency
            },
            "match_reasons": analysis.match_reasons,
            "suggestions": analysis.suggestions,
            "red_flags": analysis.red_flags,
            "email_sent": email_sent,
            "mode": "new_upload" if file else "existing_resume"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/applications/submit-multiple", tags=["Applications"])
async def submit_multiple_applications(
    user_id: str = Form(...),
    job_ids: str = Form(...),
    file: UploadFile = File(...)
):
    """Submit application to multiple jobs"""
    try:
        file_content = await file.read()
        job_id_list = [j.strip() for j in job_ids.split(',')]
        
        extracted_data = await evaluator.extract_resume_data(file_content, file.filename)
        
        resume_id = db.save_resume(user_id, file.filename, extracted_data)
        
        results = []
        for job_id in job_id_list:
            job = db.get_job_by_id(job_id)
            if not job:
                results.append({"job_id": job_id, "error": "Job not found"})
                continue
            
            analysis = await evaluator.evaluate_extracted_data(
                extracted_data=extracted_data,
                job_requirements=job["requirements"],
                user_id=user_id,
                job_id=job_id
            )
            
            status = db.determine_application_status(analysis.overall_score, analysis.performance_tier)
            analysis.application_status = status
            
            application_id = db.save_application(analysis, resume_id)
            
            results.append({
                "application_id": application_id,
                "job_id": job_id,
                "job_title": job["title"],
                "overall_score": analysis.overall_score,
                "performance_tier": analysis.performance_tier,
                "status": status
            })
        
        best_match = max(results, key=lambda x: x.get('overall_score', 0)) if results else None
        
        return {
            "success": True,
            "user_id": user_id,
            "total": len(results),
            "results": results,
            "best_match": best_match
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/applications/{application_id}", tags=["Applications"])
async def get_application(application_id: str):
    """Get application by ID"""
    try:
        application = db.get_application_by_id(application_id)
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        job = db.get_job_by_id(application['job_id'])
        if job:
            application['job_title'] = job['title']
            application['company'] = job['company']
        
        user = db.get_user_profile(application['user_id'])
        if user:
            application['candidate_name'] = user.get('name')
            application['candidate_email'] = user.get('email')
        
        return application
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/applications/{application_id}/status", tags=["Applications"])
async def update_application_status(
    application_id: str,
    status: str = Form(...),
    notes: str = Form(None)
):
    """Update application status"""
    valid_statuses = [
        "pending", "selected", "shortlisted", "waitlisted", "rejected",
        "interviewed", "offered", "accepted", "withdrawn"
    ]
    
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    try:
        success = db.update_application_status(application_id, status, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Application not found")
        
        return {"success": True, "application_id": application_id, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ANALYTICS
# ============================================================================

@app.get("/analytics/overview", tags=["Analytics"])
async def get_platform_analytics():
    """Get platform-wide analytics"""
    try:
        stats = db.get_platform_stats()
        jobs = db.get_all_jobs()
        
        return {
            "total_users": stats['total_users'],
            "total_jobs": len(jobs),
            "total_applications": stats['total_applications'],
            "avg_score": stats['avg_score'],
            "status_distribution": stats['status_distribution']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)