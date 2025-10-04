import os
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client

from models import JobPosition, ResumeAnalysis

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not all([supabase_url, supabase_key]):
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.client: Client = create_client(supabase_url, supabase_key)
    
    # ============================================================================
    # USER METHODS
    # ============================================================================
    
    def save_user(self, user_id: str, email: str = None, name: str = None, 
                  phone: str = None, location: str = None, github_url: str = None,
                  linkedin_url: str = None, leetcode_url: str = None, 
                  portfolio_url: str = None) -> bool:
        """Create or update user profile"""
        try:
            self.client.table('users').upsert({
                'user_id': user_id,
                'email': email,
                'name': name,
                'phone': phone,
                'location': location,
                'github_url': github_url,
                'linkedin_url': linkedin_url,
                'leetcode_url': leetcode_url,
                'portfolio_url': portfolio_url
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save user: {e}")
            return False
    
    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Get user profile by user_id"""
        try:
            result = self.client.table('users').select('*').eq('user_id', user_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None
    
    def search_users(self, query: str = None, skill: str = None, 
                    location: str = None, min_score: int = None, 
                    has_github: bool = None, limit: int = 20) -> List[Dict]:
        """Search users with filters"""
        try:
            db_query = self.client.table('users').select('*, applications(overall_score)')
            
            if query:
                db_query = db_query.or_(f'name.ilike.%{query}%,email.ilike.%{query}%')
            
            if location:
                db_query = db_query.ilike('location', f'%{location}%')
            
            if has_github:
                db_query = db_query.not_.is_('github_url', 'null')
            
            result = db_query.limit(limit).execute()
            users = result.data or []
            
            # Post-process for skill filtering and score filtering
            filtered = []
            for user in users:
                # Calculate avg score
                if user.get('applications'):
                    scores = [app['overall_score'] for app in user['applications'] if app.get('overall_score')]
                    avg_score = sum(scores) / len(scores) if scores else 0
                    user['avg_score'] = round(avg_score, 2)
                    user['total_applications'] = len(user['applications'])
                else:
                    user['avg_score'] = 0
                    user['total_applications'] = 0
                
                # Apply min_score filter
                if min_score and user['avg_score'] < min_score:
                    continue
                
                # Clean up
                del user['applications']
                filtered.append(user)
            
            return filtered
        except Exception as e:
            logger.error(f"Failed to search users: {e}")
            return []
    
    # ============================================================================
    # JOB METHODS
    # ============================================================================
    
    def save_job(self, job: JobPosition) -> bool:
        """Create or update job position"""
        try:
            self.client.table('jobs').upsert({
                'job_id': job.job_id,
                'title': job.title,
                'company': job.company,
                'location': job.location,
                'description': job.description,
                'requirements': job.requirements
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save job: {e}")
            return False
    
    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        """Get job by job_id"""
        try:
            result = self.client.table('jobs').select('*').eq('job_id', job_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get job: {e}")
            return None
    
    def get_all_jobs(self, company: str = None, location: str = None, 
                     active_only: bool = True) -> List[Dict]:
        """Get all jobs with optional filters"""
        try:
            query = self.client.table('jobs').select('*')
            
            if active_only:
                query = query.eq('is_active', True)
            
            if company:
                query = query.ilike('company', f'%{company}%')
            
            if location:
                query = query.ilike('location', f'%{location}%')
            
            result = query.order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get jobs: {e}")
            return []
    
    def update_job(self, job_id: str, job_data: Dict) -> bool:
        """Update job fields"""
        try:
            update_data = {}
            if 'title' in job_data:
                update_data['title'] = job_data['title']
            if 'company' in job_data:
                update_data['company'] = job_data['company']
            if 'location' in job_data:
                update_data['location'] = job_data['location']
            if 'description' in job_data:
                update_data['description'] = job_data['description']
            if 'requirements' in job_data:
                update_data['requirements'] = job_data['requirements']
            
            self.client.table('jobs').update(update_data).eq('job_id', job_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update job: {e}")
            return False
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job"""
        try:
            result = self.client.table('jobs').delete().eq('job_id', job_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Failed to delete job: {e}")
            return False
    
    # ============================================================================
    # RESUME METHODS
    # ============================================================================
    
    def save_resume(self, user_id: str, filename: str, extracted_data: Dict) -> Optional[str]:
        """Save resume and return resume_id"""
        try:
            result = self.client.table('resumes').insert({
                'user_id': user_id,
                'filename': filename,
                'extracted_data': extracted_data
            }).execute()
            return result.data[0]['id'] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save resume: {e}")
            return None
    
    def get_user_resumes(self, user_id: str) -> List[Dict]:
        """Get all resumes for a user"""
        try:
            result = self.client.table('resumes').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get user resumes: {e}")
            return []
    
    def get_resume_by_id(self, resume_id: str) -> Optional[Dict]:
        """Get resume by ID"""
        try:
            result = self.client.table('resumes').select('*').eq('id', resume_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get resume by ID: {e}")
            return None
    
    # ============================================================================
    # APPLICATION METHODS
    # ============================================================================
    
    def save_application(self, analysis: ResumeAnalysis, resume_id: str = None) -> Optional[str]:
        """Save application and return application_id"""
        try:
            result = self.client.table('applications').insert({
                'user_id': analysis.user_id,
                'job_id': analysis.job_id,
                'resume_id': resume_id,
                'overall_score': analysis.overall_score,
                'performance_tier': analysis.performance_tier,
                'technical_skills': analysis.technical_skills,
                'experience': analysis.experience,
                'education': analysis.education,
                'soft_skills': analysis.soft_skills,
                'projects': analysis.projects,
                'location_match': analysis.location_match,
                'certifications': analysis.certifications,
                'language_proficiency': analysis.language_proficiency,
                'match_reasons': analysis.match_reasons,
                'suggestions': analysis.suggestions,
                'red_flags': analysis.red_flags,
                'email_subject': analysis.email_subject,
                'email_body': analysis.email_body,
                'status': analysis.application_status
            }).execute()
            return result.data[0]['id'] if result.data else None
        except Exception as e:
            logger.error(f"Failed to save application: {e}")
            return None
    
    def get_application_by_id(self, application_id: str) -> Optional[Dict]:
        """Get application by id"""
        try:
            result = self.client.table('applications').select('*').eq('id', application_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get application: {e}")
            return None
    
    def get_application_by_user_and_job(self, user_id: str, job_id: str) -> Optional[Dict]:
        """Get application by user_id and job_id (checks for duplicates)"""
        try:
            result = self.client.table('applications').select('*').eq('user_id', user_id).eq('job_id', job_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to get application by user and job: {e}")
            return None
    
    def get_user_applications(self, user_id: str, status: str = None, 
                             sort_by: str = 'created_at', order: str = 'desc') -> List[Dict]:
        """Get all applications for a user"""
        try:
            query = self.client.table('applications').select('*').eq('user_id', user_id)
            
            if status:
                query = query.eq('status', status)
            
            desc = order == 'desc'
            result = query.order(sort_by, desc=desc).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get user applications: {e}")
            return []
    
    def get_job_applicants(self, job_id: str, status: str = None, 
                          sort_by: str = 'overall_score', order: str = 'desc',
                          limit: int = 50) -> List[Dict]:
        """Get all applicants for a job"""
        try:
            query = self.client.table('applications').select('*').eq('job_id', job_id)
            
            if status:
                query = query.eq('status', status)
            
            desc = order == 'desc'
            result = query.order(sort_by, desc=desc).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to get job applicants: {e}")
            return []
    
    def update_application_status(self, application_id: str, status: str, 
                                 notes: str = None) -> bool:
        """Update application status"""
        try:
            update_data = {'status': status}
            if notes:
                update_data['recruiter_notes'] = notes
            
            result = self.client.table('applications').update(update_data).eq('id', application_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Failed to update application status: {e}")
            return False
    
    def get_job_status_counts(self, job_id: str) -> Dict[str, int]:
        """Get count of applications by status for a job"""
        try:
            result = self.client.table('applications').select('status').eq('job_id', job_id).execute()
            applications = result.data or []
            
            status_counts = {}
            for app in applications:
                status = app['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return status_counts
        except Exception as e:
            logger.error(f"Failed to get status counts: {e}")
            return {}
    
    # ============================================================================
    # ANALYTICS METHODS
    # ============================================================================
    
    def get_job_analytics(self, job_id: str) -> Dict:
        """Get analytics for a job"""
        try:
            result = self.client.table('applications').select('*').eq('job_id', job_id).execute()
            applications = result.data or []
            
            if not applications:
                return {
                    "total_applicants": 0,
                    "average_score": 0,
                    "score_distribution": {},
                    "status_counts": {},
                    "top_candidates": []
                }
            
            scores = [app['overall_score'] for app in applications]
            avg_score = sum(scores) / len(scores)
            
            # Performance tier distribution
            tier_counts = {}
            for app in applications:
                tier = app['performance_tier']
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
            
            # Status distribution
            status_counts = {}
            for app in applications:
                status = app['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Top candidates
            top = sorted(applications, key=lambda x: x['overall_score'], reverse=True)[:10]
            top_candidates = [
                {
                    "user_id": app['user_id'],
                    "score": app['overall_score'],
                    "tier": app['performance_tier'],
                    "status": app['status']
                }
                for app in top
            ]
            
            return {
                "total_applicants": len(applications),
                "average_score": round(avg_score, 2),
                "score_distribution": tier_counts,
                "status_counts": status_counts,
                "top_candidates": top_candidates
            }
        except Exception as e:
            logger.error(f"Failed to get job analytics: {e}")
            return {"total_applicants": 0, "average_score": 0}
    
    def get_platform_stats(self) -> Dict:
        """Get overall platform statistics"""
        try:
            # Get counts
            users_result = self.client.table('users').select('user_id', count='exact').execute()
            apps_result = self.client.table('applications').select('*').execute()
            
            total_users = users_result.count or 0
            applications = apps_result.data or []
            total_applications = len(applications)
            
            if applications:
                scores = [app['overall_score'] for app in applications]
                avg_score = sum(scores) / len(scores)
                
                status_distribution = {}
                for app in applications:
                    status = app['status']
                    status_distribution[status] = status_distribution.get(status, 0) + 1
            else:
                avg_score = 0
                status_distribution = {}
            
            return {
                "total_users": total_users,
                "total_applications": total_applications,
                "avg_score": round(avg_score, 2),
                "status_distribution": status_distribution
            }
        except Exception as e:
            logger.error(f"Failed to get platform stats: {e}")
            return {
                "total_users": 0,
                "total_applications": 0,
                "avg_score": 0,
                "status_distribution": {}
            }
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    @staticmethod
    def determine_application_status(score: int, tier: str) -> str:
        """Determine application status based on score and tier"""
        if score >= 90 and tier in ["Exceptional", "Strong"]:
            return "selected"
        elif score >= 80:
            return "shortlisted"
        elif score >= 70:
            return "waitlisted"
        else:
            return "rejected"