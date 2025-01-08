# my_app/main.py
import os
import sys
from fastapi import FastAPI
from my_app.database import Base, engine
from my_app.routes import (
    auth_router, schools_router, curriculum_router, courses_router,
    enhanced_courses
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Create FastAPI app
app = FastAPI(
    title="Modular Workflow App (Courses + Curriculum)",
    debug=True,
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    print(f"HTTP exception: {exc.detail}", file=sys.stderr)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.detail),
            "type": "HTTPException",
            "status_code": exc.status_code
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation error: {exc.errors()}", file=sys.stderr)
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "type": "RequestValidationError",
            "details": exc.errors()
        }
    )

@app.middleware("http")
async def catch_exceptions_middleware(request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        print(f"Middleware caught exception: {str(e)}", file=sys.stderr)
        print(f"Exception type: {type(e)}", file=sys.stderr)
        traceback_str = traceback.format_exc()
        print(f"Traceback: {traceback_str}", file=sys.stderr)
        
        # Return error details in response
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "type": str(type(e)),
                "traceback": traceback_str,
                "request_path": request.url.path,
                "request_method": request.method,
                "request_query_params": str(request.query_params)
            }
        )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Global exception handler caught: {str(exc)}")
    print(f"Exception type: {type(exc)}")
    traceback_str = traceback.format_exc()
    print(f"Traceback: {traceback_str}")
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "type": str(type(exc)),
            "traceback": traceback_str
        }
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(auth_router, prefix="/auth")
app.include_router(schools_router)
app.include_router(curriculum_router)
app.include_router(courses_router)
app.include_router(enhanced_courses.router, tags=["Enhanced Courses"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
