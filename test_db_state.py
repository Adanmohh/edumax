from sqlalchemy.orm import Session
from my_app.database import SessionLocal
from my_app.models import School, Curriculum, User

def check_db_state():
    db = SessionLocal()
    try:
        print("\nChecking database state...")
        
        # Check schools
        schools = db.query(School).all()
        print(f"\nSchools ({len(schools)}):")
        for school in schools:
            print(f"- ID: {school.id}, Name: {school.name}")
            
            # Check curricula for this school
            curricula = db.query(Curriculum).filter(Curriculum.school_id == school.id).all()
            print(f"  Curricula ({len(curricula)}):")
            for curr in curricula:
                print(f"  - ID: {curr.id}, Name: {curr.name}")
                print(f"    File: {curr.file_path}")
                print(f"    Vector Key: {curr.vector_key}")
                print(f"    Created At: {curr.created_at}")
        
        # Check users
        users = db.query(User).all()
        print(f"\nUsers ({len(users)}):")
        for user in users:
            print(f"- ID: {user.id}, Username: {user.username}, Role: {user.role}, School ID: {user.school_id}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_db_state()
