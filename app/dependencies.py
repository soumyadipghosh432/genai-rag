"""
FastAPI Dependencies
===================

Common dependencies for FastAPI routes including database sessions,
configuration, logging, and business logic components.
"""

import logging
import uuid
from typing import Generator, Optional
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings, Settings
from .database.connection import get_db
from .core.session_manager import SessionManager
from .core.chat_manager import ChatManager
from .llm.llm_factory import LLMFactory
from .tools.tool_registry import ToolRegistry
from .utils.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)


# Configuration dependency
def get_app_settings() -> Settings:
    """
    Get application settings.
    
    Returns:
        Settings: Application configuration
    """
    return get_settings()


# Database dependency
def get_database_session() -> Generator[Session, None, None]:
    """
    Get database session with automatic cleanup.
    
    Yields:
        Session: SQLAlchemy database session
        
    Raises:
        DatabaseError: If database connection fails
    """
    try:
        db = next(get_db())
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database connection error: {str(e)}")
        raise DatabaseError(f"Database connection failed: {str(e)}")
    finally:
        if 'db' in locals():
            db.close()


# Request ID dependency
def get_request_id(request: Request) -> str:
    """
    Generate or get request ID for tracking.
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: Unique request identifier
    """
    if not hasattr(request.state, "request_id"):
        request.state.request_id = str(uuid.uuid4())
    return request.state.request_id


# Session Manager dependency
def get_session_manager(
    db: Session = Depends(get_database_session),
    settings: Settings = Depends(get_app_settings)
) -> SessionManager:
    """
    Get session manager instance.
    
    Args:
        db: Database session
        settings: Application settings
        
    Returns:
        SessionManager: Session management instance
    """
    return SessionManager(db=db, settings=settings)


# LLM Factory dependency
def get_llm_factory(
    settings: Settings = Depends(get_app_settings)
) -> LLMFactory:
    """
    Get LLM factory instance.
    
    Args:
        settings: Application settings
        
    Returns:
        LLMFactory: LLM factory instance
    """
    return LLMFactory(settings=settings)


# Tool Registry dependency  
def get_tool_registry() -> ToolRegistry:
    """
    Get tool registry instance.
    
    Returns:
        ToolRegistry: Tool registry instance
    """
    return ToolRegistry.get_instance()


# Chat Manager dependency
def get_chat_manager(
    session_manager: SessionManager = Depends(get_session_manager),
    llm_factory: LLMFactory = Depends(get_llm_factory),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    settings: Settings = Depends(get_app_settings),
    request_id: str = Depends(get_request_id)
) -> ChatManager:
    """
    Get chat manager instance with all dependencies.
    
    Args:
        session_manager: Session management instance
        llm_factory: LLM factory instance
        tool_registry: Tool registry instance
        settings: Application settings
        request_id: Request identifier
        
    Returns:
        ChatManager: Chat management instance
    """
    return ChatManager(
        session_manager=session_manager,
        llm_factory=llm_factory,
        tool_registry=tool_registry,
        settings=settings,
        request_id=request_id
    )


# Request validation dependencies
def validate_session_id(session_id: str) -> str:
    """
    Validate session ID format.
    
    Args:
        session_id: Session identifier to validate
        
    Returns:
        str: Validated session ID
        
    Raises:
        ValidationError: If session ID is invalid
    """
    if not session_id or not isinstance(session_id, str):
        raise ValidationError("Session ID is required and must be a string")
    
    if len(session_id) < 10 or len(session_id) > 100:
        raise ValidationError("Session ID must be between 10 and 100 characters")
    
    # Basic format validation (alphanumeric and common separators)
    import re
    if not re.match(r'^[a-zA-Z0-9\-_]+$', session_id):
        raise ValidationError("Session ID contains invalid characters")
    
    return session_id


