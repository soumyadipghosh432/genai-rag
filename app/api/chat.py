"""
Chat API Endpoints
==================

FastAPI endpoints for chat functionality including message processing,
session management, and tool integration.
"""

import logging
import time
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..core.chat_manager import ChatManager
from ..dependencies import (
    get_chat_manager,
    validate_chat_request,
    get_request_id,
    get_app_settings
)
from ..database.schemas import ChatRequest, ChatResponse
from ..config import Settings
from ..utils.exceptions import ChatBotException, ValidationError, LLMError, ToolError

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequestModel(BaseModel):
    """Chat request model for API endpoint"""
    session_id: str = Field(..., description="Unique session identifier", min_length=10, max_length=100)
    message: str = Field(..., description="User message", min_length=1, max_length=2000)
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "user_12345_session_67890",
                "message": "Hello, can you help me track my delivery?"
            }
        }


class ChatResponseModel(BaseModel):
    """Chat response model for API endpoint"""
    response: str = Field(..., description="AI assistant response")
    input_tokens: int = Field(..., description="Number of input tokens used")
    output_tokens: int = Field(..., description="Number of output tokens generated")
    response_time_seconds: float = Field(..., description="Time taken to generate response")
    session_id: str = Field(..., description="Session identifier")
    request_id: str = Field(..., description="Unique request identifier")
    tool_called: bool = Field(default=False, description="Whether a tool was called")
    tool_name: str = Field(default=None, description="Name of the tool that was called")
    
    class Config:
        schema_extra = {
            "example": {
                "response": "I can help you track your delivery. Please provide your delivery number.",
                "input_tokens": 25,
                "output_tokens": 18,
                "response_time_seconds": 1.23,
                "session_id": "user_12345_session_67890",
                "request_id": "req_abcd1234",
                "tool_called": False,
                "tool_name": None
            }
        }


