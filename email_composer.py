import os
import resend
import logging
from typing import Dict, Any

from models import ResumeAnalysis

logger = logging.getLogger(__name__)

class EmailComposer:
    def __init__(self):
        resend.api_key = os.getenv("RESEND_API_KEY")
        self.sender_email = os.getenv("RESEND_SENDER_EMAIL", "onboarding@resend.dev")
        
        self.templates = {
            "acceptance": {
                "subject": "Interview Invitation - {job_title} at {company}",
                "body": """Dear {candidate_name},

Thank you for your interest in the {job_title} position at {company}. After reviewing your resume, we're impressed with your qualifications and would like to invite you for an interview.

Your application scored {overall_score}% match with our requirements, particularly strong in:
{strengths}

We'll contact you within 2 business days to schedule the interview.

Best regards,
Hiring Team
{company}"""
            },
            "rejection": {
                "subject": "Update on Your Application - {job_title}",
                "body": """Dear {candidate_name},

Thank you for your interest in the {job_title} position at {company}. After careful consideration, we've decided to move forward with other candidates whose experience more closely matches our current needs.

Your application showed strengths in {strengths}. For future opportunities, consider:

{suggestions}

We'll keep your resume on file for future openings.

Best wishes,
Hiring Team
{company}"""
            },
            "waitlist": {
                "subject": "Your Application Status - {job_title}",
                "body": """Dear {candidate_name},

Thank you for applying to the {job_title} position at {company}. Your application scored {overall_score}% match.

While you have valuable skills in {strengths}, we're currently focusing on candidates with stronger experience in {gaps}.

We'd like to keep you in consideration. Consider strengthening:
{suggestions}

Best regards,
Hiring Team
{company}"""
            }
        }
    
    def generate_email(self, analysis: ResumeAnalysis, job_data: Dict, 
                      candidate_data: Dict) -> Dict[str, str]:
        """Generate appropriate email based on analysis results"""
        
        score = analysis.overall_score
        candidate_name = candidate_data.get("name", "Candidate")
        
        if score >= 85 and analysis.performance_tier in ["Exceptional", "Strong"]:
            template_key = "acceptance"
        elif score >= 60:
            template_key = "waitlist"
        else:
            template_key = "rejection"
        
        strengths = self._get_strengths(analysis)
        suggestions = self._format_suggestions(analysis.suggestions)
        gaps = self._get_gaps(analysis)
        
        template = self.templates[template_key]
        
        subject = template["subject"].format(
            job_title=job_data["title"],
            company=job_data["company"]
        )
        
        body = template["body"].format(
            candidate_name=candidate_name,
            job_title=job_data["title"],
            company=job_data["company"],
            overall_score=score,
            strengths=strengths,
            suggestions=suggestions,
            gaps=gaps
        )
        
        return {
            "subject": subject,
            "body": body,
            "template_type": template_key
        }
    
    def _get_strengths(self, analysis: ResumeAnalysis) -> str:
        """Extract top performing areas"""
        scores = {
            "Technical Skills": analysis.technical_skills,
            "Experience": analysis.experience,
            "Education": analysis.education,
            "Soft Skills": analysis.soft_skills
        }
        
        strong_areas = [area for area, score in scores.items() if score >= 75]
        return ", ".join(strong_areas) if strong_areas else "various technical areas"
    
    def _get_gaps(self, analysis: ResumeAnalysis) -> str:
        """Extract areas needing improvement"""
        scores = {
            "Technical Skills": analysis.technical_skills,
            "Experience": analysis.experience,
            "Education": analysis.education,
            "Soft Skills": analysis.soft_skills
        }
        
        weak_areas = [area for area, score in scores.items() if score < 60]
        return ", ".join(weak_areas) if weak_areas else "specific technical requirements"
    
    def _format_suggestions(self, suggestions: list) -> str:
        """Format suggestions as bullet points"""
        if not suggestions:
            return "• Continue developing technical skills\n• Gain more relevant experience"
        return '\n'.join([f"• {suggestion}" for suggestion in suggestions[:3]])
    
    def send_email(self, to_email: str, email_data: Dict[str, str]) -> bool:
        """Send email via Resend API"""
        if not resend.api_key:
            logger.warning("Resend API key not configured")
            return False
        
        try:
            params: resend.Emails.SendParams = {
                "from": self.sender_email,
                "to": [to_email],
                "subject": email_data["subject"],
                "html": f"<pre style='font-family: Arial, sans-serif; white-space: pre-wrap;'>{email_data['body']}</pre>",
            }
            
            email: resend.Email = resend.Emails.send(params)
            logger.info(f"Email sent successfully to {to_email} with ID: {email.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email via Resend: {e}")
            return False