"""
Configuration Management
========================

Handles application configuration loading from YAML files and environment variables.
Uses Pydantic for validation and type checking.
"""

import os
import logging
from typing import Optional, Dict, Any
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    """LLM provider configuration"""
    provider: str = Field(default="amazon_nova", description="LLM provider to use")
    
    # Amazon Nova configuration
    amazon_nova_region: str = Field(default="us-east-1", description="AWS region for Nova")
    amazon_nova_model_id: str = Field(default="amazon.nova-micro-v1:0", description="Nova model ID")
    
    # GPT OSS configuration
    gpt_oss_region: str = Field(default="us-west-2", description="AWS region for GPT OSS")
    gpt_oss_model_name: str = Field(default="gpt-model", description="GPT OSS model name")
    
    # Common settings
    max_tokens: int = Field(default=4096, description="Maximum tokens per request")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    top_p: float = Field(default=0.9, description="Top-p sampling parameter")
    
    @validator('provider')
    def validate_provider(cls, v):
        valid_providers = ['amazon_nova', 'gpt_oss']
        if v not in valid_providers:
            raise ValueError(f"Provider must be one of: {valid_providers}")
        return v


class GuardrailsConfig(BaseModel):
    """Chat guardrails configuration"""
    enable_general_chat: bool = Field(default=True, description="Allow general chat")
    max_conversation_length: int = Field(default=50, description="Max messages per conversation")
    session_timeout_minutes: int = Field(default=30, description="Session timeout in minutes")
    content_filter_enabled: bool = Field(default=True, description="Enable content filtering")
    max_input_length: int = Field(default=2000, description="Maximum input message length")


class ToolsConfig(BaseModel):
    """Tools configuration"""
    enabled: bool = Field(default=True, description="Enable tool functionality")
    timeout_seconds: int = Field(default=30, description="Tool execution timeout")
    max_retries: int = Field(default=3, description="Maximum tool execution retries")
    
    # Delivery tracker specific
    delivery_tracker_enabled: bool = Field(default=True, description="Enable delivery tracker tool")


class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field(default="sqlite:///data/chat_history.db", description="Database URL")
    echo: bool = Field(default=False, description="SQLAlchemy echo mode")
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field(default="INFO", description="Logging level")
    file_path: str = Field(default="data/logs/app.log", description="Log file path")
    max_file_size_mb: int = Field(default=100, description="Max log file size in MB")
    backup_count: int = Field(default=5, description="Number of log file backups")
    
    @validator('level')
    def validate_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Level must be one of: {valid_levels}")
        return v.upper()


class Settings(BaseSettings):
    """Main application settings"""
    
    # App settings
    app_title: str = Field(default="AI Chatbot with Tool Integration", description="Application title")
    app_description: str = Field(default="A sophisticated chatbot with LLM integration and delivery tracking tools", description="App description")
    app_version: str = Field(default="1.0.0", description="Application version")
    
    # Environment
    environment: str = Field(default="development", description="Environment (development/production)")
    debug: bool = Field(default=True, description="Debug mode")
    
    # API settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    
    # Security
    secret_key: str = Field(default="your-secret-key-change-in-production", description="Secret key for sessions")
    cors_origins: list = Field(default=["*"], description="CORS allowed origins")
    
    # AWS credentials (loaded from environment)
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS Access Key ID")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS Secret Access Key")
    
    # Component configurations
    llm: LLMConfig = Field(default_factory=LLMConfig)
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator('environment')
    def validate_environment(cls, v):
        valid_envs = ['development', 'production', 'testing']
        if v not in valid_envs:
            raise ValueError(f"Environment must be one of: {valid_envs}")
        return v
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development"


