import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json

from .main import app
from .database import get_db, Base, engine
from .models import User, Course, Module, Lesson, Curriculum
from .workflows.enhanced_course_workflow import EnhancedCourseCreationWorkflow

# Setup test database
Base.metadata.create_all(bind=engine)
client = TestClient(app)

def get_test_db():
    try:
        db = Session(bind=engine)
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = get_test_db

@pytest.fixture
def test_db():
    db = Session(bind=engine)
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def test_user(test_db):
    user = User(
        email="test@example.com",
        hashed_password="testpass",
        role="superadmin",
        school_id=1
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user

@pytest.fixture
def test_curriculum(test_db):
    curriculum = Curriculum(
        title="Test Curriculum",
        description="Test Description",
        school_id=1,
        vector_key="test_vector_key"
    )
    test_db.add(curriculum)
    test_db.commit()
    test_db.refresh(curriculum)
    return curriculum

@pytest.fixture
def test_course(test_db, test_curriculum):
    course = Course(
        title="Test Course",
        school_id=1,
        duration_weeks=4,
        curriculum_id=test_curriculum.id
    )
    test_db.add(course)
    test_db.commit()
    test_db.refresh(course)
    return course

def test_create_course_v2(test_db, test_user, test_curriculum):
    """Test enhanced course creation endpoint"""
    response = client.post(
        "/v2/courses/create",
        json={
            "school_id": 1,
            "title": "Test Course",
            "duration_weeks": 4,
            "curriculum_id": test_curriculum.id,
            "session_token": test_user.session_token
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "course_id" in data
    assert "modules" in data
    assert "status" in data
    assert data["status"] == "processing"

def test_get_course_progress(test_db, test_user, test_course):
    """Test course progress endpoint"""
    response = client.get(
        f"/v2/courses/{test_course.id}/progress",
        params={"session_token": test_user.session_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "course_id" in data
    assert "status" in data
    assert data["course_id"] == test_course.id

def test_get_course_v2(test_db, test_user, test_course):
    """Test enhanced course details endpoint"""
    # Create test module
    module = Module(
        course_id=test_course.id,
        name="Test Module",
        description="Test Description",
        learning_outcomes=json.dumps(["outcome1", "outcome2"]),
        prerequisites=json.dumps(["prereq1", "prereq2"]),
        estimated_duration="2 weeks"
    )
    test_db.add(module)
    test_db.commit()

    # Create test lesson
    lesson = Lesson(
        module_id=module.id,
        name="Test Lesson",
        description="Test Description",
        content="Test Content",
        key_points=json.dumps(["point1", "point2"]),
        activities=json.dumps(["activity1", "activity2"])
    )
    test_db.add(lesson)
    test_db.commit()

    response = client.get(
        f"/v2/courses/{test_course.id}",
        params={"session_token": test_user.session_token}
    )
    assert response.status_code == 200
    data = response.json()
    
    # Verify course data
    assert data["id"] == test_course.id
    assert data["title"] == test_course.title
    assert data["duration_weeks"] == test_course.duration_weeks
    
    # Verify module data
    assert len(data["modules"]) == 1
    module_data = data["modules"][0]
    assert module_data["name"] == "Test Module"
    assert module_data["description"] == "Test Description"
    assert module_data["learning_outcomes"] == ["outcome1", "outcome2"]
    assert module_data["prerequisites"] == ["prereq1", "prereq2"]
    
    # Verify lesson data
    assert len(module_data["lessons"]) == 1
    lesson_data = module_data["lessons"][0]
    assert lesson_data["name"] == "Test Lesson"
    assert lesson_data["description"] == "Test Description"
    assert lesson_data["content"] == "Test Content"
    assert lesson_data["key_points"] == ["point1", "point2"]
    assert lesson_data["activities"] == ["activity1", "activity2"]

def test_unauthorized_access(test_db):
    """Test unauthorized access to endpoints"""
    response = client.post(
        "/v2/courses/create",
        json={
            "school_id": 1,
            "title": "Test Course",
            "duration_weeks": 4,
            "curriculum_id": 1,
            "session_token": "invalid_token"
        }
    )
    assert response.status_code == 401

def test_course_not_found(test_db, test_user):
    """Test course not found error"""
    response = client.get(
        "/v2/courses/999/progress",
        params={"session_token": test_user.session_token}
    )
    assert response.status_code == 404

def test_invalid_curriculum(test_db, test_user):
    """Test creating course with invalid curriculum"""
    response = client.post(
        "/v2/courses/create",
        json={
            "school_id": 1,
            "title": "Test Course",
            "duration_weeks": 4,
            "curriculum_id": 999,  # Non-existent curriculum
            "session_token": test_user.session_token
        }
    )
    assert response.status_code == 404
