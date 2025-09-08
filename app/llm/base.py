"""
Base LLM Interface
==================

Abstract base class for all LLM providers with common interface
and response structures.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, NamedTuple
from datetime import datetime

from ..config import Settings

logger = logging.getLogger(__name__)


class LLMResponse(NamedTuple):
    """Standard response structure for LLM operations"""
    content: str
    finish_reason: str
    input_tokens: int
    output_tokens: int
    model_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseLLM(ABC):
    """
    Abstract base class for all LLM providers.
    
    Defines the common interface that all LLM implementations must follow.
    Provides basic functionality and enforces consistent behavior across providers.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = self.__class__.__name__.lower().replace('llm', '').replace('_', '')
        self.is_initialized = False
        self._client = None
        
        logger.debug(f"Initializing {self.provider} LLM provider")
    
    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the LLM provider.
        
        This method should set up the client connection and validate credentials.
        Must be called before using any other methods.
        
        Raises:
            LLMError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate a response using the LLM.
        
        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Generated response text
            
        Raises:
            LLMError: If generation fails
        """
        pass
    
    @abstractmethod
    def converse(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Have a conversation using the converse API.
        
        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with detailed response information
            
        Raises:
            LLMError: If conversation fails
        """
        pass
    
    def get_default_parameters(self) -> Dict[str, Any]:
        """
        Get default parameters for this LLM provider.
        
        Returns:
            Dictionary of default parameters
        """
        return {
            'max_tokens': self.settings.llm.max_tokens,
            'temperature': self.settings.llm.temperature,
            'top_p': self.settings.llm.top_p
        }
    
    def validate_messages(self, messages: List[Dict[str, str]]) -> None:
        """
        Validate message format.
        
        Args:
            messages: List of messages to validate
            
        Raises:
            ValidationError: If messages are invalid
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")
        
        for i, message in enumerate(messages):
            if not isinstance(message, dict):
                raise ValueError(f"Message {i} must be a dictionary")
            
            if 'role' not in message:
                raise ValueError(f"Message {i} missing 'role' field")
            
            if 'content' not in message:
                raise ValueError(f"Message {i} missing 'content' field")
            
            if message['role'] not in ['system', 'user', 'assistant']:
                raise ValueError(f"Message {i} has invalid role: {message['role']}")
    
    def format_messages_for_provider(self, messages: List[Dict[str, str]]) -> Any:
        """
        Format messages for the specific provider format.
        
        Override this method in subclasses for provider-specific formatting.
        
        Args:
            messages: Standard message format
            
        Returns:
            Provider-specific message format
        """
        return messages
    
    def extract_response_content(self, response: Any) -> str:
        """
        Extract text content from provider response.
        
        Override this method in subclasses for provider-specific extraction.
        
        Args:
            response: Raw provider response
            
        Returns:
            Extracted text content
        """
        return str(response)
    
    def get_token_count(self, text: str) -> int:
        """
        Get approximate token count for text.
        
        This is a basic implementation. Override in subclasses for more accurate counting.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Approximate token count
        """
        # Basic approximation: ~4 characters per token
        return len(text) // 4
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the LLM provider.
        
        Returns:
            Health check results
        """
        try:
            if not self.is_initialized:
                return {
                    'status': 'unhealthy',
                    'message': 'Provider not initialized',
                    'provider': self.provider
                }
            
            # Basic health check - can be overridden by subclasses
            return {
                'status': 'healthy',
                'message': 'Provider is initialized',
                'provider': self.provider,
                'client_available': self._client is not None
            }
            
        except Exception as e:
            logger.error(f"Health check failed for {self.provider}: {str(e)}")
            return {
                'status': 'unhealthy',
                'message': f'Health check failed: {str(e)}',
                'provider': self.provider
            }
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get provider information.
        
        Returns:
            Provider information dictionary
        """
        return {
            'provider': self.provider,
            'class': self.__class__.__name__,
            'initialized': self.is_initialized,
            'supports_streaming': hasattr(self, 'stream_response'),
            'supports_tools': hasattr(self, 'call_tool'),
            'default_parameters': self.get_default_parameters()
        }
    
    def cleanup(self) -> None:
        """
        Cleanup resources used by the provider.
        
        Override in subclasses if cleanup is needed.
        """
        logger.debug(f"Cleaning up {self.provider} LLM provider")
        self.is_initialized = False
        self._client = None
    
    def __enter__(self):
        """Context manager entry"""
        if not self.is_initialized:
            self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
    
    def __repr__(self) -> str:
        """String representation"""
        status = "initialized" if self.is_initialized else "not initialized"
        return f"{self.__class__.__name__}(provider={self.provider}, status={status})"