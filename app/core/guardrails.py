"""
Guardrails Manager
==================

Manages chat guardrails including content filtering, conversation limits,
and behavioral restrictions based on configuration settings.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta

from ..config import Settings
from ..database.schemas import ConversationMessage
from ..utils.exceptions import ValidationError, GuardrailsViolation

logger = logging.getLogger(__name__)


class GuardrailsManager:
    """
    Manages chat guardrails and content filtering.
    
    Responsibilities:
    - Enforce general chat restrictions
    - Apply content filtering
    - Monitor conversation limits
    - Validate user and AI messages
    - Track violations and patterns
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Content filtering patterns
        self.inappropriate_patterns = [
            r'\b(?:spam|test|abuse|harmful)\b',
            r'\b(?:hack|exploit|bypass)\b',
            r'\b(?:illegal|fraud|scam)\b'
        ]
        
        # Off-topic patterns (when general chat is disabled)
        self.off_topic_patterns = [
            r'\b(?:weather|sports|politics|entertainment)\b',
            r'\b(?:recipe|cooking|travel|music)\b',
            r'\b(?:joke|story|poem|creative)\b',
            r'\b(?:personal|relationship|advice)\b'
        ]
        
        # Tool-related keywords that should be allowed
        self.tool_keywords = [
            r'\b(?:delivery|tracking|shipment|package)\b',
            r'\b(?:order|track|status|update)\b',
            r'\b(?:help|assist|support|service)\b'
        ]
        
        # Sensitive information patterns
        self.sensitive_patterns = [
            r'\b(?:\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b',  # Credit card
            r'\b(?:\d{3}[-\s]?\d{2}[-\s]?\d{4})\b',             # SSN
            r'\b(?:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'  # Email (basic)
        ]
        
        # Violation tracking
        self.violation_history: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.debug("GuardrailsManager initialized")
    
    async def validate_user_message(
        self, 
        message: str, 
        session_id: str, 
        conversation_history: List[ConversationMessage]
    ) -> str:
        """
        Validate user message against all guardrails.
        
        Args:
            message: User message to validate
            session_id: Session identifier
            conversation_history: Previous conversation
            
        Returns:
            Validated (possibly modified) message
            
        Raises:
            ValidationError: If message violates guardrails
        """
        
        try:
            logger.debug(f"Validating user message for session {session_id[:16]}...")
            
            # Check message length
            self._check_message_length(message)
            
            # Check for inappropriate content
            self._check_inappropriate_content(message, session_id)
            
            # Check for sensitive information
            self._check_sensitive_information(message, session_id)
            
            # Check general chat restrictions
            if not self.settings.guardrails.enable_general_chat:
                self._check_tool_relevance(message, conversation_history, session_id)
            
            # Check conversation limits
            self._check_conversation_limits(conversation_history, session_id)
            
            # Check for repetitive patterns
            self._check_repetitive_patterns(message, conversation_history, session_id)
            
            # Check rate limiting patterns
            self._check_rate_limiting_patterns(message, session_id)
            
            logger.debug(f"User message validation passed for session {session_id[:16]}...")
            return message
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating user message: {str(e)}")
            raise ValidationError(f"Message validation failed: {str(e)}")
    
    async def validate_ai_response(
        self, 
        response: str, 
        user_message: str, 
        session_id: str
    ) -> str:
        """
        Validate AI response for appropriateness and policy compliance.
        
        Args:
            response: AI response to validate
            user_message: Original user message
            session_id: Session identifier
            
        Returns:
            Validated (possibly modified) AI response
        """
        
        try:
            logger.debug(f"Validating AI response for session {session_id[:16]}...")
            
            # Check response length
            if len(response) > 5000:  # Reasonable limit for AI responses
                logger.warning(f"AI response too long ({len(response)} chars), truncating")
                response = response[:4800] + "... [Response truncated for length]"
            
            # Check for inappropriate AI content
            self._check_ai_inappropriate_content(response, session_id)
            
            # Ensure AI doesn't reveal sensitive system information
            self._check_system_information_leakage(response, session_id)
            
            # Check if response addresses user's query appropriately
            self._check_response_relevance(response, user_message, session_id)
            
            logger.debug(f"AI response validation passed for session {session_id[:16]}...")
            return response
            
        except Exception as e:
            logger.error(f"Error validating AI response: {str(e)}")
            # Don't block AI responses unless critical
            return response
    
    def _check_message_length(self, message: str) -> None:
        """Check if message length is within limits"""
        
        max_length = self.settings.guardrails.max_input_length
        
        if len(message) > max_length:
            raise ValidationError(
                f"Message too long. Maximum {max_length} characters allowed."
            )
        
        if len(message.strip()) == 0:
            raise ValidationError("Message cannot be empty.")
    
    def _check_inappropriate_content(self, message: str, session_id: str) -> None:
        """Check for inappropriate content patterns"""
        
        if not self.settings.guardrails.content_filter_enabled:
            return
        
        message_lower = message.lower()
        
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, message_lower):
                violation = {
                    'type': 'inappropriate_content',
                    'pattern': pattern,
                    'timestamp': datetime.utcnow(),
                    'message_excerpt': message[:50] + "..." if len(message) > 50 else message
                }
                
                self._record_violation(session_id, violation)
                
                logger.warning(f"Inappropriate content detected in session {session_id[:16]}...")
                raise ValidationError(
                    "Your message contains inappropriate content. Please rephrase your request."
                )
    
    def _check_sensitive_information(self, message: str, session_id: str) -> None:
        """Check for sensitive information in user messages"""
        
        for pattern in self.sensitive_patterns:
            matches = re.findall(pattern, message)
            if matches:
                violation = {
                    'type': 'sensitive_information',
                    'pattern': pattern,
                    'timestamp': datetime.utcnow(),
                    'matches_count': len(matches)
                }
                
                self._record_violation(session_id, violation)
                
                logger.warning(f"Sensitive information detected in session {session_id[:16]}...")
                raise ValidationError(
                    "Please don't share sensitive information like credit card numbers, "
                    "social security numbers, or email addresses. I can help you without this information."
                )
    
    def _check_tool_relevance(
        self, 
        message: str, 
        conversation_history: List[ConversationMessage], 
        session_id: str
    ) -> None:
        """Check if message is relevant to available tools when general chat is disabled"""
        
        message_lower = message.lower()
        
        # Check if message contains tool-related keywords
        tool_relevant = any(
            re.search(pattern, message_lower) 
            for pattern in self.tool_keywords
        )
        
        # Allow greetings and basic courtesy
        courtesy_patterns = [
            r'\b(?:hello|hi|hey|thanks|thank you|please|help)\b',
            r'\b(?:good morning|good afternoon|good evening)\b'
        ]
        
        is_courtesy = any(
            re.search(pattern, message_lower)
            for pattern in courtesy_patterns
        )
        
        # Check if it's a follow-up to a tool-related conversation
        recent_tool_context = self._has_recent_tool_context(conversation_history)
        
        if not (tool_relevant or is_courtesy or recent_tool_context):
            # Check if it's clearly off-topic
            off_topic = any(
                re.search(pattern, message_lower)
                for pattern in self.off_topic_patterns
            )
            
            if off_topic or len(message.split()) > 3:  # Longer messages are more likely off-topic
                violation = {
                    'type': 'off_topic',
                    'timestamp': datetime.utcnow(),
                    'message_excerpt': message[:50] + "..." if len(message) > 50 else message
                }
                
                self._record_violation(session_id, violation)
                
                logger.info(f"Off-topic message blocked in session {session_id[:16]}...")
                raise ValidationError(
                    "I can only help with delivery tracking and related services. "
                    "Please ask about tracking a delivery or shipment status."
                )
    
    def _check_conversation_limits(
        self, 
        conversation_history: List[ConversationMessage], 
        session_id: str
    ) -> None:
        """Check conversation length and time limits"""
        
        # Check message count
        max_messages = self.settings.guardrails.max_conversation_length
        current_count = len(conversation_history)
        
        if current_count >= max_messages:
            logger.info(f"Conversation limit reached for session {session_id[:16]}...")
            raise ValidationError(
                f"Conversation limit of {max_messages} messages reached. "
                "Please start a new conversation to continue."
            )
        
        # Check session age
        if conversation_history:
            session_start = conversation_history[0].timestamp
            session_age = datetime.utcnow() - session_start
            max_age = timedelta(minutes=self.settings.guardrails.session_timeout_minutes)
            
            if session_age > max_age:
                logger.info(f"Session timeout for session {session_id[:16]}...")
                raise ValidationError(
                    "Your session has expired due to inactivity. "
                    "Please start a new conversation."
                )
    
    def _check_repetitive_patterns(
        self, 
        message: str, 
        conversation_history: List[ConversationMessage], 
        session_id: str
    ) -> None:
        """Check for repetitive or spam-like patterns"""
        
        if len(conversation_history) < 2:
            return
        
        # Get recent user messages
        recent_user_messages = [
            msg.content for msg in conversation_history[-5:]
            if msg.role == 'user'
        ]
        
        # Check for exact duplicates
        duplicate_count = recent_user_messages.count(message)
        if duplicate_count >= 2:
            violation = {
                'type': 'repetitive_message',
                'timestamp': datetime.utcnow(),
                'duplicate_count': duplicate_count
            }
            
            self._record_violation(session_id, violation)
            
            logger.warning(f"Repetitive message detected in session {session_id[:16]}...")
            raise ValidationError(
                "Please don't repeat the same message. If you need help, "
                "try rephrasing your request or ask a different question."
            )
        
        # Check for very similar messages
        similar_count = sum(
            1 for recent_msg in recent_user_messages
            if self._calculate_similarity(message, recent_msg) > 0.8
        )
        
        if similar_count >= 3:
            logger.warning(f"Similar messages detected in session {session_id[:16]}...")
            raise ValidationError(
                "Your recent messages are very similar. Please try a different approach "
                "or ask a new question if you need additional help."
            )
    
    def _check_rate_limiting_patterns(self, message: str, session_id: str) -> None:
        """Check for patterns that might indicate automated/bot behavior"""
        
        # Check for very short messages repeatedly
        if len(message.strip()) <= 2:
            recent_violations = self._get_recent_violations(session_id, 'short_message', minutes=5)
            if len(recent_violations) >= 3:
                logger.warning(f"Short message pattern detected in session {session_id[:16]}...")
                raise ValidationError(
                    "Please provide more detailed messages to help me assist you better."
                )
            
            violation = {
                'type': 'short_message',
                'timestamp': datetime.utcnow(),
                'message_length': len(message)
            }
            self._record_violation(session_id, violation)
    
    def _check_ai_inappropriate_content(self, response: str, session_id: str) -> None:
        """Check AI response for inappropriate content"""
        
        # Patterns that AI shouldn't include
        ai_inappropriate_patterns = [
            r'I cannot|I can\'t|I don\'t know',  # Too many negative responses
            r'error|failed|broken',              # Technical errors exposed
            r'admin|system|debug|internal'       # System information
        ]
        
        response_lower = response.lower()
        negative_pattern_count = 0
        
        for pattern in ai_inappropriate_patterns:
            if re.search(pattern, response_lower):
                negative_pattern_count += 1
        
        # If too many negative patterns, log but don't block
        if negative_pattern_count > 2:
            logger.warning(f"AI response has multiple negative patterns in session {session_id[:16]}...")
    
    def _check_system_information_leakage(self, response: str, session_id: str) -> None:
        """Check if AI response leaks system information"""
        
        system_info_patterns = [
            r'database|sql|query',
            r'server|host|port|endpoint',
            r'api key|token|secret|password',
            r'config|configuration|settings',
            r'internal|backend|infrastructure'
        ]
        
        response_lower = response.lower()
        
        for pattern in system_info_patterns:
            if re.search(pattern, response_lower):
                logger.warning(f"Potential system info leak in AI response for session {session_id[:16]}...")
                # In production, you might want to scrub this content
                break
    
    def _check_response_relevance(self, response: str, user_message: str, session_id: str) -> None:
        """Check if AI response is relevant to user's query"""
        
        # Basic relevance check - ensure response isn't completely generic
        generic_responses = [
            "I understand", "That's interesting", "I see", "Okay", "Alright"
        ]
        
        if response.strip() in generic_responses:
            logger.warning(f"Generic AI response detected in session {session_id[:16]}...")
    
    def _has_recent_tool_context(self, conversation_history: List[ConversationMessage]) -> bool:
        """Check if recent conversation involved tool usage"""
        
        recent_messages = conversation_history[-6:]  # Last 6 messages
        
        for message in recent_messages:
            if message.role == 'assistant':
                message_lower = message.content.lower()
                tool_indicators = [
                    'delivery', 'tracking', 'shipment', 'package',
                    'status', 'update', 'track', 'order'
                ]
                
                if any(indicator in message_lower for indicator in tool_indicators):
                    return True
        
        return False
    
    def _calculate_similarity(self, msg1: str, msg2: str) -> float:
        """Calculate similarity between two messages (simple implementation)"""
        
        if msg1 == msg2:
            return 1.0
        
        # Simple word-based similarity
        words1 = set(msg1.lower().split())
        words2 = set(msg2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _record_violation(self, session_id: str, violation: Dict[str, Any]) -> None:
        """Record a guardrail violation for tracking"""
        
        if session_id not in self.violation_history:
            self.violation_history[session_id] = []
        
        self.violation_history[session_id].append(violation)
        
        # Keep only recent violations (last 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.violation_history[session_id] = [
            v for v in self.violation_history[session_id]
            if v['timestamp'] > cutoff_time
        ]
        
        logger.debug(f"Recorded violation for session {session_id[:16]}...: {violation['type']}")
    
    def _get_recent_violations(self, session_id: str, violation_type: str, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get recent violations of a specific type"""
        
        if session_id not in self.violation_history:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        return [
            v for v in self.violation_history[session_id]
            if v['type'] == violation_type and v['timestamp'] > cutoff_time
        ]
    
    def get_session_violations(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all violations for a session"""
        return self.violation_history.get(session_id, [])
    
    def clear_session_violations(self, session_id: str) -> None:
        """Clear violations for a session"""
        if session_id in self.violation_history:
            del self.violation_history[session_id]
    
    def get_violation_summary(self) -> Dict[str, Any]:
        """Get summary of all violations across sessions"""
        
        total_violations = 0
        violation_types = {}
        active_sessions = 0
        
        for session_id, violations in self.violation_history.items():
            if violations:
                active_sessions += 1
                total_violations += len(violations)
                
                for violation in violations:
                    violation_type = violation['type']
                    violation_types[violation_type] = violation_types.get(violation_type, 0) + 1
        
        return {
            'total_violations': total_violations,
            'violation_types': violation_types,
            'sessions_with_violations': active_sessions,
            'most_common_violation': max(violation_types.items(), key=lambda x: x[1])[0] if violation_types else None
        }