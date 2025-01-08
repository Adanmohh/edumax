from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json

from ..database import get_db
from ..models import User, Course
from ..schemas import CourseCreate, ModuleCreate, CourseFinalize
from .auth import login_required
from ..workflows.enhanced_course_workflow import EnhancedCourseCreationWorkflow

router = APIRouter()

# Store active workflows
active_workflows: Dict[int, EnhancedCourseCreationWorkflow] = {}

@router.post("/v2/courses/create")
async def create_course_v2(
    data: CourseCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Enhanced course creation endpoint with progress tracking
    """
    user = login_required(data.token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    if user.role != "superadmin" and user.school_id != data.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        # Create workflow instance
        workflow = EnhancedCourseCreationWorkflow()
        
        # Start course creation
        modules_created = await workflow.start_course(
            school_id=data.school_id,
            title=data.title,
            duration_weeks=data.duration_weeks,
            curriculum_id=data.curriculum_id or 0
        )
        
        # Store workflow for progress tracking
        course_id = modules_created.event_data["course_id"]
        active_workflows[course_id] = workflow
        
        # Run remaining steps in background
        background_tasks.add_task(
            complete_course_creation,
            workflow,
            modules_created,
            course_id
        )
        
        return {
            "course_id": course_id,
            "modules": json.loads(modules_created.event_data["modules_data"]),
            "status": "processing",
            "message": "Course creation started. Use the progress endpoint to track status."
        }
        
    except HTTPException as he:
        return JSONResponse(
            {"error": he.detail},
            status_code=he.status_code
        )
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to create course: {str(e)}"},
            status_code=500
        )

async def complete_course_creation(
    workflow: EnhancedCourseCreationWorkflow,
    modules_created: Any,
    course_id: int
):
    """Complete course creation in background"""
    try:
        await workflow.create_lessons(modules_created)
        await workflow.finalize_course(modules_created)
    finally:
        # Cleanup workflow
        if course_id in active_workflows:
            del active_workflows[course_id]

@router.get("/v2/courses/{course_id}/progress")
async def get_course_progress(
    course_id: int,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Get course creation progress
    """
    user = login_required(token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)
        
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return JSONResponse({"error": "Course not found"}, status_code=404)
        
    if user.role != "superadmin" and user.school_id != course.school_id:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
        
    # Get workflow if still active
    workflow = active_workflows.get(course_id)
    if workflow:
        # Course creation still in progress
        events = workflow.ctx.events
        latest_event = events[-1] if events else None
        
        return {
            "course_id": course_id,
            "status": "processing",
            "current_step": latest_event.event_type if latest_event else "unknown",
            "progress": {
                "total_steps": 3,
                "completed_steps": len([e for e in events if e.event_type in [
                    "course_created",
                    "lessons_created",
                    "course_finalized"
                ]])
            }
        }
    else:
        # Course creation completed or not started
        return {
            "course_id": course_id,
            "status": "completed" if course.is_finalized else "not_started",
            "current_step": "finished" if course.is_finalized else None
        }

@router.get("/v2/courses/{course_id}")
async def get_course_v2(
    course_id: int,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Enhanced course details endpoint
    """
    user = login_required(token, db)
    if not user:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return JSONResponse({"error": "Course not found"}, status_code=404)

        if user.role != "superadmin" and user.school_id != course.school_id:
            return JSONResponse({"error": "Forbidden"}, status_code=403)

        # Enhanced response with curriculum context if available
        response = {
            "id": course.id,
            "title": course.title,
            "duration_weeks": course.duration_weeks,
            "is_finalized": course.is_finalized,
            "modules": [
                {
                    "id": module.id,
                    "name": module.name,
                    "description": module.description,
                    "learning_outcomes": json.loads(module.learning_outcomes) if module.learning_outcomes else [],
                    "prerequisites": json.loads(module.prerequisites) if module.prerequisites else [],
                    "estimated_duration": module.estimated_duration,
                    "lessons": [
                        {
                            "id": lesson.id,
                            "name": lesson.name,
                            "description": lesson.description,
                            "key_points": json.loads(lesson.key_points) if lesson.key_points else [],
                            "activities": json.loads(lesson.activities) if lesson.activities else [],
                            "content": lesson.content
                        }
                        for lesson in module.lessons
                    ]
                }
                for module in course.modules
            ]
        }

        # Add curriculum context if available
        if course.curriculum_id and course.curriculum_context_cache:
            context = json.loads(course.curriculum_context_cache)
            response.update({
                "curriculum_context": {
                    "learning_objectives": json.loads(course.learning_objectives) if course.learning_objectives else [],
                    "key_concepts": json.loads(course.key_concepts) if course.key_concepts else [],
                    "skill_level": course.skill_level,
                    "themes": json.loads(course.themes) if course.themes else [],
                    "progression_path": json.loads(course.progression_path) if course.progression_path else {},
                    "teaching_approach": json.loads(course.teaching_approach) if course.teaching_approach else {},
                    "core_competencies": json.loads(course.core_competencies) if course.core_competencies else []
                }
            })

        return response

    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to get course details: {str(e)}"},
            status_code=500
        )