def validate_message_content(message: str, settings: Settings = Depends(get_app_settings)) -> str:
    """
    Validate message content.
    
    Args:
        message: Message content to validate
        settings: Application settings
        
    Returns:
        str: Validated message content
        
    Raises:
        ValidationError: If message is invalid
    """
    if not message or not isinstance(message, str):
        raise ValidationError("Message is required and must be a string")
    
    message = message.strip()
    
    if not message:
        raise ValidationError("Message cannot be empty")
    
    if len(message) > settings.guardrails.max_input_length:
        raise ValidationError(f"Message too long. Maximum length is {settings.guardrails.max_input_length} characters")
    
    return message


# Session timeout validation
def validate_session_timeout(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    settings: Settings = Depends(get_app_settings)
) -> bool:
    """
    Check if session has timed out.
    
    Args:
        session_id: Session identifier
        session_manager: Session manager instance
        settings: Application settings
        
    Returns:
        bool: True if session is valid, False if timed out
        
    Raises:
        HTTPException: If session has timed out
    """
    try:
        session_data = session_manager.get_session(session_id)
        
        if not session_data:
            # New session, no timeout
            return True
        
        # Check last activity
        if session_data.last_activity:
            timeout_threshold = datetime.utcnow() - timedelta(
                minutes=settings.guardrails.session_timeout_minutes
            )
            
            if session_data.last_activity < timeout_threshold:
                logger.info(f"Session {session_id} timed out")
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail="Session has timed out. Please start a new conversation."
                )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating session timeout: {str(e)}")
        # Don't block on timeout validation errors
        return True


