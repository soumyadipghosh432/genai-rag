File Descriptions
Configuration Files

.env - Environment variables (API keys, secrets)
config.yaml - Main configuration (LLM selection, guardrails, debug mode)
requirements.txt - Python dependencies

Main Application (app/)

main.py - FastAPI app initialization and route registration
config.py - Configuration loader and validator
dependencies.py - FastAPI dependency injection setup

API Layer (app/api/)

chat.py - Main chat endpoint (/chat)
health.py - Health check endpoints

Core Business Logic (app/core/)

chat_manager.py - Main orchestration (handles chat flow, tool detection, LLM calling)
session_manager.py - Session CRUD operations with SQLite
tool_detector.py - Analyzes messages for tool requirements
guardrails.py - Enforces chat restrictions based on configuration
conversation_flow.py - Manages conversation state and context

LLM Integration (app/llm/)

base.py - Abstract base class for LLM providers
amazon_nova.py - Amazon Nova implementation with converse API
gpt_oss.py - GPT OSS implementation with converse API
llm_factory.py - Factory pattern for LLM selection

Tool System (app/tools/)

base_tool.py - Abstract base class for all tools
tool_registry.py - Dynamic tool registration and discovery
tool_executor.py - Tool execution with parameter validation
delivery_tracker/ - Delivery tracking tool module

Database Layer (app/database/)

models.py - SQLAlchemy models (Session, Message, ToolCall)
schemas.py - Pydantic models for API requests/responses
crud.py - Database operations (create, read, update, delete)
connection.py - Database setup and connection management

Utilities (app/utils/)

utils.py - General utilities including count_tokens() function
exceptions.py - Custom application exceptions
validators.py - Input validation functions

🔧 Key Design Features
1. Modular Architecture

Each component has a single responsibility
Easy to add new LLMs, tools, and features
Clean separation of concerns

2. Tool System Design

Plugin-based: New tools inherit from BaseTool
Auto-registration: Tools automatically register themselves
Parameter validation: Automatic input validation
Easy expansion: Add new tools by creating new modules

3. LLM Abstraction

Provider-agnostic: Switch between LLMs via configuration
Consistent interface: All LLMs implement the same methods
Conversation history: Built-in support for message history
Token counting: Integrated token tracking

4. Session Management

SQLite storage: Lightweight, file-based database
SQLAlchemy ORM: Type-safe database operations
Conversation persistence: Full chat history storage
Session isolation: Each session maintains separate context

5. Guardrails System

Configurable restrictions: Enable/disable general chat
Tool-only mode: Restrict to tool-related conversations
Easy toggle: Change behavior via configuration

6. Configuration Management

Centralized config: All settings in config.yaml
Environment variables: Sensitive data in .env
Runtime configuration: Change behavior without code changes