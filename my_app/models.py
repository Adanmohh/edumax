# my_app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from .database import Base

class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    users = relationship("User", back_populates="school")
    curriculums = relationship("Curriculum", back_populates="school")
    courses = relationship("Course", back_populates="school")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String)  # Plain-text for DEMO ONLY
    role = Column(String)      # e.g. "superadmin", "teacher"
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    school = relationship("School", back_populates="users")

class Curriculum(Base):
    __tablename__ = "curriculums"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    file_path = Column(String)   # Where we store the file
    vector_key = Column(String)  # Qdrant collection name
    school_id = Column(Integer, ForeignKey("schools.id"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    school = relationship("School", back_populates="curriculums")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    duration_weeks = Column(Integer)
    is_finalized = Column(Boolean, default=False)
    
    # Basic curriculum-derived content
    learning_objectives = Column(Text, nullable=True)  # JSON list
    key_concepts = Column(Text, nullable=True)  # JSON list
    skill_level = Column(String, nullable=True)
    
    # NEW: Additional curriculum context
    themes = Column(Text, nullable=True)  # JSON list of main themes
    progression_path = Column(Text, nullable=True)  # JSON describing learning progression
    teaching_approach = Column(Text, nullable=True)  # JSON teaching methodology
    core_competencies = Column(Text, nullable=True)  # JSON list
    curriculum_context_cache = Column(Text, nullable=True)  # JSON cache of extracted context
    last_context_update = Column(DateTime, nullable=True)  # Track context freshness

    # Relationships
    school_id = Column(Integer, ForeignKey("schools.id"))
    school = relationship("School", back_populates="courses")
    curriculum_id = Column(Integer, ForeignKey("curriculums.id"), nullable=True)
    modules = relationship("Module", back_populates="course")

class Module(Base):
    __tablename__ = "modules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(Text, nullable=True)
    learning_outcomes = Column(Text, nullable=True)  # JSON list
    prerequisites = Column(Text, nullable=True)  # JSON list
    estimated_duration = Column(String, nullable=True)
    
    # NEW: Module-specific context
    theme_context = Column(Text, nullable=True)  # JSON specific theme details
    module_context_cache = Column(Text, nullable=True)  # JSON cache of module-specific context

    course_id = Column(Integer, ForeignKey("courses.id"))
    course = relationship("Course", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module")

class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(Text, nullable=True)
    content = Column(Text)
    
    # Outline fields
    key_points = Column(Text, nullable=True)  # JSON list
    activities = Column(Text, nullable=True)  # JSON list
    resources = Column(Text, nullable=True)  # JSON list
    assessment_ideas = Column(Text, nullable=True)  # JSON list
    
    # Content sections
    examples = Column(Text, nullable=True)  # JSON list
    exercises = Column(Text, nullable=True)  # JSON list
    
    # NEW: Lesson-specific context
    topic_context = Column(Text, nullable=True)  # JSON specific topic details
    lesson_context_cache = Column(Text, nullable=True)  # JSON cache of lesson-specific context

    module_id = Column(Integer, ForeignKey("modules.id"))
    module = relationship("Module", back_populates="lessons")
    assessments = relationship("Assessment", back_populates="lesson")

class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(Integer, primary_key=True, index=True)
    questions = Column(Text)
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    lesson = relationship("Lesson", back_populates="assessments")
