"""
Tool Detector
=============

Analyzes user messages to detect when tools should be called and
extracts relevant parameters for tool execution.
"""

import logging
import re
from typing import Dict, Any, List, Optional, NamedTuple
from datetime import datetime

from ..config import Settings
from ..database.schemas import ConversationMessage
from ..tools.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolDetectionResult(NamedTuple):
    """Result of tool detection analysis"""
    tool_required: bool
    tool_name: Optional[str]
    confidence: float
    required_parameters: List[str]
    extracted_parameters: Dict[str, Any]
    reasoning: str


class ToolDetector:
    """
    Detects when tools should be called based on user messages.
    
    Responsibilities:
    - Analyze user messages for tool requirements
    - Extract parameters from messages
    - Determine confidence levels
    - Handle context from conversation history
    - Support multiple tool types
    """
    
    def __init__(self, tool_registry: ToolRegistry, settings: Settings):
        self.tool_registry = tool_registry
        self.settings = settings
        
        # Delivery tracking patterns
        self.delivery_patterns = {
            'intent_keywords': [
                r'\b(?:track|tracking|trace|status|check)\b',
                r'\b(?:delivery|shipment|package|order)\b',
                r'\b(?:where\s+is|locate|find)\b',
                r'\b(?:update|progress|arrival)\b'
            ],
            'delivery_number_patterns': [
                r'\b([A-Z]{2}\d{8,15})\b',           # Standard format: AB1234567890
                r'\b(\d{10,20})\b',                  # Pure numeric
                r'\b([A-Z0-9]{8,25})\b',             # Mixed alphanumeric
                r'\b([A-Z]{1,3}\d{6,15}[A-Z]{0,3})\b' # Complex format
            ],
            'urgency_indicators': [
                r'\b(?:urgent|asap|immediately|quickly)\b',
                r'\b(?:late|delayed|overdue)\b',
                r'\b(?:when|what time|arrival time)\b'
            ]
        }
        
        # Context keywords that increase confidence
        self.context_keywords = {
            'delivery_tracking': [
                'shipped', 'sent', 'dispatched', 'courier', 'postal',
                'fedex', 'ups', 'dhl', 'usps', 'amazon',
                'expected', 'estimated', 'arrive', 'delivery date'
            ]
        }
        
        # Parameter extraction patterns
        self.parameter_patterns = {
            'delivery_number': [
                r'(?:tracking|delivery|order|shipment)?\s*(?:number|id|code)?\s*:?\s*([A-Z0-9\-]{6,25})',
                r'(?:track|trace)\s+([A-Z0-9\-]{6,25})',
                r'([A-Z0-9\-]{6,25})'  # Fallback pattern
            ]
        }
        
        logger.debug("ToolDetector initialized")
    
    async def analyze_message(
        self, 
        user_message: str, 
        conversation_history: List[ConversationMessage]
    ) -> ToolDetectionResult:
        """
        Analyze user message to detect tool requirements.
        
        Args:
            user_message: Current user message
            conversation_history: Previous conversation context
            
        Returns:
            ToolDetectionResult with detection analysis
        """
        
        try:
            logger.debug("Analyzing message for tool requirements")
            
            # Check if tools are enabled
            if not self.settings.tools.enabled:
                return ToolDetectionResult(
                    tool_required=False,
                    tool_name=None,
                    confidence=0.0,
                    required_parameters=[],
                    extracted_parameters={},
                    reasoning="Tools are disabled in configuration"
                )
            
            # Analyze for delivery tracking
            delivery_result = await self._analyze_delivery_tracking(
                user_message, conversation_history
            )
            
            if delivery_result.tool_required:
                return delivery_result
            
            # Future: Add more tool detection logic here
            # e.g., order_status_result = await self._analyze_order_status(...)
            
            return ToolDetectionResult(
                tool_required=False,
                tool_name=None,
                confidence=0.0,
                required_parameters=[],
                extracted_parameters={},
                reasoning="No tool requirements detected in message"
            )
            
        except Exception as e:
            logger.error(f"Error analyzing message for tools: {str(e)}")
            return ToolDetectionResult(
                tool_required=False,
                tool_name=None,
                confidence=0.0,
                required_parameters=[],
                extracted_parameters={},
                reasoning=f"Error during analysis: {str(e)}"
            )
    
    async def _analyze_delivery_tracking(
        self, 
        user_message: str, 
        conversation_history: List[ConversationMessage]
    ) -> ToolDetectionResult:
        """
        Analyze message for delivery tracking requirements.
        
        Args:
            user_message: User message to analyze
            conversation_history: Conversation context
            
        Returns:
            ToolDetectionResult for delivery tracking
        """
        
        if not self.settings.tools.delivery_tracker_enabled:
            return ToolDetectionResult(
                tool_required=False,
                tool_name=None,
                confidence=0.0,
                required_parameters=[],
                extracted_parameters={},
                reasoning="Delivery tracker tool is disabled"
            )
        
        message_lower = user_message.lower()
        confidence_score = 0.0
        reasoning_parts = []
        
        # Check for intent keywords
        intent_matches = 0
        for pattern in self.delivery_patterns['intent_keywords']:
            if re.search(pattern, message_lower):
                intent_matches += 1
                confidence_score += 0.15
                reasoning_parts.append(f"Found intent keyword: {pattern}")
        
        # Check for delivery number patterns
        delivery_numbers = self._extract_delivery_numbers(user_message)
        if delivery_numbers:
            confidence_score += 0.4
            reasoning_parts.append(f"Found {len(delivery_numbers)} potential delivery numbers")
        
        # Check for urgency indicators
        for pattern in self.delivery_patterns['urgency_indicators']:
            if re.search(pattern, message_lower):
                confidence_score += 0.1
                reasoning_parts.append(f"Found urgency indicator: {pattern}")
        
        # Check context from conversation history
        context_boost = self._analyze_conversation_context(conversation_history, 'delivery_tracking')
        confidence_score += context_boost
        if context_boost > 0:
            reasoning_parts.append(f"Conversation context boost: {context_boost:.2f}")
        
        # Check for explicit tool requests
        explicit_requests = [
            r'track\s+(?:my|the)?\s*(?:package|delivery|shipment)',
            r'check\s+(?:my|the)?\s*(?:delivery|shipment)\s*status',
            r'where\s+is\s+my\s+(?:package|order|delivery)',
            r'delivery\s+status'
        ]
        
        for pattern in explicit_requests:
            if re.search(pattern, message_lower):
                confidence_score += 0.25
                reasoning_parts.append(f"Explicit tool request detected: {pattern}")
        
        # Determine if tool is required
        tool_required = confidence_score >= 0.3  # Threshold for tool activation
        
        # Extract parameters
        extracted_params = {}
        required_params = ['delivery_number']
        
        if delivery_numbers:
            extracted_params['delivery_number'] = delivery_numbers[0]  # Use first found
            
        # If we have high confidence but no delivery number, still trigger tool
        # The tool/LLM will ask for the missing parameter
        if tool_required and not delivery_numbers:
            reasoning_parts.append("High confidence for delivery tracking but no delivery number found")
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No significant patterns detected"
        
        logger.debug(
            f"Delivery tracking analysis - Confidence: {confidence_score:.2f}, "
            f"Tool required: {tool_required}, Parameters: {extracted_params}"
        )
        
        return ToolDetectionResult(
            tool_required=tool_required,
            tool_name='delivery_tracker' if tool_required else None,
            confidence=min(confidence_score, 1.0),  # Cap at 1.0
            required_parameters=required_params,
            extracted_parameters=extracted_params,
            reasoning=reasoning
        )
    
    def _extract_delivery_numbers(self, text: str) -> List[str]:
        """
        Extract potential delivery numbers from text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of potential delivery numbers
        """
        
        delivery_numbers = []
        text_upper = text.upper()
        
        # Try each pattern in order of specificity
        for pattern in self.delivery_patterns['delivery_number_patterns']:
            matches = re.findall(pattern, text_upper)
            for match in matches:
                # Clean up the match
                clean_match = re.sub(r'[^\w]', '', match)
                
                # Validate length and format
                if self._validate_delivery_number(clean_match):
                    delivery_numbers.append(clean_match)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_numbers = []
        for num in delivery_numbers:
            if num not in seen:
                seen.add(num)
                unique_numbers.append(num)
        
        logger.debug(f"Extracted delivery numbers: {unique_numbers}")
        return unique_numbers
    
    def _validate_delivery_number(self, number: str) -> bool:
        """
        Validate if a string looks like a legitimate delivery number.
        
        Args:
            number: Potential delivery number
            
        Returns:
            True if it looks like a valid delivery number
        """
        
        if not number:
            return False
        
        # Length check
        if len(number) < 6 or len(number) > 25:
            return False
        
        # Should contain both letters and numbers for most formats
        has_letter = bool(re.search(r'[A-Z]', number))
        has_number = bool(re.search(r'\d', number))
        
        # Pure numeric is acceptable if long enough
        if not has_letter and len(number) >= 10:
            return True
        
        # Mixed format should have both letters and numbers
        if has_letter and has_number:
            return True
        
        return False
    
    def _analyze_conversation_context(
        self, 
        conversation_history: List[ConversationMessage], 
        tool_type: str
    ) -> float:
        """
        Analyze conversation history for context that might boost tool confidence.
        
        Args:
            conversation_history: Previous conversation messages
            tool_type: Type of tool context to look for
            
        Returns:
            Context boost value (0.0 to 0.3)
        """
        
        if not conversation_history or tool_type not in self.context_keywords:
            return 0.0
        
        context_boost = 0.0
        keywords = self.context_keywords[tool_type]
        
        # Look at recent messages (last 6)
        recent_messages = conversation_history[-6:]
        
        for message in recent_messages:
            message_lower = message.content.lower()
            
            # Count keyword matches
            keyword_matches = sum(
                1 for keyword in keywords
                if keyword in message_lower
            )
            
            if keyword_matches > 0:
                # More recent messages get higher weight
                message_age = len(recent_messages) - recent_messages.index(message)
                weight = message_age / len(recent_messages)
                
                boost = min(keyword_matches * 0.05 * weight, 0.1)
                context_boost += boost
        
        return min(context_boost, 0.3)  # Cap the boost
    
    def _extract_parameters_with_patterns(
        self, 
        text: str, 
        parameter_name: str
    ) -> List[str]:
        """
        Extract parameters using predefined patterns.
        
        Args:
            text: Text to search in
            parameter_name: Name of parameter to extract
            
        Returns:
            List of extracted parameter values
        """
        
        if parameter_name not in self.parameter_patterns:
            return []
        
        extracted = []
        patterns = self.parameter_patterns[parameter_name]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]  # Take first group if multiple groups
                
                clean_match = match.strip()
                if clean_match and clean_match not in extracted:
                    extracted.append(clean_match)
        
        return extracted
    
    def get_tool_confidence_threshold(self, tool_name: str) -> float:
        """
        Get confidence threshold for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Confidence threshold (0.0 to 1.0)
        """
        
        # Default thresholds for different tools
        thresholds = {
            'delivery_tracker': 0.3,
            # Add more tools as they are implemented
        }
        
        return thresholds.get(tool_name, 0.5)  # Default threshold
    
    def analyze_parameter_completeness(
        self, 
        tool_name: str, 
        extracted_parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze if extracted parameters are complete for tool execution.
        
        Args:
            tool_name: Name of the tool
            extracted_parameters: Parameters extracted from message
            
        Returns:
            Analysis of parameter completeness
        """
        
        try:
            # Get tool info from registry
            tool_info = self.tool_registry.get_tool_info(tool_name)
            if not tool_info:
                return {
                    'complete': False,
                    'missing_parameters': [],
                    'confidence': 0.0,
                    'reason': 'Tool not found in registry'
                }
            
            required_params = tool_info.get('required_parameters', [])
            optional_params = tool_info.get('optional_parameters', [])
            
            # Check which required parameters are missing
            missing_required = [
                param for param in required_params
                if param not in extracted_parameters
            ]
            
            # Check parameter quality
            parameter_quality = {}
            for param, value in extracted_parameters.items():
                quality_score = self._assess_parameter_quality(param, value)
                parameter_quality[param] = quality_score
            
            # Calculate overall completeness confidence
            total_required = len(required_params)
            found_required = len([p for p in required_params if p in extracted_parameters])
            
            completeness_ratio = found_required / total_required if total_required > 0 else 1.0
            
            # Factor in parameter quality
            avg_quality = sum(parameter_quality.values()) / len(parameter_quality) if parameter_quality else 0.0
            
            overall_confidence = (completeness_ratio * 0.7) + (avg_quality * 0.3)
            
            return {
                'complete': len(missing_required) == 0,
                'missing_parameters': missing_required,
                'found_parameters': list(extracted_parameters.keys()),
                'parameter_quality': parameter_quality,
                'confidence': overall_confidence,
                'reason': f"Found {found_required}/{total_required} required parameters"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing parameter completeness: {str(e)}")
            return {
                'complete': False,
                'missing_parameters': [],
                'confidence': 0.0,
                'reason': f"Analysis error: {str(e)}"
            }
    
    def _assess_parameter_quality(self, parameter_name: str, value: Any) -> float:
        """
        Assess the quality/confidence of an extracted parameter.
        
        Args:
            parameter_name: Name of the parameter
            value: Extracted parameter value
            
        Returns:
            Quality score (0.0 to 1.0)
        """
        
        if not value:
            return 0.0
        
        value_str = str(value).strip()
        
        # Parameter-specific quality assessment
        if parameter_name == 'delivery_number':
            # Length check
            if len(value_str) < 6:
                return 0.2
            elif len(value_str) > 25:
                return 0.3
            
            # Format validation
            if self._validate_delivery_number(value_str):
                return 0.9
            else:
                return 0.4
        
        # Generic quality assessment
        if len(value_str) > 0:
            return 0.6
        
        return 0.0
    
    def create_tool_suggestion(
        self, 
        detection_result: ToolDetectionResult
    ) -> Dict[str, Any]:
        """
        Create a suggestion for the user when tool confidence is borderline.
        
        Args:
            detection_result: Tool detection result
            
        Returns:
            Suggestion dictionary
        """
        
        if not detection_result.tool_name:
            return {}
        
        suggestions = {
            'delivery_tracker': {
                'message': "It looks like you want to track a delivery. Please provide your tracking number.",
                'examples': [
                    "Track package AB1234567890",
                    "Check delivery status for 1234567890123",
                    "Where is my package with tracking number XY987654321"
                ],
                'required_info': ["delivery_number"]
            }
        }
        
        return suggestions.get(detection_result.tool_name, {})