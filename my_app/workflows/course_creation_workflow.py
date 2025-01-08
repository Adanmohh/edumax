from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
import json

from ..database import SessionLocal
from ..models import Course, Module, Lesson, Curriculum
from .curriculum_extraction_workflow import CurriculumExtractionWorkflow
from .ai_outline_generator import AIOutlineGenerator

##########################
# MODELS
##########################
class StartCourseEvent(BaseModel):
    """Initial event with basic course info"""
    school_id: int
    title: str
    duration_weeks: int
    curriculum_id: int  # optional; can be 0 if none

class ModulesCreatedEvent(BaseModel):
    """After modules are created"""
    course_id: int
    modules_data: str  # JSON list of {name:..}

class LessonsCreatedEvent(BaseModel):
    """After lessons are created"""
    course_id: int
    lessons_data: str

class StopEvent(BaseModel):
    """Final completion event"""
    result: str

##########################
# THE WORKFLOW CLASS
##########################
class CourseCreationWorkflow:
    def __init__(self):
        self.ctx = {}
        self.curriculum_extractor = CurriculumExtractionWorkflow()
        self.ai_generator = AIOutlineGenerator()

    async def start_course(
        self, ev: StartCourseEvent
    ) -> ModulesCreatedEvent:
        """
        Step 1: Create Course with comprehensive curriculum context
        """
        db = SessionLocal()
        try:
            modules_list = []
            if ev.curriculum_id:
                # Get curriculum info
                curriculum = db.query(Curriculum).filter(Curriculum.id == ev.curriculum_id).first()
                if not curriculum:
                    raise HTTPException(
                        status_code=404,
                        detail="Curriculum not found"
                    )
                
                if not curriculum.vector_key:
                    raise HTTPException(
                        status_code=400,
                        detail="Curriculum has not been processed yet. Please run curriculum ingestion first via /curriculum/ingest endpoint"
                    )
                
                try:
                    # Extract comprehensive curriculum context
                    curriculum_context = await self.curriculum_extractor.extract_comprehensive_context(
                        collection_name=curriculum.vector_key,
                        context_type='course'
                    )
                except HTTPException as he:
                    raise HTTPException(
                        status_code=he.status_code,
                        detail=f"Failed to extract curriculum info: {he.detail}"
                    )
                
                # Create course with comprehensive context
                course = Course(
                    school_id=ev.school_id,
                    title=ev.title,
                    duration_weeks=ev.duration_weeks,
                    curriculum_id=ev.curriculum_id,
                    # Basic context
                    learning_objectives=json.dumps(curriculum_context.learning_objectives),
                    key_concepts=json.dumps(curriculum_context.key_concepts),
                    skill_level=curriculum_context.skill_level,
                    # Enhanced context
                    themes=json.dumps(curriculum_context.themes),
                    progression_path=json.dumps(curriculum_context.progression_path),
                    teaching_approach=json.dumps(curriculum_context.teaching_approach),
                    core_competencies=json.dumps(curriculum_context.core_competencies),
                    # Cache full context
                    curriculum_context_cache=json.dumps(curriculum_context.dict()),
                    last_context_update=curriculum_context.extraction_timestamp
                )
                db.add(course)
                db.commit()
                db.refresh(course)
                
                # Generate modules using comprehensive context
                total_modules = max(ev.duration_weeks, 3)
                for i in range(total_modules):
                    # Extract module-specific context
                    module_context = await self.curriculum_extractor.extract_comprehensive_context(
                        collection_name=curriculum.vector_key,
                        context_type='module',
                        parent_context_id=course.id,
                        specific_focus=f"Module {i+1} content and structure"
                    )
                    
                    # Generate module outline using combined context
                    module_outline = await self.ai_generator.generate_module_outline(
                        curriculum_context=curriculum_context,  # Base context
                        module_number=i + 1,
                        total_modules=total_modules
                    )
                    
                    # Create module with context
                    m = Module(
                        course_id=course.id,
                        name=module_outline.name,
                        description=module_outline.description,
                        learning_outcomes=json.dumps(module_outline.learning_outcomes),
                        prerequisites=json.dumps(module_outline.prerequisites),
                        estimated_duration=module_outline.estimated_duration,
                        # Store module-specific context
                        theme_context=json.dumps(module_context.themes),
                        module_context_cache=json.dumps(module_context.dict())
                    )
                    db.add(m)
                    db.commit()
                    db.refresh(m)
                    
                    modules_list.append({
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "learning_outcomes": module_outline.learning_outcomes,
                        "prerequisites": module_outline.prerequisites,
                        "estimated_duration": module_outline.estimated_duration,
                        "themes": module_context.themes
                    })
            else:
                # Create course without curriculum
                course = Course(
                    school_id=ev.school_id,
                    title=ev.title,
                    duration_weeks=ev.duration_weeks
                )
                db.add(course)
                db.commit()
                db.refresh(course)

                # Create default modules
                for i in range(ev.duration_weeks):
                    m = Module(
                        name=f"Module_{i+1}",
                        course_id=course.id
                    )
                    db.add(m)
                    db.commit()
                    db.refresh(m)
                    modules_list.append({
                        "id": m.id,
                        "name": m.name
                    })

            return ModulesCreatedEvent(
                course_id=course.id,
                modules_data=json.dumps(modules_list)
            )
        finally:
            db.close()

    async def create_lessons(
        self, ev: ModulesCreatedEvent
    ) -> LessonsCreatedEvent:
        """
        Step 2: Create lessons using hierarchical context
        """
        db = SessionLocal()
        try:
            modules_list = json.loads(ev.modules_data)
            course = db.query(Course).filter(Course.id == ev.course_id).first()
            lessons_info = []

            if course and course.curriculum_id:
                curriculum = db.query(Curriculum).filter(Curriculum.id == course.curriculum_id).first()
                if not curriculum or not curriculum.vector_key:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid curriculum configuration"
                    )
                
                # Load course context from cache
                course_context = json.loads(course.curriculum_context_cache)
                
                for mod_info in modules_list:
                    module = db.query(Module).filter(Module.id == mod_info["id"]).first()
                    if not module:
                        continue
                    
                    # Load module context from cache
                    module_context = json.loads(module.module_context_cache)
                    
                    # Generate 4 lessons per module
                    for i in range(1, 5):
                        # Extract lesson-specific context
                        lesson_context = await self.curriculum_extractor.extract_comprehensive_context(
                            collection_name=curriculum.vector_key,
                            context_type='lesson',
                            parent_context_id=module.id,
                            specific_focus=f"{module.name} Lesson {i}"
                        )
                        
                        # Generate lesson content using hierarchical context
                        lesson_outline = await self.ai_generator.generate_lesson_outline(
                            curriculum_context=lesson_context,
                            module_name=module.name,
                            lesson_number=i,
                            total_lessons=4
                        )
                        
                        content_sections = await self.ai_generator.generate_lesson_content(
                            curriculum_context=lesson_context,
                            lesson_outline=lesson_outline
                        )
                        
                        full_content = "\n\n".join([
                            f"# {section.title}\n\n{section.content}"
                            for section in content_sections
                        ])
                        
                        all_examples = []
                        all_exercises = []
                        for section in content_sections:
                            all_examples.extend(section.examples)
                            all_exercises.extend(section.exercises)
                        
                        lesson = Lesson(
                            module_id=module.id,
                            name=lesson_outline.name,
                            description=lesson_outline.description,
                            content=full_content,
                            key_points=json.dumps(lesson_outline.key_points),
                            activities=json.dumps(lesson_outline.activities),
                            resources=json.dumps(lesson_outline.resources),
                            assessment_ideas=json.dumps(lesson_outline.assessment_ideas),
                            examples=json.dumps(all_examples),
                            exercises=json.dumps(all_exercises),
                            # Store lesson-specific context
                            topic_context=json.dumps(lesson_context.themes),
                            lesson_context_cache=json.dumps(lesson_context.dict())
                        )
                        db.add(lesson)
                        db.commit()
                        db.refresh(lesson)
                        
                        lessons_info.append({
                            "module_id": module.id,
                            "lesson_id": lesson.id,
                            "lesson_name": lesson.name,
                            "description": lesson.description
                        })
            else:
                # Create default lessons without context
                for mod_info in modules_list:
                    for i in range(1, 5):
                        lesson = Lesson(
                            module_id=mod_info["id"],
                            name=f"Lesson_{i}",
                            content=f"Default content for Lesson_{i}"
                        )
                        db.add(lesson)
                        db.commit()
                        db.refresh(lesson)
                        lessons_info.append({
                            "module_id": mod_info["id"],
                            "lesson_id": lesson.id,
                            "lesson_name": lesson.name
                        })

            return LessonsCreatedEvent(
                course_id=ev.course_id,
                lessons_data=json.dumps(lessons_info)
            )
        finally:
            db.close()

    async def finalize_course(
        self, ev: LessonsCreatedEvent
    ) -> StopEvent:
        """
        Step 3: Finalize course creation
        """
        db = SessionLocal()
        try:
            course = db.query(Course).filter(Course.id == ev.course_id).first()
            if course:
                course.is_finalized = True
                db.commit()

            return StopEvent(
                result=f"Course {ev.course_id} created successfully with comprehensive curriculum context"
            )
        finally:
            db.close()

    async def run(self, ev: StartCourseEvent) -> str:
        """Run complete workflow"""
        modules_created = await self.start_course(ev)
        lessons_created = await self.create_lessons(modules_created)
        stop = await self.finalize_course(lessons_created)
        return stop.result
