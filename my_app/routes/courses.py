# my_app/routes/courses.py
import uuid
import json
from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import User, Course
from ..schemas import CourseCreate, ModuleCreate, CourseFinalize
from .auth import login_required
from ..workflows.course_creation_workflow import (
    CourseCreationWorkflow, StartCourseEvent,
    ModulesCreatedEvent, LessonsCreatedEvent
)

router = APIRouter()

@router.post("/courses/create")
async def create_course(
    data: CourseCreate,
    db: Session = Depends(get_db)
):
    """
    Step 1: Create initial course with basic info
    """
    user = login_required(data.session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    if user.role != "superadmin" and user.school_id != data.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        workflow = CourseCreationWorkflow()
        event = StartCourseEvent(
            school_id=data.school_id,
            title=data.title,
            duration_weeks=data.duration_weeks,
            curriculum_id=data.curriculum_id or 0
        )
        
        modules_created = await workflow.start_course(event)
        return {
            "course_id": modules_created.course_id,
            "modules": json.loads(modules_created.modules_data)
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to create course: {str(e)}"},
            status_code=500
        )

@router.post("/courses/{course_id}/modules")
async def create_course_modules(
    course_id: int,
    data: ModuleCreate,
    db: Session = Depends(get_db)
):
    """
    Step 2: Create or update modules for a course
    """
    user = login_required(data.session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return JSONResponse({"error": "Course not found"}, status_code=404)

    if user.role != "superadmin" and user.school_id != course.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        workflow = CourseCreationWorkflow()
        modules_event = ModulesCreatedEvent(
            course_id=course_id,
            modules_data=json.dumps(data.modules)
        )
        
        lessons_created = await workflow.create_lessons(modules_event)
        return {
            "course_id": course_id,
            "lessons": json.loads(lessons_created.lessons_data)
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to create modules: {str(e)}"},
            status_code=500
        )

@router.post("/courses/{course_id}/finalize")
async def finalize_course(
    course_id: int,
    data: CourseFinalize,
    db: Session = Depends(get_db)
):
    """
    Step 3: Finalize the course
    """
    user = login_required(data.session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return JSONResponse({"error": "Course not found"}, status_code=404)

    if user.role != "superadmin" and user.school_id != course.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        workflow = CourseCreationWorkflow()
        lessons_event = LessonsCreatedEvent(
            course_id=course_id,
            lessons_data="{}"  # Not needed for finalization
        )
        
        result = await workflow.finalize_course(lessons_event)
        return {
            "course_id": course_id,
            "status": "finalized",
            "message": result.result
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to finalize course: {str(e)}"},
            status_code=500
        )

@router.get("/courses/{course_id}")
def get_course(
    course_id: int,
    session_token: str = None,
    db: Session = Depends(get_db)
):
    """
    Get course details including modules and lessons
    """
    if not session_token:
        return JSONResponse({"error": "Session token required"}, status_code=400)

    user = login_required(session_token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return JSONResponse({"error": "Course not found"}, status_code=404)

        if user.role != "superadmin" and user.school_id != course.school_id:
            return JSONResponse({"error": "Forbidden"}, status_code=403)

        return {
            "id": course.id,
            "title": course.title,
            "duration_weeks": course.duration_weeks,
            "is_finalized": course.is_finalized,
            "modules": [
                {
                    "id": module.id,
                    "name": module.name,
                    "lessons": [
                        {
                            "id": lesson.id,
                            "name": lesson.name,
                            "content": lesson.content
                        }
                        for lesson in module.lessons
                    ]
                }
                for module in course.modules
            ]
        }
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to get course details: {str(e)}"},
            status_code=500
        )