# Rate limiting dependency
def check_rate_limit(
    request: Request,
    session_id: str = Depends(validate_session_id),
    session_manager: SessionManager = Depends(get_session_manager)
) -> bool:
    """
    Basic rate limiting check.
    
    Args:
        request: FastAPI request object
        session_id: Session identifier
        session_manager: Session manager instance
        
    Returns:
        bool: True if request is allowed
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    try:
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # For now, implement basic session-based rate limiting
        # In production, consider Redis-based rate limiting
        
        session_data = session_manager.get_session(session_id)
        if session_data:
            # Check message count in the last minute
            recent_messages = session_manager.get_recent_message_count(
                session_id, 
                minutes=1
            )
            
            if recent_messages > 10:  # Max 10 messages per minute
                logger.warning(f"Rate limit exceeded for session {session_id} from IP {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please wait before sending more messages."
                )
        
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in rate limit check: {str(e)}")
        # Don't block on rate limiting errors
        return True


# Health check dependencies
def check_database_health(
    db: Session = Depends(get_database_session)
) -> dict:
    """
    Check database health status.
    
    Args:
        db: Database session
        
    Returns:
        dict: Database health information
    """
    try:
        # Simple query to test database connectivity
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "message": "Database connection successful",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


def check_llm_health(
    llm_factory: LLMFactory = Depends(get_llm_factory)
) -> dict:
    """
    Check LLM service health status.
    
    Args:
        llm_factory: LLM factory instance
        
    Returns:
        dict: LLM health information
    """
    try:
        llm = llm_factory.get_llm()
        # You could add a simple test call here
        return {
            "status": "healthy",
            "message": f"LLM provider ({llm.provider}) is available",
            "provider": llm.provider,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"LLM health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"LLM service error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


def check_tools_health(
    tool_registry: ToolRegistry = Depends(get_tool_registry)
) -> dict:
    """
    Check tools health status.
    
    Args:
        tool_registry: Tool registry instance
        
    Returns:
        dict: Tools health information
    """
    try:
        available_tools = tool_registry.list_tools()
        return {
            "status": "healthy",
            "message": f"Tools system operational",
            "available_tools": len(available_tools),
            "tools": list(available_tools.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Tools health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"Tools system error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


# Logging dependency
def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get logger instance for a specific module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)


# Security dependencies
def verify_api_key(request: Request, settings: Settings = Depends(get_app_settings)) -> bool:
    """
    Verify API key if required (for future use).
    
    Args:
        request: FastAPI request object
        settings: Application settings
        
    Returns:
        bool: True if API key is valid or not required
    """
    # For now, no API key required
    # This is a placeholder for future security implementation
    return True


# Content filtering dependency
def filter_content(
    message: str,
    settings: Settings = Depends(get_app_settings)
) -> str:
    """
    Apply content filtering to user messages.
    
    Args:
        message: User message to filter
        settings: Application settings
        
    Returns:
        str: Filtered message
        
    Raises:
        ValidationError: If content is not allowed
    """
    if not settings.guardrails.content_filter_enabled:
        return message
    
    # Basic content filtering
    # In production, integrate with AWS Content Moderation or similar
    
    # Check for common inappropriate patterns
    prohibited_patterns = [
        # Add patterns as needed
        r'\b(?:spam|test)\b',  # Example patterns
    ]
    
    import re
    for pattern in prohibited_patterns:
        if re.search(pattern, message.lower()):
            logger.warning(f"Content filter triggered for message: {message[:50]}...")
            raise ValidationError("Message contains prohibited content")
    
    return message


# Conversation length validation
def validate_conversation_length(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    settings: Settings = Depends(get_app_settings)
) -> bool:
    """
    Validate conversation length doesn't exceed limits.
    
    Args:
        session_id: Session identifier
        session_manager: Session manager instance
        settings: Application settings
        
    Returns:
        bool: True if conversation length is acceptable
        
    Raises:
        ValidationError: If conversation is too long
    """
    try:
        message_count = session_manager.get_message_count(session_id)
        
        if message_count >= settings.guardrails.max_conversation_length:
            raise ValidationError(
                f"Conversation too long. Maximum {settings.guardrails.max_conversation_length} messages allowed. "
                "Please start a new conversation."
            )
        
        return True
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error validating conversation length: {str(e)}")
        # Don't block on validation errors
        return True


# Cache dependencies (for future use)
class CacheManager:
    """Simple cache manager for dependency injection"""
    
    def __init__(self):
        self._cache = {}
    
    def get(self, key: str) -> Optional[any]:
        """Get value from cache"""
        item = self._cache.get(key)
        if item and item['expires'] > datetime.utcnow():
            return item['value']
        elif item:
            del self._cache[key]  # Remove expired item
        return None
    
    def set(self, key: str, value: any, ttl: int = 300) -> None:
        """Set value in cache with TTL"""
        # Simple in-memory cache - in production use Redis
        self._cache[key] = {
            'value': value,
            'expires': datetime.utcnow() + timedelta(seconds=ttl)
        }
    
    def clear_expired(self):
        """Clear expired cache entries"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, data in self._cache.items()
            if data['expires'] < now
        ]
        for key in expired_keys:
            del self._cache[key]


# Global cache instance
_cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """
    Get cache manager instance.
    
    Returns:
        CacheManager: Cache manager instance
    """
    return _cache_manager


# Combined validation dependency
def validate_chat_request(
    session_id: str,
    message: str,
    request: Request,
    settings: Settings = Depends(get_app_settings),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Combined validation for chat requests.
    
    Args:
        session_id: Session identifier
        message: User message
        request: FastAPI request object
        settings: Application settings
        session_manager: Session manager instance
        
    Returns:
        tuple: (validated_session_id, validated_message)
    """
    # Validate session ID
    valid_session_id = validate_session_id(session_id)
    
    # Validate message content
    valid_message = validate_message_content(message, settings)
    
    # Apply content filtering
    filtered_message = filter_content(valid_message, settings)
    
    # Check session timeout
    validate_session_timeout(valid_session_id, session_manager, settings)
    
    # Check conversation length
    validate_conversation_length(valid_session_id, session_manager, settings)
    
    # Check rate limits
    check_rate_limit(request, valid_session_id, session_manager)
    
    return valid_session_id, filtered_message