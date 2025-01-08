# my_app/schemas.py
from pydantic import BaseModel
from typing import Optional, List

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "teacher"
    school_id: Optional[int] = None

class SchoolCreate(BaseModel):
    name: str
    session_token: str

class CurriculumIngest(BaseModel):
    """Schema for ingesting curriculum into vector store"""
    curriculum_id: int
    collection_name: str
    session_token: str

# --- Course / Module / Lesson / Assessment schemas ---
class CourseCreate(BaseModel):
    school_id: int
    title: str
    duration_weeks: int
    curriculum_id: Optional[int] = None
    session_token: str

class ModuleCreate(BaseModel):
    modules: List[dict]  # List of module names/details
    session_token: str

class CourseFinalize(BaseModel):
    session_token: str

class LessonCreate(BaseModel):
    module_id: int
    name: str
    content: str
    session_token: str

class AssessmentCreate(BaseModel):
    lesson_id: int
    questions: List[str]
