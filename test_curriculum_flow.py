import os
import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from main import app
from my_app.database import get_db, Base, engine
from my_app.models import School, User, Curriculum

# Test client setup
client = TestClient(app)

# Test data
TEST_SCHOOL = {
    "name": "Test School"
}

TEST_USER = {
    "username": "testteacher",
    "password": "testpass",
    "role": "teacher"
}

@pytest.fixture(scope="function")
def db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Get database session
    session = Session(engine)
    
    try:
        # Create test school
        school = School(**TEST_SCHOOL)
        session.add(school)
        session.commit()
        session.refresh(school)
        
        # Create test user
        user = User(**TEST_USER, school_id=school.id)
        session.add(user)
        session.commit()
        session.refresh(user)
        
        yield session
    finally:
        session.close()
        # Clean up tables
        Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_curriculum_flow(db):
    """Test the complete curriculum flow from upload through ingestion"""
    
    # 1. First authenticate
    auth_response = client.post("/auth/login", json={
        "username": TEST_USER["username"],
        "password": TEST_USER["password"]
    })
    assert auth_response.status_code == 200
    auth_data = auth_response.json()
    assert "token" in auth_data, f"Expected 'token' in response, got: {auth_data}"
    session_token = auth_data["token"]
    
    # Get test school
    school = db.query(School).filter(School.name == TEST_SCHOOL["name"]).first()
    assert school is not None
    
    # 2. Upload curriculum
    test_file_path = "my_app/uploaded_files/VOTA - hyvien väestösuhteiden suunnittelutyökalu (1).pdf"
    with open(test_file_path, "rb") as f:
        upload_response = client.post(
            "/curriculum/upload",
            files={"file": ("test.pdf", f, "application/pdf")},
            data={
                "name": "Test Curriculum",
                "school_id": str(school.id),
                "token": session_token
            }
        )
    assert upload_response.status_code == 200
    curriculum_id = upload_response.json()["curriculum_id"]
    
    # 3. Verify curriculum was created with empty vector_key
    curriculum = db.query(Curriculum).filter(Curriculum.id == curriculum_id).first()
    assert curriculum is not None
    assert curriculum.vector_key == ""
    
    # 4. Trigger ingestion
    collection_name = f"test_collection_{curriculum_id}"
    ingest_response = client.post(
        "/curriculum/ingest",
        json={
            "curriculum_id": curriculum_id,
            "collection_name": collection_name,
            "token": session_token
        }
    )
    assert ingest_response.status_code == 200
    
    # 5. Verify vector_key was updated
    db.refresh(curriculum)
    assert curriculum.vector_key == collection_name
    
    # 6. Verify curriculum list shows processed status
    list_response = client.get(f"/curriculum?token={session_token}&school_id={school.id}")
    assert list_response.status_code == 200
    curricula = list_response.json()["curricula"]
    
    # Find our curriculum in the list
    test_curriculum = next(
        (c for c in curricula if c["id"] == curriculum_id),
        None
    )
    assert test_curriculum is not None
    assert test_curriculum["has_embeddings"] == True
    assert test_curriculum["vector_key"] == collection_name

if __name__ == "__main__":
    asyncio.run(test_curriculum_flow(next(get_db())))
