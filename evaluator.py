import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv
from models import ResumeAnalysis, get_performance_tier

logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment")

genai.configure(api_key=GEMINI_API_KEY)

class ResumeEvaluator:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    @staticmethod    
    def save_temp_file(file_bytes: bytes, filename: str) -> str:
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            return tmp.name
    
    async def extract_resume_data(self, file_bytes: bytes, filename: str) -> Dict:
        temp_path = self.save_temp_file(file_bytes, filename)

        try:
            if filename.lower().endswith('.pdf'):
                uploaded_file = genai.upload_file(temp_path)
            elif filename.lower().endswith(('.png', '.jpeg', '.jpg', '.webp')):
                uploaded_file = Image.open(temp_path)
            else:
                raise ValueError(f"Unsupported file format: {filename}")
            
            extraction_prompt = """
Extract comprehensive information from this resume and structure it as JSON.

Extract:
1. Personal Details: name, email, phone, location (city, country)
2. Skills: technical skills and soft skills separately
3. Work Experience: company, role, duration, location, key responsibilities
4. Education: institution, degree, field, graduation year, location
5. Certifications: name, issuing organization, date obtained
6. Languages: language name and proficiency level
7. Projects: project name, description, technologies used, url (if mentioned)
8. Awards/Achievements: title, organization, date
9. Social Profiles: Extract only URLs explicitly mentioned in resume
   - GitHub (github.com)
   - LinkedIn (linkedin.com)
   - LeetCode (leetcode.com)
   - HackerRank (hackerrank.com)
   - CodeChef (codechef.com)
   - Codeforces (codeforces.com)
   - Portfolio/Personal Website
   - Twitter/X (twitter.com or x.com)
   - Medium/Blog (medium.com)

Return valid JSON only:
{
    "personal_details": {
        "name": "string",
        "email": "string",
        "phone": "string",
        "location": "string"
    },
    "skills": {
        "technical": ["skill1", "skill2"],
        "soft": ["skill1", "skill2"]
    },
    "experience": [
        {
            "company": "string",
            "role": "string", 
            "duration": "string",
            "location": "string",
            "responsibilities": ["resp1", "resp2"]
        }
    ],
    "education": [
        {
            "institution": "string",
            "degree": "string",
            "field": "string",
            "graduation_year": "string",
            "location": "string"
        }
    ],
    "certifications": [
        {
            "name": "string",
            "organization": "string",
            "date": "string"
        }
    ],
    "languages": [
        {
            "language": "string",
            "proficiency": "string"
        }
    ],
    "projects": [
        {
            "name": "string",
            "description": "string",
            "technologies": ["tech1", "tech2"],
            "url": "string"
        }
    ],
    "awards": [
        {
            "title": "string",
            "organization": "string", 
            "date": "string"
        }
    ],
    "social_profiles": {
        "github": "url_or_null",
        "linkedin": "url_or_null",
        "leetcode": "url_or_null",
        "hackerrank": "url_or_null",
        "codechef": "url_or_null",
        "codeforces": "url_or_null",
        "portfolio": "url_or_null",
        "twitter": "url_or_null",
        "medium": "url_or_null"
    },
    "summary": "string_or_empty"
}

IMPORTANT:
- Only extract information clearly present in the resume
- Do not invent or assume any details
- Use null for missing optional fields
- Ensure all arrays are valid (empty [] if nothing found)
- Output ONLY valid JSON, no markdown, no explanations
"""
            
            response = self.model.generate_content([extraction_prompt, uploaded_file])
            response_text = response.text.strip()

            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            extracted_data = json.loads(response_text)
            
            required_keys = ['personal_details', 'skills', 'experience', 'education']
            for key in required_keys:
                if key not in extracted_data:
                    extracted_data[key] = {} if key in ['personal_details', 'skills'] else []
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            return self._get_empty_resume_structure(error=f"Failed to parse response: {str(e)}")
        except Exception as e:
            logger.error(f"Resume data extraction failed: {e}")
            return self._get_empty_resume_structure(error=str(e))
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    async def evaluate_resume(self, file_content: bytes, filename: str, 
                            job_requirements: Dict, user_id: str, job_id: str) -> ResumeAnalysis:
        """Evaluate resume against job requirements"""
        
        temp_path = self.save_temp_file(file_content, filename)

        try:
            if filename.lower().endswith('.pdf'):
                uploaded_file = genai.upload_file(temp_path)
            elif filename.lower().endswith(('.png', '.jpeg', '.jpg', '.webp')):
                uploaded_file = Image.open(temp_path)
            else:
                raise ValueError(f"Unsupported file format: {filename}")
            
            analysis_prompt = f"""
Analyze this resume comprehensively against the job requirements.

Job Requirements:
{json.dumps(job_requirements, indent=2)}

Provide detailed scoring for each criterion (0-100 scale):

1. **Technical Skills**: Match with required technical skills
2. **Experience**: Relevance and quality of work experience
3. **Education**: Educational background alignment
4. **Soft Skills**: Communication, leadership, teamwork evidence
5. **Projects**: Quality and relevance of projects
6. **Location Match**: Geographic/remote work compatibility
7. **Certifications**: Professional credentials and certificates
8. **Language Proficiency**: Required language skills

For each score, provide:
- Numeric score (0-100)
- Reasoning explaining the score
- Red flags if any (empty array if none)

Return valid JSON only:
{{
    "personal_details": {{"name": "", "email": "", "phone": "", "location": ""}},
    "skills": {{"technical": [], "soft": []}},
    "experience": [{{}}],
    "education": [{{}}],
    "certifications": [],
    "languages": [],
    "projects": [],
    "individual_scoring": {{
        "technical_skills": {{"score": 0, "reasoning": "", "red_flags": []}},
        "experience": {{"score": 0, "reasoning": "", "red_flags": []}},
        "education": {{"score": 0, "reasoning": "", "red_flags": []}},
        "soft_skills": {{"score": 0, "reasoning": "", "red_flags": []}},
        "projects": {{"score": 0, "reasoning": "", "red_flags": []}},
        "location_match": {{"score": 0, "reasoning": "", "red_flags": []}},
        "certifications": {{"score": 0, "reasoning": "", "red_flags": []}},
        "language_proficiency": {{"score": 0, "reasoning": "", "red_flags": []}}
    }},
    "overall_assessment": {{
        "match_reasons": ["reason1", "reason2", "reason3"],
        "suggestions": ["suggestion1", "suggestion2", "suggestion3"],
        "overall_impression": "Brief summary"
    }}
}}

Output ONLY valid JSON without inventing any information, no markdown, no explanations.
"""
            
            response = self.model.generate_content([analysis_prompt, uploaded_file])
            response_text = response.text.strip()
            
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            analysis_data = json.loads(response_text)
            
            individual_scores = analysis_data.get("individual_scoring", {})
            weights = job_requirements.get("weights", {})
            
            total_score = 0
            total_weight = 0
            all_red_flags = []
            scores = {}
            
            score_keys = [
                "technical_skills",
                "experience", 
                "education",
                "soft_skills",
                "projects",
                "location_match",
                "certifications",
                "language_proficiency"
            ]
            
            for key in score_keys:
                criterion_data = individual_scores.get(key, {"score": 0, "reasoning": "", "red_flags": []})
                score = criterion_data.get("score", 0)
                
                weight_key = key.replace("_", "") if "_" in key else key
                weight = weights.get(key, weights.get(weight_key, 10))
                
                scores[key] = score
                total_score += score * weight
                total_weight += weight
                
                red_flags = criterion_data.get("red_flags", [])
                all_red_flags.extend(red_flags)
            
            overall_score = int(total_score / total_weight) if total_weight > 0 else 0
            performance_tier = get_performance_tier(overall_score)
            
            result = ResumeAnalysis(
                user_id=user_id,
                job_id=job_id,
                overall_score=overall_score,
                performance_tier=performance_tier,
                technical_skills=scores.get("technical_skills", 0),
                experience=scores.get("experience", 0),
                education=scores.get("education", 0),
                soft_skills=scores.get("soft_skills", 0),
                projects=scores.get("projects", 0),
                location_match=scores.get("location_match", 0),
                certifications=scores.get("certifications", 0),
                language_proficiency=scores.get("language_proficiency", 0),
                match_reasons=" | ".join(analysis_data.get("overall_assessment", {}).get("match_reasons", [])),
                suggestions=analysis_data.get("overall_assessment", {}).get("suggestions", []),
                red_flags=all_red_flags,
                extracted_data=analysis_data
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed during evaluation: {e}")
            return self._get_failed_analysis(user_id, job_id, f"Failed to parse AI response: {str(e)}")
        except Exception as e:
            logger.error(f"Resume evaluation failed: {e}")
            return self._get_failed_analysis(user_id, job_id, str(e))
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    async def evaluate_extracted_data(self, extracted_data: Dict, job_requirements: Dict, 
                                    user_id: str, job_id: str) -> ResumeAnalysis:
      
        scoring_prompt = f"""
Re-score this candidate's profile against the job requirements.

Candidate Profile:
{json.dumps(extracted_data, indent=2)}

Job Requirements:
{json.dumps(job_requirements, indent=2)}

Provide detailed scoring for each criterion (0-100 scale):

1. **Technical Skills**: Match with required technical skills
2. **Experience**: Relevance and quality of work experience
3. **Education**: Educational background alignment
4. **Soft Skills**: Communication, leadership, teamwork evidence
5. **Projects**: Quality and relevance of projects
6. **Location Match**: Geographic/remote work compatibility
7. **Certifications**: Professional credentials and certificates
8. **Language Proficiency**: Required language skills

For each score, provide:
- Numeric score (0-100)
- Reasoning explaining the score
- Red flags if any (empty array if none)

Return valid JSON only:
{{
    "personal_details": {{"name": "", "email": "", "phone": "", "location": ""}},
    "skills": {{"technical": [], "soft": []}},
    "experience": [{{}}],
    "education": [{{}}],
    "certifications": [],
    "languages": [],
    "projects": [],
    "individual_scoring": {{
        "technical_skills": {{"score": 0, "reasoning": "", "red_flags": []}},
        "experience": {{"score": 0, "reasoning": "", "red_flags": []}},
        "education": {{"score": 0, "reasoning": "", "red_flags": []}},
        "soft_skills": {{"score": 0, "reasoning": "", "red_flags": []}},
        "projects": {{"score": 0, "reasoning": "", "red_flags": []}},
        "location_match": {{"score": 0, "reasoning": "", "red_flags": []}},
        "certifications": {{"score": 0, "reasoning": "", "red_flags": []}},
        "language_proficiency": {{"score": 0, "reasoning": "", "red_flags": []}}
    }},
    "overall_assessment": {{
        "match_reasons": ["reason1", "reason2", "reason3"],
        "suggestions": ["suggestion1", "suggestion2", "suggestion3"],
        "overall_impression": "Brief summary"
    }}
}}

Output ONLY valid JSON without inventing any information, no markdown, no explanations.
"""
        
        try:
            response = self.model.generate_content(scoring_prompt)
            response_text = response.text.strip()
            
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            new_analysis = json.loads(response_text)
            
            individual_scores = new_analysis.get("individual_scoring", {})
            weights = job_requirements.get("weights", {})

            total_score = 0
            total_weight = 0
            all_red_flags = []
            scores = {}

            score_keys = [
                "technical_skills", "experience", "education", "soft_skills",
                "projects", "location_match", "certifications", "language_proficiency"
            ]

            for key in score_keys:
                criterion_data = individual_scores.get(key, {"score": 0, "reasoning": "", "red_flags": []})
                score = criterion_data.get("score", 0)

                weight_key = key.replace("_", "") if "_" in key else key
                weight = weights.get(key, weights.get(weight_key, 10))

                scores[key] = score
                total_score += score * weight
                total_weight += weight

                red_flags = criterion_data.get("red_flags", [])
                all_red_flags.extend(red_flags)

            overall_score = int(total_score / total_weight) if total_weight > 0 else 0
            performance_tier = get_performance_tier(overall_score)

            assessment = new_analysis.get("overall_assessment", {})

            return ResumeAnalysis(
                user_id=user_id,
                job_id=job_id,
                overall_score=overall_score,
                performance_tier=performance_tier,
                technical_skills=scores.get("technical_skills", 0),
                experience=scores.get("experience", 0),
                education=scores.get("education", 0),
                soft_skills=scores.get("soft_skills", 0),
                projects=scores.get("projects", 0),
                location_match=scores.get("location_match", 0),
                certifications=scores.get("certifications", 0),
                language_proficiency=scores.get("language_proficiency", 0),
                match_reasons=" | ".join(assessment.get("match_reasons", [])),
                suggestions=assessment.get("suggestions", []),
                red_flags=all_red_flags,
                extracted_data=new_analysis
            )
            
        except Exception as e:
            logger.error(f"Re-evaluation failed: {e}")
            return self._get_failed_analysis(user_id, job_id, f"Re-evaluation error: {str(e)}")
    
    @staticmethod
    def _get_empty_resume_structure(error: str = "") -> Dict:
        """Return empty resume structure for failed extractions"""
        return {
            "personal_details": {},
            "skills": {"technical": [], "soft": []},
            "experience": [],
            "education": [],
            "certifications": [],
            "languages": [],
            "projects": [],
            "awards": [],
            "social_profiles": {},
            "summary": "",
            "error": error
        }
    
    @staticmethod
    def _get_failed_analysis(user_id: str, job_id: str, error: str) -> ResumeAnalysis:
        """Return failed analysis with error details"""
        return ResumeAnalysis(
            user_id=user_id,
            job_id=job_id,
            overall_score=0,
            performance_tier="Poor",
            technical_skills=0,
            experience=0,
            education=0,
            soft_skills=0,
            projects=0,
            location_match=0,
            certifications=0,
            language_proficiency=0,
            match_reasons="Analysis failed",
            suggestions=["Please try uploading the resume again"],
            red_flags=[f"Evaluation error: {error}"],
            extracted_data={"error": error}
        )