"""
FastAPI Chatbot Application Package
==================================

This package contains the core FastAPI chatbot application with:
- LLM integration (Amazon Nova, GPT OSS)
- Tool calling system
- Session management
- Database operations
- Chat guardrails

Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "FastAPI Chatbot Team"
__email__ = "chatbot@example.com"

# Package-level imports for easy access
from .config import get_settings, Settings
from .main import create_app

__all__ = [
    "get_settings",
    "Settings", 
    "create_app",
    "__version__",
]