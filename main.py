"""
FastAPI Main Application Entry Point
====================================

This is the main entry point for the FastAPI chatbot application.
It initializes the FastAPI app, loads configuration, sets up middleware,
and includes API routers.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Add app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.config import get_settings
from app.database.connection import init_database
from app.api import chat, health
from app.middleware.logging import LoggingMiddleware
from app.utils.exceptions import ChatBotException
from app.tools.tool_registry import initialize_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/app.log', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    
    This function handles:
    - Database initialization
    - Tool registration
    - Configuration validation
    - Cleanup on shutdown
    """
    logger.info("Starting up FastAPI Chatbot Application...")
    
    try:
        # Load and validate configuration
        settings = get_settings()
        logger.info(f"Loaded configuration - Environment: {settings.environment}")
        logger.info(f"Debug mode: {settings.debug}")
        logger.info(f"LLM Provider: {settings.llm.provider}")
        logger.info(f"General chat enabled: {settings.guardrails.enable_general_chat}")
        
        # Initialize database
        logger.info("Initializing database...")
        await init_database()
        logger.info("Database initialized successfully")
        
        # Initialize and register tools
        logger.info("Initializing tools...")
        tool_count = await initialize_tools()
        logger.info(f"Initialized {tool_count} tools successfully")
        
        # Create logs directory if it doesn't exist
        Path("data/logs").mkdir(parents=True, exist_ok=True)
        
        logger.info("Application startup completed successfully!")
        
        yield  # Application runs here
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise
    
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down FastAPI Chatbot Application...")
        # Add any cleanup code here if needed
        logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    
    # Load settings
    settings = get_settings()
    
    # Create FastAPI app with lifespan manager
    app = FastAPI(
        title="AI Chatbot with Tool Integration",
        description="A sophisticated chatbot with Amazon Nova/GPT OSS integration and delivery tracking tools",
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom logging middleware
    app.add_middleware(LoggingMiddleware)
    
    # Include API routers
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["health"]
    )
    
    app.include_router(
        chat.router,
        prefix="",  # No prefix to match ChatUI expectations (/chat)
        tags=["chat"]
    )
    
    # Global exception handler
    @app.exception_handler(ChatBotException)
    async def chatbot_exception_handler(request: Request, exc: ChatBotException):
        """Handle custom chatbot exceptions"""
        logger.error(f"ChatBot Exception: {exc.detail} - Path: {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "type": exc.__class__.__name__,
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        logger.error(f"Unexpected error: {str(exc)} - Path: {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error occurred",
                "type": "InternalServerError",
                "path": str(request.url.path)
            }
        )
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with basic information"""
        settings = get_settings()
        return {
            "message": "AI Chatbot API is running",
            "version": "1.0.0",
            "environment": settings.environment,
            "llm_provider": settings.llm.provider,
            "tools_enabled": settings.tools.enabled,
            "general_chat": settings.guardrails.enable_general_chat,
            "docs": "/docs" if settings.debug else "Documentation disabled in production"
        }
    
    return app


# Create the FastAPI app instance
app = create_app()


if __name__ == "__main__":
    """
    Run the application directly with uvicorn.
    This is primarily for development purposes.
    """
    
    settings = get_settings()
    
    # Configure uvicorn logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logger.info("Starting FastAPI application with uvicorn...")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_config=log_config,
        access_log=True,
    )