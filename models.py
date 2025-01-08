# my_app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from .database import Base

class School(Base):
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    users = relationship("User", back_populates="school")
    curriculums = relationship("Curriculum", back_populates="school")
    # NEW: courses for workflow
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

    school = relationship("School", back_populates="curriculums")

# --------------------------------------------------------------------------
# NEW: Course, Module, Lesson, Assessment (for the CourseCreationWorkflow)
# --------------------------------------------------------------------------
class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    duration_weeks = Column(Integer)
    is_finalized = Column(Boolean, default=False)

    # Relationship
    school_id = Column(Integer, ForeignKey("schools.id"))
    school = relationship("School", back_populates="courses")

    # One curriculum reference (optional)
    curriculum_id = Column(Integer, ForeignKey("curriculums.id"), nullable=True)

    modules = relationship("Module", back_populates="course")


class Module(Base):
    __tablename__ = "modules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

    course_id = Column(Integer, ForeignKey("courses.id"))
    course = relationship("Course", back_populates="modules")

    lessons = relationship("Lesson", back_populates="module")


class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    content = Column(Text)

    module_id = Column(Integer, ForeignKey("modules.id"))
    module = relationship("Module", back_populates="lessons")

    assessments = relationship("Assessment", back_populates="lesson")


class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(Integer, primary_key=True, index=True)
    questions = Column(Text)

    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    lesson = relationship("Lesson", back_populates="assessments")
