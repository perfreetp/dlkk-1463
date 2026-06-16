from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine
from .api import api_router
from .core.exceptions import BusinessException
from .core.logger import logger
from .services import SchedulerService
from .models import User


def create_tables():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    create_tables()
    
    if settings.ENABLE_SCHEDULER:
        logger.info("Starting scheduler...")
        scheduler_service = SchedulerService.get_instance()
        scheduler_service.start()
        app.state.scheduler = scheduler_service
        logger.info("Scheduler started successfully")
    
    yield
    
    if settings.ENABLE_SCHEDULER and hasattr(app.state, 'scheduler'):
        logger.info("Shutting down scheduler...")
        app.state.scheduler.shutdown()
        logger.info("Scheduler shutdown successfully")
    
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    logger.warning(f"Business exception: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后重试",
            "data": None,
        },
    )


@app.get("/", tags=["系统"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if settings.APP_DEBUG else None,
    }


@app.get("/health", tags=["系统"])
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
    }


@app.get("/api/health", tags=["系统"])
async def api_health_check():
    return {"status": "healthy"}


app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.APP_DEBUG,
        log_level="info" if settings.APP_DEBUG else "warning",
    )
