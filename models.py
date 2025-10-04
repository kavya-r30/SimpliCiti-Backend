from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class JobPosition(BaseModel):
    """Job position model"""
    job_id: str
    title: str
    company: str
    location: str
    description: Optional[str] = None
    requirements: Dict[str, Any]

class ResumeAnalysis(BaseModel):
    """Resume analysis result"""
    id: Optional[str] = None
    user_id: str
    job_id: str
    
    # Overall scoring
    overall_score: int = Field(ge=0, le=100)
    performance_tier: str
    application_status: str = "pending"
    
    # Individual scores (8 fields - must match evaluator and database)
    technical_skills: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    education: int = Field(ge=0, le=100)
    soft_skills: int = Field(ge=0, le=100)
    projects: int = Field(ge=0, le=100)
    location_match: int = Field(ge=0, le=100)
    certifications: int = Field(ge=0, le=100)
    language_proficiency: int = Field(ge=0, le=100)
    
    # Analysis details
    match_reasons: str
    suggestions: List[str] = []
    red_flags: List[str] = []
    extracted_data: Dict[str, Any] = {}
    
    # Email
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    
    # Metadata
    recruiter_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

APPLICATION_STATUSES = [
    "pending",      # Initial submission
    "selected",     # Score >= 90, top tier
    "shortlisted",  # Score 80-89, strong candidates
    "waitlisted",   # Score 70-79, backup
    "rejected",     # Score < 70
    "interviewed",  # Moved to interview
    "offered",      # Job offer extended
    "accepted",     # Offer accepted
    "withdrawn"     # Candidate withdrew
]

PERFORMANCE_TIERS = [
    {"min": 90, "tier": "Exceptional"},
    {"min": 80, "tier": "Strong"},
    {"min": 70, "tier": "Moderate"},
    {"min": 60, "tier": "Weak"},
    {"min": 0, "tier": "Poor"}
]


def get_performance_tier(score: int) -> tuple[str, str]:
    for tier_info in PERFORMANCE_TIERS:
        if score >= tier_info["min"]:
            return tier_info["tier"]
    return "Poor"

def validate_status(status: str) -> bool:
    return status in APPLICATION_STATUSES