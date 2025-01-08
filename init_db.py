from sqlalchemy.orm import Session
from my_app.database import engine, Base, SessionLocal
from my_app.models import User

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully")
    
    db = SessionLocal()
    try:
        print("\nChecking for existing users...")
        all_users = db.query(User).all()
        print(f"Found {len(all_users)} users:")
        for user in all_users:
            print(f"- ID: {user.id}, Username: {user.username}, Role: {user.role}, Password: {user.password}")
        
        print("\nChecking for superadmin...")
        superadmin = db.query(User).filter(User.username == "superadmin").first()
        if not superadmin:
            print("Creating superadmin user...")
            superadmin = User(
                username="superadmin",
                password="admin123",
                role="superadmin",
                school_id=None
            )
            db.add(superadmin)
            db.commit()
            db.refresh(superadmin)
            print(f"Superadmin created with ID: {superadmin.id}")
        else:
            print(f"Superadmin exists with ID: {superadmin.id}")
            print(f"Current password: {superadmin.password}")
            
            # Update password if needed
            if superadmin.password != "admin123":
                print("Updating superadmin password...")
                superadmin.password = "admin123"
                db.commit()
                print("Password updated")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
