from .auth import router as auth_router
from .schools import router as schools_router
from .curriculum import router as curriculum_router
from .courses import router as courses_router

__all__ = ['auth_router', 'schools_router', 'curriculum_router', 'courses_router']
