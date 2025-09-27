import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from models import JobPosition, ResumeAnalysis, ResumeData

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not all([supabase_url, supabase_key]):
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.client: Client = create_client(supabase_url, supabase_key)
    
    def save_user(self, user_id: str, email: str = None, name: str = None) -> bool:
        """Save or update user"""
        try:
            self.client.table('users').upsert({
                'user_id': user_id,
                'email': email,
                'name': name
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save user: {e}")
            return False
    
    def save_job(self, job: JobPosition) -> bool:
        """Save job position"""
        try:
            self.client.table('job_positions').upsert({
                'job_id': job.job_id,
                'title': job.title,
                'company': job.company,
                'location': job.location,
                'requirements': job.requirements
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save job: {e}")
            return False
    
    def save_resume(self, user_id: str, filename: str, extracted_data: Dict) -> bool:
        """Save resume data"""
        try:
            self.client.table('resumes').insert({
                'user_id': user_id,
                'filename': filename,
                'extracted_data': extracted_data
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save resume: {e}")
            return False
    
    def save_analysis(self, analysis: ResumeAnalysis) -> bool:
        """Save resume analysis"""
        try:
            self.client.table('resume_analysis').insert({
                'user_id': analysis.user_id,
                'job_id': analysis.job_id,
                'overall_score': analysis.overall_score,
                'performance_tier': analysis.performance_tier,
                'technical_skills': analysis.technical_skills,
                'experience': analysis.experience,
                'education': analysis.education,
                'soft_skills': analysis.soft_skills,
                'location_match': analysis.location_match,
                'certifications': analysis.certifications,
                'language_proficiency': analysis.language_proficiency,
                'match_reasons': analysis.match_reasons,
                'suggestions': analysis.suggestions,
                'red_flags': analysis.red_flags,
                'email_subject': analysis.email_subject,
                'email_body': analysis.email_body
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")
            return False
    
    def get_user_history(self, user_id: str) -> List[Dict]:
        """Get user's analysis history"""
        try:
            result = self.client.table('resume_analysis').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get user history: {e}")
            return []
    
    def get_user_resumes(self, user_id: str) -> List[Dict]:
        """Get user's uploaded resumes"""
        try:
            result = self.client.table('resumes').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get user resumes: {e}")
            return []
    
    def get_job_analytics(self, job_id: str) -> Dict:
        """Get analytics for a job position"""
        try:
            result = self.client.table('resume_analysis').select('*').eq('job_id', job_id).execute()
            analyses = result.data or []
            
            if not analyses:
                return {"total_applicants": 0, "average_score": 0}
            
            scores = [a['overall_score'] for a in analyses]
            performance_tiers = [a['performance_tier'] for a in analyses]
            
            return {
                "total_applicants": len(analyses),
                "average_score": sum(scores) / len(scores),
                "score_distribution": {
                    tier: performance_tiers.count(tier)
                    for tier in ["Exceptional", "Strong", "Moderate", "Weak", "Poor"]
                },
                "top_candidates": sorted(
                    [{"score": a['overall_score'], "user_id": a['user_id'], "tier": a['performance_tier']}
                     for a in analyses],
                    key=lambda x: x['score'],
                    reverse=True
                )[:10]
            }
        except Exception as e:
            logger.error(f"Failed to get job analytics: {e}")
            return {"total_applicants": 0, "average_score": 0}