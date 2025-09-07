"""
API Module
==========

FastAPI routers for the chatbot application.
Contains endpoints for chat functionality and health monitoring.
"""

from .chat import router as chat_router
from .health import router as health_router

__all__ = [
    "chat_router",
    "health_router"
]