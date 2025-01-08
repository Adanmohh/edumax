from sqlalchemy.orm import Session
from my_app.database import engine, Base, SessionLocal
from my_app.models import User, Curriculum, School, Course, Module, Lesson, Assessment
from my_app.config import BASE_DIR
from datetime import datetime
import os

def init_db():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Tables dropped successfully")
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully")
    
    db = SessionLocal()
    try:
        print("\nCreating school...")
        school = School(
            name="Demo School"
        )
        db.add(school)
        db.commit()
        print(f"Created school with ID: {school.id}")
        
        print("\nCreating users...")
        
        # Create admin user (connected to school)
        admin = User(
            username="admin",
            password="admin123",
            role="superadmin",
            school_id=school.id  # Connect to Demo School
        )
        db.add(admin)
        
        # Create teacher user (connected to school)
        teacher = User(
            username="teacher",
            password="teacher123",
            role="teacher",
            school_id=school.id  # Connect to Demo School
        )
        db.add(teacher)
        
        # Create superadmin user (system-wide)
        superadmin = User(
            username="superadmin",
            password="admin123",
            role="superadmin",
            school_id=None  # System-wide user
        )
        db.add(superadmin)
        
        db.commit()
        
        # Print created users
        all_users = db.query(User).all()
        print(f"Created {len(all_users)} users:")
        for user in all_users:
            print(f"- ID: {user.id}, Username: {user.username}, Role: {user.role}, Password: {user.password}")
        
        print("\nRecreating curriculum entries...")
        
        # List of curriculum files to restore
        curricula = [
            {
                "file_name": "KPI-Plan-for-Baano-Call-Centre.pdf",
                "name": "KPI Plan for Baano Call Centre",
                "location": os.path.join(BASE_DIR, "uploaded_files")
            },
            {
                "file_name": "OPEX – Tehtävien ja työnhallinnan järjestelmä.pdf",
                "name": "OPEX - Tehtävien ja työnhallinnan järjestelmä",
                "location": os.path.join(os.path.dirname(BASE_DIR), "uploaded_files")
            },
            {
                "file_name": "VOTA - hyvien väestösuhteiden suunnittelutyökalu (1).pdf",
                "name": "VOTA - Hyvien väestösuhteiden suunnittelutyökalu",
                "location": os.path.join(os.path.dirname(BASE_DIR), "uploaded_files")
            }
        ]
        
        for curriculum_info in curricula:
            file_path = os.path.join(curriculum_info["location"], curriculum_info["file_name"])
            
            if os.path.exists(file_path):
                try:
                    print(f"\nCreating curriculum for {curriculum_info['file_name']}")
                    curriculum = Curriculum(
                        name=curriculum_info["name"],
                        file_path=file_path,
                        vector_key="",  # This will be set when embeddings are generated
                        school_id=school.id,  # Associate with the created school
                        created_at=datetime.utcnow()
                    )
                    db.add(curriculum)
                    db.commit()
                    db.refresh(curriculum)
                    print(f"Created curriculum entry: {curriculum.__dict__}")
                except Exception as e:
                    print(f"Error creating curriculum: {str(e)}")
                    import traceback
                    print(f"Traceback: {traceback.format_exc()}")
                    raise
            else:
                print(f"Warning: Could not find file {curriculum_info['file_name']}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
