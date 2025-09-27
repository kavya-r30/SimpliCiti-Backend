import os
import json
import logging
import tempfile
from pathlib import Path
from io import BytesIO
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
        
        # Prompts from original code
        self.extract_prompt = """
        Extract the key requirements from the following job description.

        Job Description:
        {job_desc}

        Provide the output in the following JSON format:
        {{
          "required_experience_years": integer,
          "required_education_level": string,
          "required_skills": [list of strings],
          "optional_skills": [list of strings],
          "certifications_preferred": [list of strings],
          "soft_skills": [list of strings],
          "keywords_to_match": [list of strings],
          "location": {{
            "country": string,
            "city": string
          }},
          "emphasis": {{
            "technical_skills_weight": integer,
            "soft_skills_weight": integer,
            "experience_weight": integer,
            "education_weight": integer,
            "language_proficiency_weight": integer,
            "certifications_weight": integer,
            "location_weight": integer
          }}
        }}

        Only output valid JSON. Strictly no explanation, no comments, no intro.
        """
        
        self.standardize_prompt = """
        Given the following raw text extracted from a resume, convert it into a unified format following these guidelines:

        Resume Object Model Definition (Markdown):
        ===
        # Full legal name as it appears on official documents
        ## Specific position or role aimed for

        Format: Email / Phone / Country / City

        ## Summary
        Brief overview of qualifications and career goals

        ## Skills
        Format: _skill, skill, skill_

        ## Employment History
        **Company / Job Title / Location**
        Start - End Date
        - Responsibility 1
        - Responsibility 2

        ## Education
        **Institution / Degree / Location**
        Start - End Date

        ## Courses (Optional)
        **Platform / Course Title**
        Start - End Date

        ## Languages (Optional)
        **Language / Proficiency**

        ## Links (Optional)
        - [Title](URL)

        ## Certifications (Optional)
        List of certifications

        Raw Resume Text:
        ~~~
        {resume_text}
        ~~~

        Structure the resume according to the format. Only include sections present in the original text.
        Do not invent information. Use telegraphic English with no fluff.
        Output clean Markdown format only. No intro, no explanations, no comments.
        """
        
        self.scoring_criteria = [
            {
                "name": "Technical Skills",
                "key": "technical_skills", 
                "description": "Assign points for each required and optional skill, considering proficiency level.",
                "factors": ["Proficiency in required skills", "Optional skills", "Learning ability"]
            },
            {
                "name": "Experience",
                "key": "experience",
                "description": "Assign points based on relevance and quality of experience.",
                "factors": ["Years of experience", "Role relevance", "Achievements"]
            },
            {
                "name": "Education", 
                "key": "education",
                "description": "Assign points based on education level and relevance.",
                "factors": ["Education level", "Field relevance", "Institution quality"]
            },
            {
                "name": "Soft Skills",
                "key": "soft_skills",
                "description": "Assign points for soft skills demonstrated through examples.",
                "factors": ["Communication", "Leadership", "Problem-solving"]
            },
            {
                "name": "Location Match",
                "key": "location_match", 
                "description": "Assign points based on location compatibility.",
                "factors": ["Geographic proximity", "Remote capability", "Relocation willingness"]
            },
            {
                "name": "Certifications",
                "key": "certifications",
                "description": "Assign points for relevant certifications.",
                "factors": ["Required certifications", "Industry credentials"]
            },
            {
                "name": "Language Proficiency",
                "key": "language_proficiency",
                "description": "Assign points for language skills.",
                "factors": ["Required languages", "Communication ability"]
            }
        ]

    @staticmethod    
    def save_temp_file(file_bytes: bytes, filename: str) -> str:
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            return tmp.name
    
    async def extract_resume_data(self, file_bytes: bytes, filename: str) -> Dict:
        temp_path = self.save_temp_file(file_bytes, filename)

        image = None
        uploaded_file = None

        if filename.lower().endswith('.pdf'):
            uploaded_file = genai.upload_file(temp_path)
        elif filename.lower().endswith(('.png', '.jpeg', '.jpg', '.webp')):
            image = Image.open(temp_path)
            uploaded_file = image
        
        extraction_prompt = """
        Extract comprehensive information from this resume and structure it as JSON.
        
        Extract:
        1. Personal Details: name, email, phone, location (city, country)
        2. Skills: technical skills and soft skills separately
        3. Work Experience: company, role, duration, location, key responsibilities
        4. Education: institution, degree, field, graduation year, location
        5. Certifications: name, issuing organization, date obtained
        6. Languages: language name and proficiency level
        7. Projects: project name, description, technologies used
        8. Awards/Achievements: title, organization, date
        
        Return structured JSON:
        {
            "personal_details": {
                "name": "", "email": "", "phone": "", "location": ""
            },
            "skills": {
                "technical": ["", "", ""],
                "soft": ["", "", ""]
            },
            "experience": [
                {
                    "company": "",
                    "role": "", 
                    "duration": "",
                    "location": "",
                    "responsibilities": ["Achievement 1", "Achievement 2"]
                }
            ],
            "education": [
                {
                    "institution": "University Name",
                    "degree": "",
                    "field": "",
                    "graduation_year": "",
                    "location": ""
                }
            ],
            "certifications": [
                {
                    "name": "",
                    "organization": "",
                    "date": ""
                }
            ],
            "languages": [
                {
                    "language": "",
                    "proficiency": ""
                }
            ],
            "projects": [
                {
                    "name": "",
                    "description": "",
                    "technologies": ["", "", ""]
                }
            ],
            "awards": [
                {
                    "title": "",
                    "organization": "", 
                    "date": ""
                }
            ]
        }
        
        Only extract information that is clearly present. Do not invent or assume details.
        """
        
        try:
            if image:
                response = self.model.generate_content([extraction_prompt, uploaded_file])
            else:
                response = self.model.generate_content([extraction_prompt, uploaded_file])
            
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]
            
            extracted_data = json.loads(response_text)
            return extracted_data
            
        except Exception as e:
            logger.error(f"Resume data extraction failed: {e}")
            return {
                "personal_details": {},
                "skills": {"technical": [], "soft": []},
                "experience": [],
                "education": [],
                "certifications": [],
                "languages": [],
                "projects": [],
                "awards": [],
                "error": str(e)
            }
    

    async def evaluate_resume(self, file_bytes, filename: str, 
                            job_requirements: Dict, user_id: str, job_id: str) -> ResumeAnalysis:
        
        temp_path = self.save_temp_file(file_bytes, filename)

        image = None
        uploaded_file = None

        if filename.lower().endswith('.pdf'):
            uploaded_file = genai.upload_file(temp_path)
        elif filename.lower().endswith(('.png', '.jpeg', '.jpg', '.webp')):
            image = Image.open(temp_path)
            uploaded_file = image
        
        analysis_prompt = f"""
        Analyze this resume comprehensively against the job requirements.
        
        Job Requirements:
        {json.dumps(job_requirements, indent=2)}
        
        Analyze from the given document
        
        Extract and analyze:
        1. Personal details (name, email, phone, location)
        2. Technical skills with proficiency indicators
        3. Work experience with achievements
        4. Education with grades/honors if mentioned
        5. Certifications and credentials
        6. Languages with proficiency levels
        7. Soft skills evidence from descriptions
        
        Then provide individual scoring for each criterion (0-100):
        - Technical Skills: Match with required skills
        - Experience: Relevance and quality of work history
        - Education: Educational background alignment
        - Soft Skills: Communication and leadership evidence
        - Location Match: Geographic/remote compatibility
        - Certifications: Professional credentials
        - Language Proficiency: Communication capabilities
        
        Do not invent information. No intro, no explanations, no comments. 
        Return detailed JSON with reasoning for each score.
        
        JSON Format:
        {{
            "personal_details": {{"name": "", "email": "", "phone": "", "location": ""}},
            "skills": {{"technical": [], "soft": []}},
            "experience": [{{}}],
            "education": [{{}}],
            "certifications": [],
            "languages": [],
            "individual_scoring": {{
                "technical_skills": {{"score": 85, "reasoning": "Strong match in React, JavaScript...", "red_flags": []}},
                "experience": {{"score": 70, "reasoning": "Good experience but...", "red_flags": []}},
                "education": {{"score": 80, "reasoning": "", "red_flags": []}},
                "soft_skills": {{"score": 75, "reasoning": "", "red_flags": []}},
                "location_match": {{"score": 90, "reasoning": "", "red_flags": []}},
                "certifications": {{"score": 60, "reasoning": "", "red_flags": []}},
                "language_proficiency": {{"score": 85, "reasoning": "", "red_flags": []}}
            }},
            "overall_assessment": {{
                "match_reasons": ["reason1", "reason2", "reason3"],
                "suggestions": ["suggestion1", "suggestion2", "suggestion3"],
                "overall_impression": "Strong candidate with..."
            }}
        }}
        """
        
        try:
            if image:
                response = self.model.generate_content([analysis_prompt, uploaded_file])
            else:
                response = self.model.generate_content([analysis_prompt, uploaded_file])
            
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]
            
            analysis_data = json.loads(response_text)
            
            individual_scores = analysis_data.get("individual_scoring", {})
            weights = job_requirements.get("weights", {})
            
            total_score = 0
            total_weight = 0
            all_red_flags = []
            
            scores = {}
            for criterion_key, criterion_data in individual_scores.items():
                score = criterion_data.get("score", 0)
                weight = weights.get(criterion_key.replace("_", ""), weights.get(criterion_key, 10))
                
                scores[criterion_key] = score
                total_score += score * weight
                total_weight += weight
                
                red_flags = criterion_data.get("red_flags", [])
                all_red_flags.extend(red_flags)
            
            overall_score = int(total_score / total_weight) if total_weight > 0 else 0
            
            performance_tier, _ = get_performance_tier(overall_score)
            
            result = ResumeAnalysis(
                user_id=user_id,
                job_id=job_id,
                overall_score=overall_score,
                performance_tier=performance_tier,
                technical_skills=scores.get("technical_skills", 0),
                experience=scores.get("experience", 0),
                education=scores.get("education", 0),
                soft_skills=scores.get("soft_skills", 0),
                location_match=scores.get("location_match", 0),
                certifications=scores.get("certifications", 0),
                language_proficiency=scores.get("language_proficiency", 0),
                match_reasons=" | ".join(analysis_data.get("overall_assessment", {}).get("match_reasons", [])),
                suggestions=analysis_data.get("overall_assessment", {}).get("suggestions", []),
                red_flags=all_red_flags,
                extracted_data=analysis_data
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Resume evaluation failed: {e}")
            return ResumeAnalysis(
                user_id=user_id,
                job_id=job_id,
                overall_score=0,
                performance_tier="Poor",
                technical_skills=0,
                experience=0,
                education=0,
                soft_skills=0,
                location_match=0,
                certifications=0,
                language_proficiency=0,
                match_reasons="Analysis failed",
                suggestions=["Please try uploading again"],
                red_flags=["Evaluation error"],
                extracted_data={"error": str(e)}
            )
    
    async def evaluate_extracted_data(self, extracted_data: Dict, job_requirements: Dict, 
                                    user_id: str, job_id: str) -> ResumeAnalysis:
        scoring_prompt = f"""
        Re-score this candidate against new job requirements:
        
        Previous Analysis:
        {json.dumps(extracted_data, indent=2)}
        
        New Job Requirements:
        {json.dumps(job_requirements, indent=2)}
        
        Provide updated individual scores (0-100) in JSON format:
        {{
            "individual_scoring": {{
                "technical_skills": {{"score": 85}},
                "experience": {{"score": 70}},
                "education": {{"score": 80}},
                "soft_skills": {{"score": 75}},
                "location_match": {{"score": 90}},
                "certifications": {{"score": 60}},
                "language_proficiency": {{"score": 85}}
            }},
            "match_reasons": ["reason1", "reason2"],
            "suggestions": ["suggestion1", "suggestion2"]
        }}
        """
        
        try:
            response = self.model.generate_content(scoring_prompt)
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3]
            
            new_analysis = json.loads(response_text)
            
            individual_scores = new_analysis.get("individual_scoring", {})
            weights = job_requirements.get("weights", {})
            
            total_score = 0
            total_weight = 0
            
            scores = {}
            for criterion_key, criterion_data in individual_scores.items():
                score = criterion_data.get("score", 0)
                weight = weights.get(criterion_key.replace("_", ""), weights.get(criterion_key, 10))
                
                scores[criterion_key] = score
                total_score += score * weight
                total_weight += weight
            
            overall_score = int(total_score / total_weight) if total_weight > 0 else 0
            performance_tier, _ = get_performance_tier(overall_score)
            
            return ResumeAnalysis(
                user_id=user_id,
                job_id=job_id,
                overall_score=overall_score,
                performance_tier=performance_tier,
                technical_skills=scores.get("technical_skills", 0),
                experience=scores.get("experience", 0),
                education=scores.get("education", 0),
                soft_skills=scores.get("soft_skills", 0),
                location_match=scores.get("location_match", 0),
                certifications=scores.get("certifications", 0),
                language_proficiency=scores.get("language_proficiency", 0),
                match_reasons=" | ".join(new_analysis.get("match_reasons", [])),
                suggestions=new_analysis.get("suggestions", []),
                red_flags=[],
                extracted_data=extracted_data
            )
            
        except Exception as e:
            logger.error(f"Re-evaluation failed: {e}")
            return ResumeAnalysis(
                user_id=user_id,
                job_id=job_id,
                overall_score=50,
                performance_tier="Moderate",
                technical_skills=50,
                experience=50,
                education=50,
                soft_skills=50,
                location_match=50,
                certifications=50,
                language_proficiency=50,
                match_reasons="Re-analysis with existing data",
                suggestions=["Consider updating resume for this role"],
                red_flags=[],
                extracted_data=extracted_data
            )