from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime
import json

from .base_workflow import BaseWorkflow, WorkflowEvent
from .curriculum_extraction_workflow import CurriculumExtractionWorkflow
from .ai_outline_generator import AIOutlineGenerator
from ..database import SessionLocal
from ..models import Course, Module, Lesson, Curriculum
from fastapi import HTTPException

class CourseStartEvent(WorkflowEvent):
    """Initial event with basic course info"""
    event_type: str = "course_start"
    event_data: Dict = {
        "school_id": int,
        "title": str,
        "duration_weeks": int,
        "curriculum_id": int
    }

class ModulesCreatedEvent(WorkflowEvent):
    """After modules are created"""
    event_type: str = "modules_created"
    event_data: Dict = {
        "course_id": int,
        "modules_data": str  # JSON list of {name:..}
    }

class LessonsCreatedEvent(WorkflowEvent):
    """After lessons are created"""
    event_type: str = "lessons_created"
    event_data: Dict = {
        "course_id": int,
        "lessons_data": str
    }

class CourseFinishedEvent(WorkflowEvent):
    """Final completion event"""
    event_type: str = "course_finished"
    event_data: Dict = {
        "course_id": int,
        "result": str
    }

class EnhancedCourseCreationWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__()
        self.curriculum_extractor = CurriculumExtractionWorkflow()
        self.ai_generator = AIOutlineGenerator()

    async def start_course(self, school_id: int, title: str, duration_weeks: int, curriculum_id: int = 0) -> ModulesCreatedEvent:
        """
        Step 1: Create Course with comprehensive curriculum context
        """
        try:
            # Emit start event
            await self.emit_event("course_start", {
                "school_id": school_id,
                "title": title,
                "duration_weeks": duration_weeks,
                "curriculum_id": curriculum_id
            })

            db = SessionLocal()
            try:
                modules_list = []
                if curriculum_id:
                    # Get curriculum info
                    curriculum = db.query(Curriculum).filter(Curriculum.id == curriculum_id).first()
                    if not curriculum:
                        raise HTTPException(status_code=404, detail="Curriculum not found")
                    
                    if not curriculum.vector_key:
                        raise HTTPException(
                            status_code=400,
                            detail="Curriculum has not been processed yet"
                        )

                    try:
                        # Extract comprehensive curriculum context
                        curriculum_context = await self.curriculum_extractor.extract_comprehensive_context(
                            collection_name=curriculum.vector_key,
                            context_type='course'
                        )
                        
                        # Log context extraction
                        await self.emit_event("context_extracted", {
                            "curriculum_id": curriculum_id,
                            "context_type": "course"
                        })

                    except Exception as e:
                        await self.handle_error(e, "curriculum_context_extraction")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to extract curriculum info: {str(e)}"
                        )

                    # Create course with comprehensive context
                    course = Course(
                        school_id=school_id,
                        title=title,
                        duration_weeks=duration_weeks,
                        curriculum_id=curriculum_id,
                        learning_objectives=json.dumps(curriculum_context.learning_objectives),
                        key_concepts=json.dumps(curriculum_context.key_concepts),
                        skill_level=curriculum_context.skill_level,
                        themes=json.dumps(curriculum_context.themes),
                        progression_path=json.dumps(curriculum_context.progression_path),
                        teaching_approach=json.dumps(curriculum_context.teaching_approach),
                        core_competencies=json.dumps(curriculum_context.core_competencies),
                        curriculum_context_cache=json.dumps(curriculum_context.dict()),
                        last_context_update=curriculum_context.extraction_timestamp
                    )
                    db.add(course)
                    db.commit()
                    db.refresh(course)

                    # Log course creation
                    await self.emit_event("course_created", {
                        "course_id": course.id,
                        "title": course.title
                    })

                    # Generate modules using comprehensive context
                    total_modules = max(duration_weeks, 3)
                    for i in range(total_modules):
                        # Extract module-specific context
                        module_context = await self.curriculum_extractor.extract_comprehensive_context(
                            collection_name=curriculum.vector_key,
                            context_type='module',
                            parent_context_id=course.id,
                            specific_focus=f"Module {i+1} content and structure"
                        )

                        # Generate module outline
                        module_outline = await self.ai_generator.generate_module_outline(
                            curriculum_context=curriculum_context,
                            module_number=i + 1,
                            total_modules=total_modules
                        )

                        # Create module
                        m = Module(
                            course_id=course.id,
                            name=module_outline.name,
                            description=module_outline.description,
                            learning_outcomes=json.dumps(module_outline.learning_outcomes),
                            prerequisites=json.dumps(module_outline.prerequisites),
                            estimated_duration=module_outline.estimated_duration,
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

                        # Log module creation
                        await self.emit_event("module_created", {
                            "module_id": m.id,
                            "name": m.name,
                            "course_id": course.id
                        })

                else:
                    # Create course without curriculum
                    course = Course(
                        school_id=school_id,
                        title=title,
                        duration_weeks=duration_weeks
                    )
                    db.add(course)
                    db.commit()
                    db.refresh(course)

                    # Create default modules
                    for i in range(duration_weeks):
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
                    event_data={
                        "course_id": course.id,
                        "modules_data": json.dumps(modules_list)
                    }
                )

            finally:
                db.close()

        except Exception as e:
            await self.handle_error(e, "start_course")
            raise

    async def create_lessons(self, modules_event: ModulesCreatedEvent) -> LessonsCreatedEvent:
        """
        Step 2: Create lessons using hierarchical context
        """
        try:
            db = SessionLocal()
            try:
                modules_list = json.loads(modules_event.event_data["modules_data"])
                course = db.query(Course).filter(Course.id == modules_event.event_data["course_id"]).first()
                lessons_info = []

                if course and course.curriculum_id:
                    curriculum = db.query(Curriculum).filter(Curriculum.id == course.curriculum_id).first()
                    if not curriculum or not curriculum.vector_key:
                        raise HTTPException(status_code=400, detail="Invalid curriculum configuration")

                    # Load course context
                    course_context = json.loads(course.curriculum_context_cache)

                    for mod_info in modules_list:
                        module = db.query(Module).filter(Module.id == mod_info["id"]).first()
                        if not module:
                            continue

                        # Load module context
                        module_context = json.loads(module.module_context_cache)

                        # Generate lessons
                        for i in range(1, 5):
                            # Extract lesson context
                            lesson_context = await self.curriculum_extractor.extract_comprehensive_context(
                                collection_name=curriculum.vector_key,
                                context_type='lesson',
                                parent_context_id=module.id,
                                specific_focus=f"{module.name} Lesson {i}"
                            )

                            # Generate lesson content
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

                            # Create lesson
                            lesson = await self._create_lesson(
                                db, module.id, lesson_outline, content_sections, lesson_context
                            )

                            lessons_info.append({
                                "module_id": module.id,
                                "lesson_id": lesson.id,
                                "lesson_name": lesson.name,
                                "description": lesson.description
                            })

                            # Log lesson creation
                            await self.emit_event("lesson_created", {
                                "lesson_id": lesson.id,
                                "name": lesson.name,
                                "module_id": module.id
                            })

                else:
                    # Create default lessons
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
                    event_data={
                        "course_id": modules_event.event_data["course_id"],
                        "lessons_data": json.dumps(lessons_info)
                    }
                )

            finally:
                db.close()

        except Exception as e:
            await self.handle_error(e, "create_lessons")
            raise

    async def _create_lesson(self, db, module_id: int, outline, content_sections, context) -> Lesson:
        """Helper method to create a lesson with content"""
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
            module_id=module_id,
            name=outline.name,
            description=outline.description,
            content=full_content,
            key_points=json.dumps(outline.key_points),
            activities=json.dumps(outline.activities),
            resources=json.dumps(outline.resources),
            assessment_ideas=json.dumps(outline.assessment_ideas),
            examples=json.dumps(all_examples),
            exercises=json.dumps(all_exercises),
            topic_context=json.dumps(context.themes),
            lesson_context_cache=json.dumps(context.dict())
        )
        db.add(lesson)
        db.commit()
        db.refresh(lesson)
        return lesson

    async def finalize_course(self, lessons_event: LessonsCreatedEvent) -> CourseFinishedEvent:
        """
        Step 3: Finalize course creation
        """
        try:
            db = SessionLocal()
            try:
                course = db.query(Course).filter(Course.id == lessons_event.event_data["course_id"]).first()
                if course:
                    course.is_finalized = True
                    db.commit()

                    # Log course finalization
                    await self.emit_event("course_finalized", {
                        "course_id": course.id,
                        "title": course.title
                    })

                return CourseFinishedEvent(
                    event_data={
                        "course_id": course.id,
                        "result": f"Course {course.id} created successfully with comprehensive curriculum context"
                    }
                )

            finally:
                db.close()

        except Exception as e:
            await self.handle_error(e, "finalize_course")
            raise

    async def run(self, school_id: int, title: str, duration_weeks: int, curriculum_id: int = 0) -> str:
        """Run complete workflow"""
        try:
            modules_created = await self.start_course(school_id, title, duration_weeks, curriculum_id)
            lessons_created = await self.create_lessons(modules_created)
            finished = await self.finalize_course(lessons_created)
            return finished.event_data["result"]
        except Exception as e:
            await self.handle_error(e, "workflow_run")
            raise
        finally:
            await self.cleanup()
