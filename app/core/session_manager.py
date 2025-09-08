"""
Session Manager
===============

Manages chat sessions, conversation history, and database operations
for persistent storage of chat data.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc, and_

from ..config import Settings
from ..database.models import ChatSession, ConversationMessage as DBMessage, ErrorLog
from ..database.schemas import ConversationMessage
from ..utils.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages chat sessions and conversation history.
    
    Responsibilities:
    - Create and manage chat sessions
    - Store and retrieve conversation history
    - Track session activity and metrics
    - Handle session cleanup and expiration
    - Manage database operations for chat data
    """
    
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        
        logger.debug("SessionManager initialized")
    
    async def get_or_create_session(self, session_id: str) -> ChatSession:
        """
        Get existing session or create a new one.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            ChatSession: Database session object
            
        Raises:
            DatabaseError: If database operation fails
        """
        
        try:
            logger.debug(f"Getting or creating session: {session_id[:16]}...")
            
            # Try to get existing session
            session = self.db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            if session:
                logger.debug(f"Found existing session: {session_id[:16]}...")
                return session
            
            # Create new session
            session = ChatSession(
                session_id=session_id,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                is_active=True,
                message_count=0,
                total_input_tokens=0,
                total_output_tokens=0
            )
            
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"Created new session: {session_id[:16]}...")
            return session
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_or_create_session: {str(e)}")
            self.db.rollback()
            raise DatabaseError(f"Failed to get or create session: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in get_or_create_session: {str(e)}")
            self.db.rollback()
            raise DatabaseError(f"Session operation failed: {str(e)}")
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get existing session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ChatSession or None if not found
        """
        
        try:
            session = self.db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            return session
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting session: {str(e)}")
            raise DatabaseError(f"Failed to get session: {str(e)}")
    
    async def save_user_message(
        self, 
        session_id: str, 
        message: str
    ) -> DBMessage:
        """
        Save user message to database.
        
        Args:
            session_id: Session identifier
            message: User message content
            
        Returns:
            DBMessage: Saved message object
        """
        
        try:
            logger.debug(f"Saving user message for session: {session_id[:16]}...")
            
            # Create message record
            db_message = DBMessage(
                session_id=session_id,
                role='user',
                content=message,
                timestamp=datetime.utcnow(),
                input_tokens=0,  # User messages don't have token counts
                output_tokens=0,
                tool_name=None
            )
            
            self.db.add(db_message)
            
            # Update session message count
            session = await self.get_session(session_id)
            if session:
                session.message_count += 1
                session.last_activity = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(db_message)
            
            logger.debug(f"User message saved for session: {session_id[:16]}...")
            return db_message
            
        except SQLAlchemyError as e:
            logger.error(f"Database error saving user message: {str(e)}")
            self.db.rollback()
            raise DatabaseError(f"Failed to save user message: {str(e)}")
    
    async def save_ai_message(
        self,
        session_id: str,
        message: str,
        input_tokens: int,
        output_tokens: int,
        tool_name: Optional[str] = None
    ) -> DBMessage:
        """
        Save AI response to database.
        
        Args:
            session_id: Session identifier
            message: AI response content
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated
            tool_name: Name of tool used if any
            
        Returns:
            DBMessage: Saved message object
        """
        
        try:
            logger.debug(f"Saving AI message for session: {session_id[:16]}...")
            
            # Create message record
            db_message = DBMessage(
                session_id=session_id,
                role='assistant',
                content=message,
                timestamp=datetime.utcnow(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_name=tool_name
            )
            
            self.db.add(db_message)
            
            # Update session totals
            session = await self.get_session(session_id)
            if session:
                session.message_count += 1
                session.total_input_tokens += input_tokens
                session.total_output_tokens += output_tokens
                session.last_activity = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(db_message)
            
            logger.debug(f"AI message saved for session: {session_id[:16]}...")
            return db_message
            
        except SQLAlchemyError as e:
            logger.error(f"Database error saving AI message: {str(e)}")
            self.db.rollback()
            raise DatabaseError(f"Failed to save AI message: {str(e)}")
    
    async def get_conversation_history(
        self, 
        session_id: str, 
        limit: Optional[int] = None
    ) -> List[ConversationMessage]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            
        Returns:
            List of ConversationMessage objects
        """
        
        try:
            logger.debug(f"Getting conversation history for session: {session_id[:16]}...")
            
            query = self.db.query(DBMessage).filter(
                DBMessage.session_id == session_id
            ).order_by(DBMessage.timestamp.asc())
            
            if limit:
                query = query.limit(limit)
            
            db_messages = query.all()
            
            # Convert to ConversationMessage objects
            conversation_messages = []
            for db_msg in db_messages:
                conv_msg = ConversationMessage(
                    role=db_msg.role,
                    content=db_msg.content,
                    timestamp=db_msg.timestamp,
                    input_tokens=db_msg.input_tokens or 0,
                    output_tokens=db_msg.output_tokens or 0,
                    tool_name=db_msg.tool_name
                )
                conversation_messages.append(conv_msg)
            
            logger.debug(f"Retrieved {len(conversation_messages)} messages for session: {session_id[:16]}...")
            return conversation_messages
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting conversation history: {str(e)}")
            raise DatabaseError(f"Failed to get conversation history: {str(e)}")
    
    async def get_message_count(self, session_id: str) -> int:
        """
        Get total message count for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Number of messages in session
        """
        
        try:
            count = self.db.query(DBMessage).filter(
                DBMessage.session_id == session_id
            ).count()
            
            return count
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting message count: {str(e)}")
            raise DatabaseError(f"Failed to get message count: {str(e)}")
    
    async def get_recent_message_count(
        self, 
        session_id: str, 
        minutes: int = 5
    ) -> int:
        """
        Get count of messages in the last N minutes.
        
        Args:
            session_id: Session identifier
            minutes: Number of minutes to look back
            
        Returns:
            Number of recent messages
        """
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
            
            count = self.db.query(DBMessage).filter(
                and_(
                    DBMessage.session_id == session_id,
                    DBMessage.timestamp >= cutoff_time
                )
            ).count()
            
            return count
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting recent message count: {str(e)}")
            raise DatabaseError(f"Failed to get recent message count: {str(e)}")
    
    async def update_session_activity(self, session_id: str) -> None:
        """
        Update session last activity timestamp.
        
        Args:
            session_id: Session identifier
        """
        
        try:
            session = await self.get_session(session_id)
            if session:
                session.last_activity = datetime.utcnow()
                self.db.commit()
                
        except SQLAlchemyError as e:
            logger.error(f"Database error updating session activity: {str(e)}")
            self.db.rollback()
            raise DatabaseError(f"Failed to update session activity: {str(e)}")
    
    async def clear_session(self, session_id: str) -> bool:
        """
        Clear a session and all its messages.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was cleared successfully
        """
        
        try:
            logger.info(f"Clearing session: {session_id[:16]}...")
            
            # Delete all messages for this session
            message_count = self.db.query(DBMessage).filter(
                DBMessage.session_id == session_id
            ).delete()
            
            # Delete the session
            session_deleted = self.db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).delete()
            
            self.db.commit()
            
            logger.info(
                f"Session cleared: {session_id[:16]}... - "
                f"Deleted {message_count} messages and {session_deleted} session records"
            )
            
            return session_deleted > 0
            
        except SQLAlchemyError as e:
            logger.error(f"Database error clearing session: {str(e)}")
            self.db.rollback()
            raise DatabaseError(f"Failed to clear session: {str(e)}")
    
    async def list_sessions(
        self, 
        limit: int = 50, 
        offset: int = 0,
        active_only: bool = True
    ) -> List[ChatSession]:
        """
        List chat sessions with pagination.
        
        Args:
            limit: Maximum number of sessions to return
            offset: Offset for pagination
            active_only: Whether to return only active sessions
            
        Returns:
            List of ChatSession objects
        """
        
        try:
            query = self.db.query(ChatSession)
            
            if active_only:
                query = query.filter(ChatSession.is_active == True)
            
            sessions = query.order_by(
                desc(ChatSession.last_activity)
            ).offset(offset).limit(limit).all()
            
            return sessions
            
        except SQLAlchemyError as e:
            logger.error(f"Database error listing sessions: {str(e)}")
            raise DatabaseError(f"Failed to list sessions: {str(e)}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall chat system statistics.
        
        Returns:
            Dictionary containing statistics
        """
        
        try:
            logger.debug("Getting chat statistics")
            
            # Session statistics
            total_sessions = self.db.query(ChatSession).count()
            active_sessions = self.db.query(ChatSession).filter(
                ChatSession.is_active == True
            ).count()
            
            # Message statistics
            total_messages = self.db.query(DBMessage).count()
            user_messages = self.db.query(DBMessage).filter(
                DBMessage.role == 'user'
            ).count()
            ai_messages = self.db.query(DBMessage).filter(
                DBMessage.role == 'assistant'
            ).count()
            
            # Token statistics
            token_stats = self.db.query(
                func.sum(ChatSession.total_input_tokens).label('total_input'),
                func.sum(ChatSession.total_output_tokens).label('total_output')
            ).first()
            
            total_input_tokens = token_stats.total_input or 0
            total_output_tokens = token_stats.total_output or 0
            
            # Tool usage statistics
            tool_messages = self.db.query(DBMessage).filter(
                DBMessage.tool_name.isnot(None)
            ).count()
            
            # Recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_sessions = self.db.query(ChatSession).filter(
                ChatSession.last_activity >= recent_cutoff
            ).count()
            
            recent_messages = self.db.query(DBMessage).filter(
                DBMessage.timestamp >= recent_cutoff
            ).count()
            
            # Average messages per session
            avg_messages_per_session = total_messages / total_sessions if total_sessions > 0 else 0
            
            return {
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'total_messages': total_messages,
                'user_messages': user_messages,
                'ai_messages': ai_messages,
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'tool_usage_count': tool_messages,
                'recent_sessions_24h': recent_sessions,
                'recent_messages_24h': recent_messages,
                'avg_messages_per_session': round(avg_messages_per_session, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting statistics: {str(e)}")
            raise DatabaseError(f"Failed to get statistics: {str(e)}")
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions based on timeout settings.
        
        Returns:
            Number of sessions cleaned up
        """
        
        try:
            logger.info("Starting expired session cleanup")
            
            # Calculate expiration time
            timeout_minutes = self.settings.guardrails.session_timeout_minutes
            expiration_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            
            # Find expired sessions
            expired_sessions = self.db.query(ChatSession).filter(
                and_(
                    ChatSession.last_activity < expiration_time,
                    ChatSession.is_active == True
                )
            ).all()
            
            cleanup_count = 0
            
            for session in expired_sessions:
                # Mark session as inactive instead of deleting
                session.is_active = False
                cleanup_count += 1
                
                logger.debug(f"Marked expired session as inactive: {session.session_id[:16]}...")
            
            self.db.commit()
            
            logger.info(f"Cleaned up {cleanup_count} expired sessions")
            return cleanup_count
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during cleanup: {str(e)}")
            self.db.rollback()
            raise DatabaseError(f"Failed to cleanup expired sessions: {str(e)}")
    
    async def log_error(
        self, 
        session_id: str, 
        error_message: str, 
        request_id: Optional[str] = None
    ) -> None:
        """
        Log error for a specific session.
        
        Args:
            session_id: Session identifier
            error_message: Error message to log
            request_id: Optional request identifier
        """
        
        try:
            error_log = ErrorLog(
                session_id=session_id,
                error_message=error_message,
                request_id=request_id,
                timestamp=datetime.utcnow()
            )
            
            self.db.add(error_log)
            self.db.commit()
            
            logger.debug(f"Error logged for session: {session_id[:16]}...")
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to log error to database: {str(e)}")
            self.db.rollback()
            # Don't raise exception here as it would mask the original error
    
    async def get_session_errors(
        self, 
        session_id: str, 
        limit: int = 10
    ) -> List[ErrorLog]:
        """
        Get error logs for a specific session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of errors to return
            
        Returns:
            List of ErrorLog objects
        """
        
        try:
            errors = self.db.query(ErrorLog).filter(
                ErrorLog.session_id == session_id
            ).order_by(
                desc(ErrorLog.timestamp)
            ).limit(limit).all()
            
            return errors
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting session errors: {str(e)}")
            raise DatabaseError(f"Failed to get session errors: {str(e)}")
    
    async def export_session_data(self, session_id: str) -> Dict[str, Any]:
        """
        Export complete session data for external use.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Complete session data dictionary
        """
        
        try:
            session = await self.get_session(session_id)
            if not session:
                raise ValidationError("Session not found")
            
            # Get conversation history
            messages = await self.get_conversation_history(session_id)
            
            # Get error logs
            errors = await self.get_session_errors(session_id)
            
            # Format data
            export_data = {
                'session_info': {
                    'session_id': session.session_id,
                    'created_at': session.created_at.isoformat(),
                    'last_activity': session.last_activity.isoformat() if session.last_activity else None,
                    'is_active': session.is_active,
                    'message_count': session.message_count,
                    'total_input_tokens': session.total_input_tokens,
                    'total_output_tokens': session.total_output_tokens
                },
                'messages': [
                    {
                        'role': msg.role,
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat(),
                        'input_tokens': msg.input_tokens,
                        'output_tokens': msg.output_tokens,
                        'tool_name': msg.tool_name
                    }
                    for msg in messages
                ],
                'errors': [
                    {
                        'error_message': error.error_message,
                        'request_id': error.request_id,
                        'timestamp': error.timestamp.isoformat()
                    }
                    for error in errors
                ],
                'export_timestamp': datetime.utcnow().isoformat()
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting session data: {str(e)}")
            raise DatabaseError(f"Failed to export session data: {str(e)}")