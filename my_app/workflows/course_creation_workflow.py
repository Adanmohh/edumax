# my_app/workflows/course_creation_workflow.py

from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Course, Module, Lesson
import json

##########################
# MODELS
##########################
class StartCourseEvent(BaseModel):
    """
    This event triggers the workflow with basic course info.
    """
    school_id: int
    title: str
    duration_weeks: int
    curriculum_id: int  # optional; can be 0 if none

class ModulesCreatedEvent(BaseModel):
    """
    After modules are created.
    """
    course_id: int
    modules_data: str  # e.g. JSON list of {name:..}

class LessonsCreatedEvent(BaseModel):
    """
    After lessons are created for each module.
    """
    course_id: int
    lessons_data: str

class StopEvent(BaseModel):
    """
    Final event indicating workflow completion.
    """
    result: str

##########################
# THE WORKFLOW CLASS
##########################
class CourseCreationWorkflow:
    def __init__(self):
        self.ctx = {}

    async def start_course(
        self, ev: StartCourseEvent
    ) -> ModulesCreatedEvent:
        """
        Step 1: Create a Course record in DB, generate modules.
        For example, we might create # of modules based on duration_weeks.
        """
        # We'll do a standard DB session local open for demonstration
        db = SessionLocal()
        try:
            # create the course row
            course = Course(
                school_id=ev.school_id,
                title=ev.title,
                duration_weeks=ev.duration_weeks,
                curriculum_id=ev.curriculum_id if ev.curriculum_id else None
            )
            db.add(course)
            db.commit()
            db.refresh(course)

            # Suppose we create 'duration_weeks' modules by default
            modules_list = []
            for i in range(ev.duration_weeks):
                m = Module(name=f"Module_{i+1}", course_id=course.id)
                db.add(m)
                db.commit()
                db.refresh(m)
                modules_list.append({"id": m.id, "name": m.name})

            # store the modules list as JSON
            modules_data = json.dumps(modules_list)
            return ModulesCreatedEvent(
                course_id=course.id,
                modules_data=modules_data
            )
        finally:
            db.close()

    async def create_lessons(
        self, ev: ModulesCreatedEvent
    ) -> LessonsCreatedEvent:
        """
        Step 2: For each module, create some default lessons
        (e.g. 4 lessons per module).
        """
        db = SessionLocal()
        try:
            modules_list = json.loads(ev.modules_data)
            course_id = ev.course_id

            lessons_info = []

            for mod_info in modules_list:
                module_id = mod_info["id"]
                # example: create 4 lessons per module
                for i in range(1, 5):
                    lesson = Lesson(
                        module_id=module_id,
                        name=f"Lesson_{i}",
                        content=f"This is the content of Lesson_{i} in {mod_info['name']}"
                    )
                    db.add(lesson)
                    db.commit()
                    db.refresh(lesson)
                    lessons_info.append({
                        "module_id": module_id,
                        "lesson_id": lesson.id,
                        "lesson_name": lesson.name
                    })

            lessons_data = json.dumps(lessons_info)
            return LessonsCreatedEvent(
                course_id=course_id,
                lessons_data=lessons_data
            )
        finally:
            db.close()

    async def finalize_course(
        self, ev: LessonsCreatedEvent
    ) -> StopEvent:
        """
        Step 3: Mark the course as finalized (if desired).
        Could also do more steps for assessments, etc.
        """
        db = SessionLocal()
        try:
            course_id = ev.course_id
            course = db.query(Course).filter(Course.id == course_id).first()
            if course:
                # we won't forcibly set is_finalized in this step,
                # but let's pretend we do for demonstration
                course.is_finalized = True
                db.commit()

            return StopEvent(
                result=f"Course {course_id} created with modules/lessons. Finalized!"
            )
        finally:
            db.close()

    async def run(self, ev: StartCourseEvent) -> str:
        """
        Run the workflow from start to finish
        """
        modules_created = await self.start_course(ev)
        lessons_created = await self.create_lessons(modules_created)
        stop = await self.finalize_course(lessons_created)
        return stop.result