@router.post(
    "/chat",
    response_model=ChatResponseModel,
    summary="Process chat message",
    description="Process a user message and return AI assistant response with token counts",
    responses={
        200: {"description": "Successful response with AI message"},
        400: {"description": "Invalid request data"},
        408: {"description": "Request timeout or session expired"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
async def chat_endpoint(
    chat_request: ChatRequestModel,
    request: Request,
    chat_manager: ChatManager = Depends(get_chat_manager),
    request_id: str = Depends(get_request_id),
    settings: Settings = Depends(get_app_settings)
) -> ChatResponseModel:
    """
    Process chat message and return AI response.
    
    This endpoint:
    1. Validates the request and applies content filtering
    2. Manages session state and conversation history
    3. Detects tool requirements and executes tools if needed
    4. Generates AI response using the configured LLM
    5. Applies guardrails based on configuration
    6. Returns response with token counts and timing
    """
    
    start_time = time.time()
    
    try:
        logger.info(f"Processing chat request - Session: {chat_request.session_id[:16]}... Request: {request_id}")
        
        # Validate request (includes rate limiting, content filtering, etc.)
        validated_session_id, validated_message = validate_chat_request(
            chat_request.session_id,
            chat_request.message,
            request,
            settings
        )
        
        logger.debug(f"Request validated for session {validated_session_id[:16]}...")
        
        # Create internal chat request
        internal_request = ChatRequest(
            session_id=validated_session_id,
            message=validated_message
        )
        
        # Process chat message through chat manager
        chat_response = await chat_manager.process_message(internal_request)
        
        # Calculate response time
        response_time = time.time() - start_time
        
        logger.info(
            f"Chat processed successfully - Session: {validated_session_id[:16]}... "
            f"Response time: {response_time:.2f}s, "
            f"Input tokens: {chat_response.input_tokens}, "
            f"Output tokens: {chat_response.output_tokens}, "
            f"Tool called: {chat_response.tool_called}"
        )
        
        # Return formatted response
        return ChatResponseModel(
            response=chat_response.response,
            input_tokens=chat_response.input_tokens,
            output_tokens=chat_response.output_tokens,
            response_time_seconds=round(response_time, 3),
            session_id=validated_session_id,
            request_id=request_id,
            tool_called=chat_response.tool_called,
            tool_name=chat_response.tool_name
        )
        
    except ValidationError as e:
        logger.warning(f"Validation error for session {chat_request.session_id[:16]}...: {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.detail
        )
    
    except LLMError as e:
        logger.error(f"LLM error for session {chat_request.session_id[:16]}...: {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service temporarily unavailable. Please try again."
        )
    
    except ToolError as e:
        logger.error(f"Tool error for session {chat_request.session_id[:16]}...: {e.detail}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to process tool request. Please try again or rephrase your request."
        )
    
    except ChatBotException as e:
        logger.error(f"ChatBot error for session {chat_request.session_id[:16]}...: {e.detail}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (from dependencies)
        raise
    
    except Exception as e:
        logger.error(
            f"Unexpected error processing chat request - Session: {chat_request.session_id[:16]}... "
            f"Request: {request_id} - Error: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your message."
        )


@router.get(
    "/chat/session/{session_id}",
    summary="Get session information",
    description="Retrieve information about a chat session",
    responses={
        200: {"description": "Session information"},
        404: {"description": "Session not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_session_info(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager),
    request_id: str = Depends(get_request_id)
) -> Dict[str, Any]:
    """Get information about a chat session"""
    
    try:
        logger.info(f"Getting session info - Session: {session_id[:16]}... Request: {request_id}")
        
        session_info = await chat_manager.get_session_info(session_id)
        
        if not session_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return session_info
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error getting session info - Session: {session_id[:16]}... Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve session information"
        )


@router.delete(
    "/chat/session/{session_id}",
    summary="Clear session",
    description="Clear/reset a chat session and its history",
    responses={
        200: {"description": "Session cleared successfully"},
        404: {"description": "Session not found"},
        500: {"description": "Internal server error"}
    }
)
async def clear_session(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager),
    request_id: str = Depends(get_request_id)
) -> Dict[str, str]:
    """Clear a chat session and its history"""
    
    try:
        logger.info(f"Clearing session - Session: {session_id[:16]}... Request: {request_id}")
        
        success = await chat_manager.clear_session(session_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or could not be cleared"
            )
        
        logger.info(f"Session cleared successfully - Session: {session_id[:16]}...")
        
        return {
            "message": "Session cleared successfully",
            "session_id": session_id,
            "request_id": request_id
        }
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error clearing session - Session: {session_id[:16]}... Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to clear session"
        )


@router.get(
    "/chat/sessions",
    summary="List active sessions",
    description="Get list of active chat sessions (admin endpoint)",
    responses={
        200: {"description": "List of active sessions"},
        500: {"description": "Internal server error"}
    }
)
async def list_sessions(
    chat_manager: ChatManager = Depends(get_chat_manager),
    request_id: str = Depends(get_request_id),
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Get list of active sessions (for admin/monitoring)"""
    
    try:
        logger.info(f"Listing sessions - Request: {request_id} - Limit: {limit}, Offset: {offset}")
        
        sessions = await chat_manager.list_sessions(limit=limit, offset=offset)
        
        return {
            "sessions": sessions,
            "total": len(sessions),
            "limit": limit,
            "offset": offset,
            "request_id": request_id
        }
        
    except Exception as e:
        logger.error(f"Error listing sessions - Request: {request_id} - Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to list sessions"
        )


@router.get(
    "/chat/stats",
    summary="Get chat statistics",
    description="Get overall chat system statistics",
    responses={
        200: {"description": "Chat statistics"},
        500: {"description": "Internal server error"}
    }
)
async def get_chat_stats(
    chat_manager: ChatManager = Depends(get_chat_manager),
    request_id: str = Depends(get_request_id)
) -> Dict[str, Any]:
    """Get chat system statistics"""
    
    try:
        logger.info(f"Getting chat stats - Request: {request_id}")
        
        stats = await chat_manager.get_stats()
        
        return {
            **stats,
            "request_id": request_id,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error getting chat stats - Request: {request_id} - Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve chat statistics"
        )