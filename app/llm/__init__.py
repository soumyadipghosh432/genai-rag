"""
LLM Module
==========

Large Language Model integration module supporting multiple providers:
- Amazon Nova (Bedrock)
- GPT OSS (SageMaker/Bedrock)

Provides abstract interfaces and factory patterns for easy provider switching.
"""

from .base import BaseLLM, LLMResponse
from .llm_factory import LLMFactory
from .amazon_nova import AmazonNovaLLM
from .gpt_oss import GPTOssLLM

__all__ = [
    "BaseLLM",
    "LLMResponse", 
    "LLMFactory",
    "AmazonNovaLLM",
    "GPTOssLLM"
]