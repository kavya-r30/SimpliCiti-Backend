from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime

class JobPosition(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    requirements: Dict[str, Any]

class ResumeAnalysis(BaseModel):
    id: Optional[str] = None
    user_id: str
    job_id: str
    overall_score: int
    performance_tier: str
    technical_skills: int
    experience: int
    education: int
    soft_skills: int
    location_match: int
    certifications: int
    language_proficiency: int
    match_reasons: str
    suggestions: List[str]
    red_flags: List[str]
    extracted_data: Dict[str, Any]
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    created_at: Optional[datetime] = None

class ResumeData(BaseModel):
    user_id: str
    filename: str
    extracted_data: Dict[str, Any]
    created_at: Optional[datetime] = None

class EmailTemplate(BaseModel):
    subject: str
    body: str
    template_type: str

SCORE_RANGES = [
    {"min": 90, "tier": "Exceptional", "emoji": "🏆"},
    {"min": 80, "tier": "Strong", "emoji": "🌟"},
    {"min": 70, "tier": "Moderate", "emoji": "👍"},
    {"min": 60, "tier": "Weak", "emoji": "⚠️"},
    {"min": 0, "tier": "Poor", "emoji": "❌"}
]

def get_performance_tier(score: int) -> tuple:
    for range_info in SCORE_RANGES:
        if score >= range_info["min"]:
            return range_info["tier"], range_info["emoji"]
    return "Poor", "❌"