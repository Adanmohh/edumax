# my_app/routes/courses.py
import uuid
import json
import sys
import traceback
from fastapi import APIRouter, Body, Depends, HTTPException
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
    user = login_required(data.token, db)
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
    except HTTPException as he:
        print(f"HTTP Exception in create_course: {he.detail}", file=sys.stderr)
        return JSONResponse(
            {"error": he.detail},
            status_code=he.status_code
        )
    except Exception as e:
        print(f"Unexpected error in create_course: {str(e)}", file=sys.stderr)
        print(f"Error traceback: {traceback.format_exc()}", file=sys.stderr)
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
    user = login_required(data.token, db)
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
    user = login_required(data.token, db)
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

@router.get("/schools/{school_id}/courses")
def get_school_courses(
    school_id: int,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Get all courses for a specific school
    """
    if not token:
        return JSONResponse({"error": "Token required"}, status_code=400)

    user = login_required(token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    # Check if user has access to this school
    if user.role != "superadmin" and user.school_id != school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        # Query courses filtered by school_id
        courses = db.query(Course).filter(Course.school_id == school_id).all()
        
        return [
            {
                "id": course.id,
                "title": course.title,
                "duration_weeks": course.duration_weeks,
                "is_finalized": course.is_finalized
            }
            for course in courses
        ]
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to get courses: {str(e)}"},
            status_code=500
        )

@router.get("/courses/{course_id}")
def get_course(
    course_id: int,
    token: str = None,
    db: Session = Depends(get_db)
):
    """
    Get course details including modules and lessons
    """
    if not token:
        return JSONResponse({"error": "Token required"}, status_code=400)

    user = login_required(token, db)
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
