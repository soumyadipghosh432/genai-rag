"""
Conversation Flow Manager
========================

Manages conversation state, flow control, and context tracking
for maintaining coherent multi-turn conversations.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum

from ..config import Settings
from ..database.schemas import ConversationMessage
from ..utils.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """Conversation state enumeration"""
    INITIAL = "initial"
    ONGOING = "ongoing" 
    WAITING_FOR_INPUT = "waiting_for_input"
    TOOL_EXECUTION = "tool_execution"
    COMPLETED = "completed"
    ERROR = "error"


class InputType(Enum):
    """Types of input the system might be waiting for"""
    DELIVERY_NUMBER = "delivery_number"
    CONFIRMATION = "confirmation"
    CLARIFICATION = "clarification"
    CHOICE = "choice"
    GENERAL = "general"


class ConversationFlowManager:
    """
    Manages conversation flow and state tracking.
    
    Responsibilities:
    - Track conversation state and context
    - Identify when waiting for specific inputs
    - Manage multi-turn interactions
    - Handle conversation completion and reset
    - Analyze conversation patterns
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Patterns for detecting different types of responses
        self.waiting_patterns = {
            InputType.DELIVERY_NUMBER: [
                r'delivery\s*number',
                r'tracking\s*number',
                r'package\s*id',
                r'shipment\s*id',
                r'order\s*number'
            ],
            InputType.CONFIRMATION: [
                r'confirm',
                r'yes\s*or\s*no',
                r'proceed',
                r'continue'
            ],
            InputType.CLARIFICATION: [
                r'clarify',
                r'specify',
                r'more\s*details',
                r'which\s*one'
            ],
            InputType.CHOICE: [
                r'choose',
                r'select',
                r'option',
                r'preference'
            ]
        }
        
        # Positive/negative response patterns
        self.positive_responses = [
            r'\byes\b', r'\byep\b', r'\byeah\b', r'\bsure\b', 
            r'\bok\b', r'\bokay\b', r'\bconfirm\b', r'\bproceed\b',
            r'\bcorrect\b', r'\bright\b', r'\bagree\b'
        ]
        
        self.negative_responses = [
            r'\bno\b', r'\bnope\b', r'\bcancel\b', r'\bstop\b',
            r'\bwrong\b', r'\bincorrect\b', r'\bdisagree\b'
        ]
        
        # Delivery number patterns
        self.delivery_number_patterns = [
            r'\b[A-Z]{2}\d{8,12}\b',  # Standard tracking format
            r'\b\d{10,15}\b',         # Numeric tracking
            r'\b[A-Z0-9]{8,20}\b'     # Alphanumeric tracking
        ]
        
        logger.debug("ConversationFlowManager initialized")
    
    def analyze_conversation_state(
        self, 
        conversation_history: List[ConversationMessage], 
        current_message: str
    ) -> Dict[str, Any]:
        """
        Analyze current conversation state and flow.
        
        Args:
            conversation_history: Previous messages in conversation
            current_message: Current user message
            
        Returns:
            Dictionary containing flow state information
        """
        
        try:
            if not conversation_history:
                return self._create_flow_state(ConversationState.INITIAL)
            
            # Get last AI message to understand context
            last_ai_message = self._get_last_ai_message(conversation_history)
            
            if not last_ai_message:
                return self._create_flow_state(ConversationState.INITIAL)
            
            # Analyze what the AI was asking for
            waiting_for = self._analyze_ai_request(last_ai_message.content)
            
            if waiting_for:
                # Check if user provided the requested information
                provided_info = self._analyze_user_response(current_message, waiting_for)
                
                if provided_info['has_requested_info']:
                    return self._create_flow_state(
                        ConversationState.ONGOING,
                        provided_info=provided_info,
                        previous_request=waiting_for
                    )
                else:
                    return self._create_flow_state(
                        ConversationState.WAITING_FOR_INPUT,
                        waiting_for=waiting_for,
                        attempts=self._count_request_attempts(conversation_history, waiting_for)
                    )
            
            # Check if conversation should be completed
            if self._should_complete_conversation(conversation_history, current_message):
                return self._create_flow_state(ConversationState.COMPLETED)
            
            return self._create_flow_state(ConversationState.ONGOING)
            
        except Exception as e:
            logger.error(f"Error analyzing conversation state: {str(e)}")
            return self._create_flow_state(ConversationState.ERROR, error=str(e))
    
    def _create_flow_state(
        self, 
        state: ConversationState, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a flow state dictionary.
        
        Args:
            state: Current conversation state
            **kwargs: Additional state information
            
        Returns:
            Flow state dictionary
        """
        
        flow_state = {
            'state': state.value,
            'timestamp': datetime.utcnow().isoformat(),
            'awaiting_input': state == ConversationState.WAITING_FOR_INPUT,
            **kwargs
        }
        
        logger.debug(f"Created flow state: {flow_state}")
        return flow_state
    
    def _get_last_ai_message(self, conversation_history: List[ConversationMessage]) -> Optional[ConversationMessage]:
        """
        Get the last AI message from conversation history.
        
        Args:
            conversation_history: List of conversation messages
            
        Returns:
            Last AI message or None
        """
        
        for message in reversed(conversation_history):
            if message.role == 'assistant':
                return message
        return None
    
    def _analyze_ai_request(self, ai_message: str) -> Optional[Dict[str, Any]]:
        """
        Analyze AI message to determine what information it's requesting.
        
        Args:
            ai_message: AI assistant's message
            
        Returns:
            Information about what the AI is requesting or None
        """
        
        ai_message_lower = ai_message.lower()
        
        for input_type, patterns in self.waiting_patterns.items():
            for pattern in patterns:
                if re.search(pattern, ai_message_lower):
                    return {
                        'type': input_type.value,
                        'description': self._get_input_description(input_type),
                        'patterns': patterns,
                        'urgent': self._is_urgent_request(ai_message_lower),
                        'alternatives': self._get_input_alternatives(input_type)
                    }
        
        # Check for question marks indicating a question
        if '?' in ai_message:
            return {
                'type': InputType.GENERAL.value,
                'description': 'General information or clarification',
                'patterns': [r'\?'],
                'urgent': False,
                'alternatives': []
            }
        
        return None
    
    def _analyze_user_response(self, user_message: str, waiting_for: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze user response to see if it contains requested information.
        
        Args:
            user_message: User's message
            waiting_for: Information about what was requested
            
        Returns:
            Analysis of user response
        """
        
        input_type = InputType(waiting_for['type'])
        user_message_lower = user_message.lower()
        
        result = {
            'has_requested_info': False,
            'extracted_info': None,
            'confidence': 0.0,
            'response_type': None
        }
        
        if input_type == InputType.DELIVERY_NUMBER:
            delivery_numbers = self._extract_delivery_numbers(user_message)
            if delivery_numbers:
                result.update({
                    'has_requested_info': True,
                    'extracted_info': delivery_numbers[0],  # Take first found
                    'confidence': 0.9,
                    'response_type': 'delivery_number'
                })
        
        elif input_type == InputType.CONFIRMATION:
            if self._is_positive_response(user_message_lower):
                result.update({
                    'has_requested_info': True,
                    'extracted_info': 'yes',
                    'confidence': 0.8,
                    'response_type': 'confirmation_positive'
                })
            elif self._is_negative_response(user_message_lower):
                result.update({
                    'has_requested_info': True,
                    'extracted_info': 'no',
                    'confidence': 0.8,
                    'response_type': 'confirmation_negative'
                })
        
        elif input_type == InputType.CLARIFICATION:
            # Any substantive response counts as clarification
            if len(user_message.strip()) > 5:
                result.update({
                    'has_requested_info': True,
                    'extracted_info': user_message.strip(),
                    'confidence': 0.6,
                    'response_type': 'clarification'
                })
        
        elif input_type == InputType.CHOICE:
            # Look for choice indicators
            choice = self._extract_choice(user_message_lower)
            if choice:
                result.update({
                    'has_requested_info': True,
                    'extracted_info': choice,
                    'confidence': 0.7,
                    'response_type': 'choice'
                })
        
        elif input_type == InputType.GENERAL:
            # Any response counts for general questions
            if len(user_message.strip()) > 0:
                result.update({
                    'has_requested_info': True,
                    'extracted_info': user_message.strip(),
                    'confidence': 0.5,
                    'response_type': 'general'
                })
        
        logger.debug(f"User response analysis: {result}")
        return result
    
    def _extract_delivery_numbers(self, text: str) -> List[str]:
        """
        Extract potential delivery numbers from text.
        
        Args:
            text: Input text
            
        Returns:
            List of potential delivery numbers
        """
        
        delivery_numbers = []
        
        for pattern in self.delivery_number_patterns:
            matches = re.findall(pattern, text.upper())
            delivery_numbers.extend(matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_numbers = []
        for num in delivery_numbers:
            if num not in seen:
                seen.add(num)
                unique_numbers.append(num)
        
        return unique_numbers
    
    def _is_positive_response(self, text: str) -> bool:
        """Check if text contains positive response"""
        return any(re.search(pattern, text) for pattern in self.positive_responses)
    
    def _is_negative_response(self, text: str) -> bool:
        """Check if text contains negative response"""
        return any(re.search(pattern, text) for pattern in self.negative_responses)
    
    def _extract_choice(self, text: str) -> Optional[str]:
        """
        Extract choice from user message.
        
        Args:
            text: User message text
            
        Returns:
            Extracted choice or None
        """
        
        # Look for numbered choices
        number_match = re.search(r'\b([1-9])\b', text)
        if number_match:
            return f"option_{number_match.group(1)}"
        
        # Look for lettered choices
        letter_match = re.search(r'\b([a-e])\b', text)
        if letter_match:
            return f"option_{letter_match.group(1)}"
        
        # Look for first/second/etc
        ordinal_patterns = {
            r'\bfirst\b': 'option_1',
            r'\bsecond\b': 'option_2',
            r'\bthird\b': 'option_3',
            r'\bfourth\b': 'option_4',
            r'\bfifth\b': 'option_5'
        }
        
        for pattern, choice in ordinal_patterns.items():
            if re.search(pattern, text):
                return choice
        
        return None
    
    def _count_request_attempts(self, conversation_history: List[ConversationMessage], waiting_for: Dict[str, Any]) -> int:
        """
        Count how many times the AI has asked for the same information.
        
        Args:
            conversation_history: Conversation history
            waiting_for: Information being requested
            
        Returns:
            Number of attempts
        """
        
        attempts = 0
        input_type = waiting_for['type']
        patterns = waiting_for.get('patterns', [])
        
        for message in reversed(conversation_history):
            if message.role == 'assistant':
                message_lower = message.content.lower()
                
                # Check if this message contains the same request
                pattern_matches = any(
                    re.search(pattern, message_lower) 
                    for pattern in patterns
                )
                
                if pattern_matches:
                    attempts += 1
                else:
                    # Stop counting if we hit a different type of message
                    break
        
        return attempts
    
    def _should_complete_conversation(self, conversation_history: List[ConversationMessage], current_message: str) -> bool:
        """
        Determine if conversation should be marked as completed.
        
        Args:
            conversation_history: Conversation history
            current_message: Current user message
            
        Returns:
            True if conversation should be completed
        """
        
        completion_indicators = [
            r'\bthank\s*you\b',
            r'\bthanks\b',
            r'\bgoodbye\b',
            r'\bbye\b',
            r'\bdone\b',
            r'\bfinished\b',
            r'\bno\s*more\s*questions\b',
            r'\bthat\'s\s*all\b'
        ]
        
        message_lower = current_message.lower()
        
        for pattern in completion_indicators:
            if re.search(pattern, message_lower):
                return True
        
        # Check conversation length
        if len(conversation_history) >= self.settings.guardrails.max_conversation_length:
            return True
        
        return False
    
    def _get_input_description(self, input_type: InputType) -> str:
        """Get human-readable description of input type"""
        
        descriptions = {
            InputType.DELIVERY_NUMBER: "delivery or tracking number",
            InputType.CONFIRMATION: "confirmation (yes/no)",
            InputType.CLARIFICATION: "clarification or additional details",
            InputType.CHOICE: "selection from available options",
            InputType.GENERAL: "general information"
        }
        
        return descriptions.get(input_type, "information")
    
    def _get_input_alternatives(self, input_type: InputType) -> List[str]:
        """Get alternative ways to provide the requested input"""
        
        alternatives = {
            InputType.DELIVERY_NUMBER: [
                "tracking number",
                "package ID",
                "shipment number",
                "order number"
            ],
            InputType.CONFIRMATION: [
                "yes",
                "no",
                "confirm",
                "cancel"
            ],
            InputType.CLARIFICATION: [
                "provide more details",
                "specify what you mean",
                "explain further"
            ],
            InputType.CHOICE: [
                "select option number",
                "choose by letter",
                "say 'first', 'second', etc."
            ]
        }
        
        return alternatives.get(input_type, [])
    
    def _is_urgent_request(self, ai_message: str) -> bool:
        """
        Determine if the AI request is urgent (multiple attempts, etc.)
        
        Args:
            ai_message: AI message text
            
        Returns:
            True if request should be considered urgent
        """
        
        urgent_indicators = [
            r'please\s*provide',
            r'need\s*to\s*know',
            r'required',
            r'must\s*have',
            r'important'
        ]
        
        return any(re.search(pattern, ai_message) for pattern in urgent_indicators)
    
    def get_conversation_summary(self, conversation_history: List[ConversationMessage]) -> Dict[str, Any]:
        """
        Generate a summary of the conversation.
        
        Args:
            conversation_history: Full conversation history
            
        Returns:
            Conversation summary
        """
        
        if not conversation_history:
            return {
                'total_messages': 0,
                'user_messages': 0,
                'ai_messages': 0,
                'tools_used': [],
                'duration_minutes': 0,
                'status': 'empty'
            }
        
        user_messages = [msg for msg in conversation_history if msg.role == 'user']
        ai_messages = [msg for msg in conversation_history if msg.role == 'assistant']
        
        # Calculate duration
        if len(conversation_history) > 1:
            start_time = conversation_history[0].timestamp
            end_time = conversation_history[-1].timestamp
            duration = (end_time - start_time).total_seconds() / 60
        else:
            duration = 0
        
        # Extract tools used
        tools_used = []
        for msg in ai_messages:
            # This would be enhanced to actually track tool usage
            if 'delivery' in msg.content.lower() and 'tracked' in msg.content.lower():
                tools_used.append('delivery_tracker')
        
        return {
            'total_messages': len(conversation_history),
            'user_messages': len(user_messages),
            'ai_messages': len(ai_messages),
            'tools_used': list(set(tools_used)),
            'duration_minutes': round(duration, 2),
            'status': self._determine_conversation_status(conversation_history)
        }
    
    def _determine_conversation_status(self, conversation_history: List[ConversationMessage]) -> str:
        """
        Determine the overall status of the conversation.
        
        Args:
            conversation_history: Conversation history
            
        Returns:
            Status string
        """
        
        if not conversation_history:
            return 'empty'
        
        last_message = conversation_history[-1]
        
        if last_message.role == 'user':
            if self._should_complete_conversation(conversation_history, last_message.content):
                return 'completed_by_user'
            else:
                return 'awaiting_response'
        else:
            # Last message was from AI
            if self._analyze_ai_request(last_message.content):
                return 'awaiting_user_input'
            else:
                return 'conversation_ongoing'