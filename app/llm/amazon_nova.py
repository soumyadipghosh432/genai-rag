"""
Amazon Nova LLM Provider
=========================

Amazon Nova implementation using AWS Bedrock with converse API.
"""

import logging
import json
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from ..config import Settings
from ..utils.exceptions import LLMError, ConfigurationError
from .base import BaseLLM, LLMResponse

logger = logging.getLogger(__name__)


class AmazonNovaLLM(BaseLLM):
    """
    Amazon Nova LLM provider using AWS Bedrock.
    
    Supports Nova models through the Bedrock converse API with
    conversation history and parameter control.
    """
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.region = settings.llm.amazon_nova_region
        self.model_id = settings.llm.amazon_nova_model_id
        self.bedrock_client = None
        
        logger.debug(f"Amazon Nova LLM configured for region: {self.region}, model: {self.model_id}")
    
    def initialize(self) -> None:
        """Initialize the Bedrock client and validate configuration."""
        
        try:
            logger.info(f"Initializing Amazon Nova LLM in region: {self.region}")
            
            # Create Bedrock Runtime client
            session = boto3.Session()
            self.bedrock_client = session.client(
                service_name='bedrock-runtime',
                region_name=self.region
            )
            
            # Validate credentials and model access
            self._validate_model_access()
            
            self.is_initialized = True
            self._client = self.bedrock_client
            
            logger.info(f"Successfully initialized Amazon Nova LLM")
            
        except Exception as e:
            logger.error(f"Failed to initialize Amazon Nova LLM: {str(e)}")
            raise LLMError(f"Amazon Nova initialization failed: {str(e)}")
    
    def _validate_model_access(self) -> None:
        """Validate that we can access the specified model."""
        
        try:
            # Try to list foundation models to validate access
            response = self.bedrock_client.list_foundation_models()
            
            # Check if our model is available
            available_models = [model['modelId'] for model in response.get('modelSummaries', [])]
            
            if self.model_id not in available_models:
                logger.warning(f"Model {self.model_id} not found in available models. "
                             f"Available models: {available_models[:5]}...")
                # Don't fail here as the model might still work
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                raise ConfigurationError(
                    "Access denied to Bedrock. Check your AWS credentials and permissions."
                )
            elif error_code == 'UnauthorizedOperation':
                raise ConfigurationError(
                    "Unauthorized to access Bedrock. Verify your IAM permissions."
                )
            else:
                logger.warning(f"Could not validate model access: {str(e)}")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate response using Amazon Nova."""
        
        try:
            # Use converse method and extract just the text
            response = self.converse(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                **kwargs
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"Failed to generate response with Amazon Nova: {str(e)}")
            raise LLMError(f"Response generation failed: {str(e)}")
    
    def converse(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """Have a conversation using the Bedrock converse API."""
        
        if not self.is_initialized:
            raise LLMError("Amazon Nova LLM not initialized")
        
        try:
            # Validate and format messages
            self.validate_messages(messages)
            bedrock_messages = self._format_messages_for_bedrock(messages)
            
            # Prepare inference parameters
            inference_config = self._prepare_inference_config(
                max_tokens, temperature, top_p
            )
            
            logger.debug(f"Calling Bedrock converse API with {len(bedrock_messages)} messages")
            
            # Call Bedrock converse API
            response = self.bedrock_client.converse(
                modelId=self.model_id,
                messages=bedrock_messages,
                inferenceConfig=inference_config,
                **kwargs
            )
            
            # Extract response data
            output_message = response['output']['message']
            usage = response.get('usage', {})
            stop_reason = response.get('stopReason', 'end_turn')
            
            # Extract content from response
            content = ''
            if 'content' in output_message:
                for content_block in output_message['content']:
                    if 'text' in content_block:
                        content += content_block['text']
            
            # Create response object
            llm_response = LLMResponse(
                content=content,
                finish_reason=stop_reason,
                input_tokens=usage.get('inputTokens', 0),
                output_tokens=usage.get('outputTokens', 0),
                model_id=self.model_id,
                metadata={
                    'response_id': response.get('responseMetadata', {}).get('RequestId'),
                    'model_id': self.model_id,
                    'region': self.region
                }
            )
            
            logger.debug(
                f"Amazon Nova response: {len(content)} chars, "
                f"{usage.get('inputTokens', 0)} input tokens, "
                f"{usage.get('outputTokens', 0)} output tokens"
            )
            
            return llm_response
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"Bedrock API error: {error_code} - {error_message}")
            
            if error_code == 'ThrottlingException':
                raise LLMError("Request rate exceeded. Please try again later.")
            elif error_code == 'ValidationException':
                raise LLMError(f"Invalid request: {error_message}")
            elif error_code == 'AccessDeniedException':
                raise LLMError("Access denied. Check your permissions.")
            elif error_code == 'ModelNotReadyException':
                raise LLMError("Model is not ready. Please try again later.")
            else:
                raise LLMError(f"Bedrock error: {error_message}")
                
        except BotoCoreError as e:
            logger.error(f"AWS SDK error: {str(e)}")
            raise LLMError(f"AWS connection error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Unexpected error in Amazon Nova converse: {str(e)}")
            raise LLMError(f"Conversation failed: {str(e)}")
    
    def _format_messages_for_bedrock(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Format messages for Bedrock converse API."""
        
        bedrock_messages = []
        
        for message in messages:
            role = message['role']
            content = message['content']
            
            # Skip system messages for now - Bedrock handles them differently
            if role == 'system':
                continue
            
            # Convert role names
            if role == 'assistant':
                bedrock_role = 'assistant'
            else:
                bedrock_role = 'user'
            
            bedrock_message = {
                'role': bedrock_role,
                'content': [
                    {
                        'text': content
                    }
                ]
            }
            
            bedrock_messages.append(bedrock_message)
        
        return bedrock_messages
    
    def _prepare_inference_config(
        self,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> Dict[str, Any]:
        """Prepare inference configuration for Bedrock."""
        
        config = {}
        
        # Set max tokens
        if max_tokens is not None:
            config['maxTokens'] = max_tokens
        else:
            config['maxTokens'] = self.settings.llm.max_tokens
        
        # Set temperature
        if temperature is not None:
            config['temperature'] = temperature
        else:
            config['temperature'] = self.settings.llm.temperature
        
        # Set top_p
        if top_p is not None:
            config['topP'] = top_p
        else:
            config['topP'] = self.settings.llm.top_p
        
        return config
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check specific to Amazon Nova."""
        
        base_health = super().health_check()
        
        if not self.is_initialized:
            return base_health
        
        try:
            # Try a simple API call to validate connectivity
            response = self.bedrock_client.list_foundation_models(byProvider='amazon')
            
            nova_models = [
                model for model in response.get('modelSummaries', [])
                if 'nova' in model.get('modelId', '').lower()
            ]
            
            base_health.update({
                'bedrock_accessible': True,
                'nova_models_available': len(nova_models),
                'configured_model': self.model_id,
                'region': self.region
            })
            
        except Exception as e:
            logger.error(f"Amazon Nova health check failed: {str(e)}")
            base_health.update({
                'status': 'unhealthy',
                'bedrock_accessible': False,
                'error': str(e)
            })
        
        return base_health
    
    def get_supported_models(self) -> List[str]:
        """Get list of supported Nova models."""
        
        if not self.is_initialized:
            raise LLMError("Amazon Nova LLM not initialized")
        
        try:
            response = self.bedrock_client.list_foundation_models(byProvider='amazon')
            
            nova_models = []
            for model in response.get('modelSummaries', []):
                model_id = model.get('modelId', '')
                if 'nova' in model_id.lower():
                    nova_models.append(model_id)
            
            return nova_models
            
        except Exception as e:
            logger.error(f"Failed to get supported models: {str(e)}")
            return []
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Dict[str, float]:
        """
        Estimate cost for token usage (approximate pricing).
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost estimation dictionary
        """
        
        # These are approximate costs and may vary
        # Check AWS pricing for current rates
        pricing = {
            'amazon.nova-micro-v1:0': {'input': 0.000035, 'output': 0.00014},
            'amazon.nova-lite-v1:0': {'input': 0.00006, 'output': 0.00024},
            'amazon.nova-pro-v1:0': {'input': 0.0008, 'output': 0.0032}
        }
        
        model_pricing = pricing.get(self.model_id, {'input': 0.0001, 'output': 0.0004})
        
        input_cost = (input_tokens / 1000) * model_pricing['input']
        output_cost = (output_tokens / 1000) * model_pricing['output']
        total_cost = input_cost + output_cost
        
        return {
            'input_cost': round(input_cost, 6),
            'output_cost': round(output_cost, 6),
            'total_cost': round(total_cost, 6),
            'currency': 'USD'
        }
    
    def cleanup(self) -> None:
        """Cleanup Amazon Nova resources."""
        
        logger.debug("Cleaning up Amazon Nova LLM")
        super().cleanup()
        self.bedrock_client = None