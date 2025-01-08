# my_app/main.py
import os
from fastapi import FastAPI
from my_app.database import Base, engine
from my_app.routes import auth, schools, curriculum, courses

def create_app():
    app = FastAPI(title="Modular Workflow App (Courses + Curriculum)")

    Base.metadata.create_all(bind=engine)

    # Include routers
    app.include_router(auth.router, prefix="/auth", tags=["Auth"])
    app.include_router(schools.router, tags=["Schools"])
    app.include_router(curriculum.router, tags=["Curriculum"])
    app.include_router(courses.router, tags=["CourseWorkflow"])

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
