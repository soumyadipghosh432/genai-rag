"""
FastAPI Application Factory
===========================

Factory function for creating FastAPI application instances
with all necessary configuration and middleware.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .middleware.cors import get_cors_config
from .middleware.logging import LoggingMiddleware
from .utils.exceptions import ChatBotException, ValidationError, LLMError, ToolError, DatabaseError
from .api import chat, health

logger = logging.getLogger(__name__)


def create_app(config_override: Optional[dict] = None) -> FastAPI:
    """
    Create and configure FastAPI application instance.
    
    Args:
        config_override: Optional configuration overrides for testing
        
    Returns:
        FastAPI: Configured application instance
    """
    
    settings = get_settings()
    
    # Override settings if provided (for testing)
    if config_override:
        for key, value in config_override.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.app_title,
        description=settings.app_description,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # Add CORS middleware
    cors_config = get_cors_config(settings)
    app.add_middleware(
        CORSMiddleware,
        **cors_config
    )
    
    # Add custom middleware
    app.add_middleware(LoggingMiddleware)
    
    # Configure exception handlers
    configure_exception_handlers(app)
    
    # Include routers
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["health"]
    )
    
    app.include_router(
        chat.router,
        prefix="",
        tags=["chat"]
    )
    
    # Add root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information"""
        return {
            "message": "AI Chatbot API",
            "version": settings.app_version,
            "environment": settings.environment,
            "llm_provider": settings.llm.provider,
            "tools_enabled": settings.tools.enabled,
            "general_chat_enabled": settings.guardrails.enable_general_chat,
            "debug_mode": settings.debug,
            "documentation": "/docs" if settings.debug else "disabled"
        }
    
    return app


def configure_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers for the application"""
    
    @app.exception_handler(ChatBotException)
    async def chatbot_exception_handler(request: Request, exc: ChatBotException):
        """Handle custom chatbot exceptions"""
        logger.error(f"ChatBot Exception: {exc.detail} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_type": exc.__class__.__name__,
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "request_id": getattr(request.state, "request_id", None)
            }
        )
    
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        """Handle validation errors"""
        logger.warning(f"Validation Error: {exc.detail} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_type": "ValidationError",
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "request_id": getattr(request.state, "request_id", None)
            }
        )
    
    @app.exception_handler(LLMError)
    async def llm_exception_handler(request: Request, exc: LLMError):
        """Handle LLM-related errors"""
        logger.error(f"LLM Error: {exc.detail} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "An error occurred while processing your request with the AI model",
                "error_type": "LLMError", 
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "request_id": getattr(request.state, "request_id", None)
            }
        )
    
    @app.exception_handler(ToolError)
    async def tool_exception_handler(request: Request, exc: ToolError):
        """Handle tool execution errors"""
        logger.error(f"Tool Error: {exc.detail} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "An error occurred while executing the requested tool",
                "error_type": "ToolError",
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "request_id": getattr(request.state, "request_id", None)
            }
        )
    
    @app.exception_handler(DatabaseError)
    async def database_exception_handler(request: Request, exc: DatabaseError):
        """Handle database errors"""
        logger.error(f"Database Error: {exc.detail} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "A database error occurred",
                "error_type": "DatabaseError",
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "request_id": getattr(request.state, "request_id", None)
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle FastAPI HTTP exceptions"""
        logger.warning(f"HTTP Exception: {exc.detail} - Status: {exc.status_code} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_type": "HTTPException",
                "error_code": f"HTTP_{exc.status_code}",
                "path": str(request.url.path),
                "request_id": getattr(request.state, "request_id", None)
            }
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        logger.error(f"Unexpected Error: {str(exc)} - Path: {request.url.path}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "An unexpected error occurred",
                "error_type": "InternalServerError",
                "error_code": "INTERNAL_ERROR",
                "path": str(request.url.path),
                "request_id": getattr(request.state, "request_id", None)
            }
        )