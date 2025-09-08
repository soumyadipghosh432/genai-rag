"""
LLM Factory
===========

Factory pattern implementation for creating LLM provider instances
based on configuration settings.
"""

import logging
from typing import Dict, Type, Optional
from functools import lru_cache

from ..config import Settings
from ..utils.exceptions import LLMError, ConfigurationError
from .base import BaseLLM
from .amazon_nova import AmazonNovaLLM
from .gpt_oss import GPTOssLLM

logger = logging.getLogger(__name__)


class LLMFactory:
    """
    Factory class for creating LLM provider instances.
    
    Responsibilities:
    - Manage LLM provider registration
    - Create appropriate LLM instances based on configuration
    - Handle provider-specific initialization
    - Cache LLM instances for efficiency
    - Validate provider configurations
    """
    
    # Registry of available LLM providers
    _providers: Dict[str, Type[BaseLLM]] = {
        'amazon_nova': AmazonNovaLLM,
        'gpt_oss': GPTOssLLM
    }
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm_instance: Optional[BaseLLM] = None
        
        logger.debug(f"LLMFactory initialized with provider: {settings.llm.provider}")
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseLLM]) -> None:
        """
        Register a new LLM provider.
        
        Args:
            name: Provider name identifier
            provider_class: LLM provider class that inherits from BaseLLM
        """
        
        if not issubclass(provider_class, BaseLLM):
            raise ValueError(f"Provider class must inherit from BaseLLM")
        
        cls._providers[name] = provider_class
        logger.info(f"Registered LLM provider: {name}")
    
    @classmethod
    def get_available_providers(cls) -> Dict[str, Type[BaseLLM]]:
        """
        Get all available LLM providers.
        
        Returns:
            Dictionary of provider names to provider classes
        """
        return cls._providers.copy()
    
    def get_llm(self) -> BaseLLM:
        """
        Get LLM instance based on configuration.
        
        Returns:
            BaseLLM: Configured LLM provider instance
            
        Raises:
            LLMError: If provider creation fails
            ConfigurationError: If provider is not configured properly
        """
        
        # Return cached instance if available
        if self._llm_instance is not None:
            return self._llm_instance
        
        try:
            provider_name = self.settings.llm.provider
            
            # Validate provider exists
            if provider_name not in self._providers:
                available_providers = list(self._providers.keys())
                raise ConfigurationError(
                    f"Unknown LLM provider '{provider_name}'. "
                    f"Available providers: {available_providers}"
                )
            
            # Get provider class
            provider_class = self._providers[provider_name]
            
            # Validate provider configuration
            self._validate_provider_config(provider_name)
            
            # Create provider instance
            logger.info(f"Creating LLM instance for provider: {provider_name}")
            
            self._llm_instance = provider_class(self.settings)
            
            # Initialize the provider
            self._llm_instance.initialize()
            
            logger.info(f"Successfully created LLM instance: {provider_name}")
            return self._llm_instance
            
        except ConfigurationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create LLM instance: {str(e)}")
            raise LLMError(f"Failed to initialize LLM provider: {str(e)}")
    
    def _validate_provider_config(self, provider_name: str) -> None:
        """
        Validate provider-specific configuration.
        
        Args:
            provider_name: Name of the provider to validate
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        
        llm_config = self.settings.llm
        
        if provider_name == 'amazon_nova':
            # Validate Amazon Nova configuration
            if not llm_config.amazon_nova_region:
                raise ConfigurationError("Amazon Nova region is required")
            
            if not llm_config.amazon_nova_model_id:
                raise ConfigurationError("Amazon Nova model ID is required")
            
        elif provider_name == 'gpt_oss':
            # Validate GPT OSS configuration
            if not llm_config.gpt_oss_region:
                raise ConfigurationError("GPT OSS region is required")
            
            if not llm_config.gpt_oss_model_name:
                raise ConfigurationError("GPT OSS model name is required")
        
        # Common validations
        if llm_config.max_tokens <= 0:
            raise ConfigurationError("max_tokens must be greater than 0")
        
        if not (0.0 <= llm_config.temperature <= 2.0):
            raise ConfigurationError("temperature must be between 0.0 and 2.0")
        
        if not (0.0 <= llm_config.top_p <= 1.0):
            raise ConfigurationError("top_p must be between 0.0 and 1.0")
    
    def create_provider_instance(self, provider_name: str) -> BaseLLM:
        """
        Create a specific provider instance (bypassing cache).
        
        Args:
            provider_name: Name of the provider to create
            
        Returns:
            BaseLLM: New provider instance
            
        Raises:
            LLMError: If provider creation fails
        """
        
        try:
            if provider_name not in self._providers:
                available_providers = list(self._providers.keys())
                raise LLMError(
                    f"Unknown provider '{provider_name}'. "
                    f"Available: {available_providers}"
                )
            
            # Validate configuration for this provider
            original_provider = self.settings.llm.provider
            self.settings.llm.provider = provider_name
            
            try:
                self._validate_provider_config(provider_name)
            finally:
                self.settings.llm.provider = original_provider
            
            # Create instance
            provider_class = self._providers[provider_name]
            instance = provider_class(self.settings)
            instance.initialize()
            
            logger.info(f"Created new instance for provider: {provider_name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create provider instance: {str(e)}")
            raise LLMError(f"Provider creation failed: {str(e)}")
    
    def switch_provider(self, new_provider: str) -> BaseLLM:
        """
        Switch to a different LLM provider.
        
        Args:
            new_provider: Name of the new provider
            
        Returns:
            BaseLLM: New provider instance
        """
        
        try:
            logger.info(f"Switching LLM provider from {self.settings.llm.provider} to {new_provider}")
            
            # Update configuration
            old_provider = self.settings.llm.provider
            self.settings.llm.provider = new_provider
            
            # Clear cached instance
            self._llm_instance = None
            
            try:
                # Create new instance
                return self.get_llm()
            except Exception:
                # Rollback on failure
                self.settings.llm.provider = old_provider
                self._llm_instance = None
                raise
                
        except Exception as e:
            logger.error(f"Failed to switch LLM provider: {str(e)}")
            raise LLMError(f"Provider switch failed: {str(e)}")
    
    def get_provider_info(self, provider_name: Optional[str] = None) -> Dict[str, any]:
        """
        Get information about a provider.
        
        Args:
            provider_name: Provider to get info for (default: current provider)
            
        Returns:
            Dictionary containing provider information
        """
        
        if provider_name is None:
            provider_name = self.settings.llm.provider
        
        if provider_name not in self._providers:
            raise LLMError(f"Unknown provider: {provider_name}")
        
        provider_class = self._providers[provider_name]
        
        # Get basic info
        info = {
            'name': provider_name,
            'class': provider_class.__name__,
            'module': provider_class.__module__,
            'is_current': provider_name == self.settings.llm.provider,
            'configuration': {}
        }
        
        # Add provider-specific configuration info
        if provider_name == 'amazon_nova':
            info['configuration'] = {
                'region': self.settings.llm.amazon_nova_region,
                'model_id': self.settings.llm.amazon_nova_model_id
            }
        elif provider_name == 'gpt_oss':
            info['configuration'] = {
                'region': self.settings.llm.gpt_oss_region,
                'model_name': self.settings.llm.gpt_oss_model_name
            }
        
        # Add common configuration
        info['configuration'].update({
            'max_tokens': self.settings.llm.max_tokens,
            'temperature': self.settings.llm.temperature,
            'top_p': self.settings.llm.top_p
        })
        
        return info
    
    def validate_all_providers(self) -> Dict[str, Dict[str, any]]:
        """
        Validate configuration for all registered providers.
        
        Returns:
            Dictionary mapping provider names to validation results
        """
        
        results = {}
        original_provider = self.settings.llm.provider
        
        for provider_name in self._providers.keys():
            try:
                # Temporarily set provider for validation
                self.settings.llm.provider = provider_name
                self._validate_provider_config(provider_name)
                
                results[provider_name] = {
                    'valid': True,
                    'error': None
                }
                
            except Exception as e:
                results[provider_name] = {
                    'valid': False,
                    'error': str(e)
                }
            finally:
                # Restore original provider
                self.settings.llm.provider = original_provider
        
        return results
    
    def health_check(self) -> Dict[str, any]:
        """
        Perform health check on current LLM provider.
        
        Returns:
            Health check results
        """
        
        try:
            llm = self.get_llm()
            
            # Try to get provider status
            if hasattr(llm, 'health_check'):
                health_result = llm.health_check()
            else:
                health_result = {
                    'status': 'unknown',
                    'message': 'Provider does not implement health_check'
                }
            
            return {
                'provider': self.settings.llm.provider,
                'factory_status': 'healthy',
                'provider_health': health_result,
                'instance_cached': self._llm_instance is not None
            }
            
        except Exception as e:
            logger.error(f"LLM health check failed: {str(e)}")
            return {
                'provider': self.settings.llm.provider,
                'factory_status': 'unhealthy',
                'error': str(e),
                'instance_cached': self._llm_instance is not None
            }
    
    def reset(self) -> None:
        """
        Reset the factory by clearing cached instances.
        """
        
        logger.info("Resetting LLM factory")
        
        # Cleanup existing instance if it has cleanup method
        if self._llm_instance and hasattr(self._llm_instance, 'cleanup'):
            try:
                self._llm_instance.cleanup()
            except Exception as e:
                logger.warning(f"Error during LLM cleanup: {str(e)}")
        
        self._llm_instance = None
        logger.info("LLM factory reset complete")
    
    def __del__(self):
        """Cleanup when factory is destroyed"""
        try:
            self.reset()
        except:
            pass  # Ignore errors during cleanup