def load_config_from_yaml(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to the YAML config file
        
    Returns:
        Dict containing configuration data
    """
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.warning(f"Config file {config_path} not found, using defaults")
        return {}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {config_path}")
            return config_data
            
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML config file: {e}")
        raise ValueError(f"Invalid YAML configuration: {e}")
        
    except Exception as e:
        logger.error(f"Error loading config file: {e}")
        raise


def merge_config_data(yaml_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge YAML configuration data into a flat structure for Pydantic.
    
    Args:
        yaml_data: Nested configuration data from YAML
        
    Returns:
        Flattened configuration dictionary
    """
    
    merged = {}
    
    # App level settings
    if 'app' in yaml_data:
        app_config = yaml_data['app']
        merged.update({
            'app_title': app_config.get('title', 'AI Chatbot with Tool Integration'),
            'app_description': app_config.get('description', 'A sophisticated chatbot'),
            'app_version': app_config.get('version', '1.0.0'),
            'environment': app_config.get('environment', 'development'),
            'debug': app_config.get('debug', True),
        })
    
    # LLM settings
    if 'llm' in yaml_data:
        llm_config = yaml_data['llm']
        llm_data = {
            'provider': llm_config.get('provider', 'amazon_nova'),
            'max_tokens': llm_config.get('max_tokens', 4096),
            'temperature': llm_config.get('temperature', 0.7),
            'top_p': llm_config.get('top_p', 0.9),
        }
        
        # Amazon Nova specific
        if 'amazon_nova' in llm_config:
            nova_config = llm_config['amazon_nova']
            llm_data.update({
                'amazon_nova_region': nova_config.get('region', 'us-east-1'),
                'amazon_nova_model_id': nova_config.get('model_id', 'amazon.nova-micro-v1:0'),
            })
        
        # GPT OSS specific
        if 'gpt_oss' in llm_config:
            gpt_config = llm_config['gpt_oss']
            llm_data.update({
                'gpt_oss_region': gpt_config.get('region', 'us-west-2'),
                'gpt_oss_model_name': gpt_config.get('model_name', 'gpt-model'),
            })
        
        merged['llm'] = llm_data
    
    # Guardrails settings
    if 'guardrails' in yaml_data:
        merged['guardrails'] = yaml_data['guardrails']
    
    # Tools settings
    if 'tools' in yaml_data:
        merged['tools'] = yaml_data['tools']
    
    # Database settings
    if 'database' in yaml_data:
        merged['database'] = yaml_data['database']
    
    # Logging settings
    if 'logging' in yaml_data:
        merged['logging'] = yaml_data['logging']
    
    return merged


@lru_cache()
def get_settings(config_path: str = "config.yaml") -> Settings:
    """
    Get application settings with caching.
    Loads from YAML file and environment variables.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        Settings: Validated application settings
    """
    
    try:
        # Load YAML configuration
        yaml_data = load_config_from_yaml(config_path)
        
        # Merge and flatten config data
        config_data = merge_config_data(yaml_data)
        
        # Create settings instance (will also load from environment)
        settings = Settings(**config_data)
        
        logger.info("Configuration loaded and validated successfully")
        return settings
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        # Fallback to default settings
        logger.warning("Using default configuration")
        return Settings()


def create_config_template(output_path: str = "config.yaml.template") -> None:
    """
    Create a template configuration file.
    
    Args:
        output_path: Path where to save the template
    """
    
    template = """
# Application Configuration
app:
  title: "AI Chatbot with Tool Integration"
  description: "A sophisticated chatbot with LLM integration and delivery tracking tools"
  version: "1.0.0"
  environment: "development"  # development, production, testing
  debug: true

# Chat Guardrails
guardrails:
  enable_general_chat: true  # false = tool-only mode
  max_conversation_length: 50
  session_timeout_minutes: 30
  content_filter_enabled: true
  max_input_length: 2000

# LLM Configuration
llm:
  provider: "amazon_nova"  # "amazon_nova" or "gpt_oss"
  max_tokens: 4096
  temperature: 0.7
  top_p: 0.9
  
  amazon_nova:
    region: "us-east-1"
    model_id: "amazon.nova-micro-v1:0"
  
  gpt_oss:
    region: "us-west-2"
    model_name: "your-gpt-model"

# Tool Configuration
tools:
  enabled: true
  timeout_seconds: 30
  max_retries: 3
  delivery_tracker_enabled: true

# Database Configuration
database:
  url: "sqlite:///data/chat_history.db"
  echo: false  # SQLAlchemy logging
  pool_size: 10
  max_overflow: 20

# Logging Configuration
logging:
  level: "INFO"
  file_path: "data/logs/app.log"
  max_file_size_mb: 100
  backup_count: 5
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template.strip())
    
    logger.info(f"Configuration template created at {output_path}")


if __name__ == "__main__":
    # Create config template and test loading
    create_config_template()
    settings = get_settings()
    print(f"Loaded settings: {settings.model_dump()}")