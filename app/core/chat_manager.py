"""
Chat Manager
============

Main orchestrator for chat functionality including LLM interaction,
tool calling, session management, and guardrails enforcement.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..config import Settings
from ..database.schemas import ChatRequest, ChatResponse, ConversationMessage
from ..llm.llm_factory import LLMFactory
from ..tools.tool_registry import ToolRegistry
from ..core.session_manager import SessionManager
from ..core.tool_detector import ToolDetector
from ..core.guardrails import GuardrailsManager
from ..core.conversation_flow import ConversationFlowManager
from ..utils.exceptions import ChatBotException, LLMError, ToolError, ValidationError
from ..utils.utils import count_tokens

logger = logging.getLogger(__name__)


class ChatManager:
    """
    Main chat management class that orchestrates the entire conversation flow.
    
    Responsibilities:
    - Coordinate between LLM, tools, and session management
    - Apply guardrails and content filtering
    - Manage conversation flow and context
    - Handle tool detection and execution
    - Track metrics and performance
    """
    
    def __init__(
        self,
        session_manager: SessionManager,
        llm_factory: LLMFactory,
        tool_registry: ToolRegistry,
        settings: Settings,
        request_id: str
    ):
        self.session_manager = session_manager
        self.llm_factory = llm_factory
        self.tool_registry = tool_registry
        self.settings = settings
        self.request_id = request_id
        
        # Initialize components
        self.tool_detector = ToolDetector(tool_registry, settings)
        self.guardrails = GuardrailsManager(settings)
        self.conversation_flow = ConversationFlowManager(settings)
        
        # Get LLM instance
        self.llm = llm_factory.get_llm()
        
        logger.debug(f"ChatManager initialized - Request: {request_id}")
    
    async def process_message(self, chat_request: ChatRequest) -> ChatResponse:
        """
        Process a chat message through the complete pipeline.
        
        Args:
            chat_request: User chat request
            
        Returns:
            ChatResponse: Complete response with AI message and metadata
            
        Raises:
            ChatBotException: If processing fails
        """
        
        start_time = time.time()
        session_id = chat_request.session_id
        user_message = chat_request.message
        
        try:
            logger.info(f"Processing message for session {session_id[:16]}... - Request: {self.request_id}")
            
            # Step 1: Get or create session and conversation history
            session = await self.session_manager.get_or_create_session(session_id)
            conversation_history = await self.session_manager.get_conversation_history(session_id)
            
            logger.debug(f"Session loaded - Messages in history: {len(conversation_history)}")
            
            # Step 2: Apply guardrails to user message
            await self.guardrails.validate_user_message(user_message, session_id, conversation_history)
            
            # Step 3: Save user message to database
            user_message_record = await self.session_manager.save_user_message(
                session_id, user_message
            )
            
            # Step 4: Check conversation flow state
            flow_state = self.conversation_flow.analyze_conversation_state(
                conversation_history, user_message
            )
            
            logger.debug(f"Conversation flow state: {flow_state}")
            
            # Step 5: Detect if tools are needed
            tool_detection_result = await self.tool_detector.analyze_message(
                user_message, conversation_history
            )
            
            logger.debug(f"Tool detection result: {tool_detection_result}")
            
            # Step 6: Handle tool execution if needed
            tool_response = None
            tool_called = False
            tool_name = None
            
            if tool_detection_result.tool_required:
                tool_response = await self._handle_tool_execution(
                    tool_detection_result, user_message, session_id, conversation_history
                )
                tool_called = True
                tool_name = tool_detection_result.tool_name
            
            # Step 7: Generate LLM response
            ai_response, input_tokens, output_tokens = await self._generate_llm_response(
                user_message, conversation_history, tool_response, flow_state
            )
            
            # Step 8: Apply guardrails to AI response
            ai_response = await self.guardrails.validate_ai_response(
                ai_response, user_message, session_id
            )
            
            # Step 9: Save AI response to database
            await self.session_manager.save_ai_message(
                session_id, ai_response, input_tokens, output_tokens, tool_name
            )
            
            # Step 10: Update session activity
            await self.session_manager.update_session_activity(session_id)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            logger.info(
                f"Message processed successfully - Session: {session_id[:16]}... "
                f"Processing time: {processing_time:.2f}s, Tool called: {tool_called}"
            )
            
            return ChatResponse(
                response=ai_response,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                tool_called=tool_called,
                tool_name=tool_name,
                session_id=session_id,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(
                f"Error processing message - Session: {session_id[:16]}... "
                f"Request: {self.request_id} - Error: {str(e)}",
                exc_info=True
            )
            
            # Log error to session if possible
            try:
                await self.session_manager.log_error(session_id, str(e), self.request_id)
            except:
                pass
            
            if isinstance(e, ChatBotException):
                raise
            else:
                raise ChatBotException(f"Failed to process message: {str(e)}")
    
    async def _handle_tool_execution(
        self,
        detection_result,
        user_message: str,
        session_id: str,
        conversation_history: List[ConversationMessage]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle tool execution based on detection result.
        
        Args:
            detection_result: Tool detection result
            user_message: User's message
            session_id: Session identifier
            conversation_history: Conversation history
            
        Returns:
            Dict containing tool execution result or None
        """
        
        try:
            tool_name = detection_result.tool_name
            required_params = detection_result.required_parameters
            
            logger.info(f"Executing tool: {tool_name} - Session: {session_id[:16]}...")
            
            # Check if all required parameters are available
            missing_params = [
                param for param in required_params
                if param not in detection_result.extracted_parameters
            ]
            
            if missing_params:
                logger.debug(f"Missing parameters for tool {tool_name}: {missing_params}")
                # Tool will be called but may prompt for missing parameters
                # The LLM will handle requesting missing information
            
            # Get tool instance
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                raise ToolError(f"Tool {tool_name} not found")
            
            # Execute tool
            tool_result = await tool.execute(
                parameters=detection_result.extracted_parameters,
                conversation_context={
                    'session_id': session_id,
                    'user_message': user_message,
                    'conversation_history': conversation_history
                }
            )
            
            logger.info(f"Tool {tool_name} executed successfully - Session: {session_id[:16]}...")
            
            return {
                'tool_name': tool_name,
                'parameters': detection_result.extracted_parameters,
                'result': tool_result,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Tool execution failed - Tool: {tool_name} - Error: {str(e)}")
            return {
                'tool_name': tool_name,
                'parameters': detection_result.extracted_parameters,
                'result': None,
                'success': False,
                'error': str(e)
            }
    
    async def _generate_llm_response(
        self,
        user_message: str,
        conversation_history: List[ConversationMessage],
        tool_response: Optional[Dict[str, Any]] = None,
        flow_state: Optional[Dict[str, Any]] = None
    ) -> tuple[str, int, int]:
        """
        Generate response using LLM.
        
        Args:
            user_message: User's message
            conversation_history: Conversation history
            tool_response: Tool execution result if any
            flow_state: Current conversation flow state
            
        Returns:
            Tuple of (ai_response, input_tokens, output_tokens)
        """
        
        try:
            logger.debug(f"Generating LLM response - Request: {self.request_id}")
            
            # Prepare conversation context
            messages = self._prepare_conversation_context(
                user_message, conversation_history, tool_response, flow_state
            )
            
            # Count input tokens
            input_text = self._format_messages_for_token_counting(messages)
            input_tokens = count_tokens(input_text)
            
            # Generate response using LLM
            ai_response = await self.llm.generate_response(
                messages=messages,
                max_tokens=self.settings.llm.max_tokens,
                temperature=self.settings.llm.temperature,
                top_p=self.settings.llm.top_p
            )
            
            # Count output tokens
            output_tokens = count_tokens(ai_response)
            
            logger.debug(
                f"LLM response generated - Input tokens: {input_tokens}, "
                f"Output tokens: {output_tokens}"
            )
            
            return ai_response, input_tokens, output_tokens
            
        except Exception as e:
            logger.error(f"LLM response generation failed - Error: {str(e)}")
            raise LLMError(f"Failed to generate response: {str(e)}")
    
    def _prepare_conversation_context(
        self,
        user_message: str,
        conversation_history: List[ConversationMessage],
        tool_response: Optional[Dict[str, Any]] = None,
        flow_state: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        Prepare conversation context for LLM.
        
        Args:
            user_message: Current user message
            conversation_history: Previous conversation
            tool_response: Tool execution result
            flow_state: Conversation flow state
            
        Returns:
            List of message dictionaries for LLM
        """
        
        messages = []
        
        # System message with context
        system_message = self._build_system_message(tool_response, flow_state)
        messages.append({"role": "system", "content": system_message})
        
        # Add conversation history
        for msg in conversation_history[-10:]:  # Limit history to prevent context overflow
            role = "user" if msg.role == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _build_system_message(
        self,
        tool_response: Optional[Dict[str, Any]] = None,
        flow_state: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build system message for LLM with context and instructions.
        
        Args:
            tool_response: Tool execution result
            flow_state: Conversation flow state
            
        Returns:
            System message string
        """
        
        system_parts = []
        
        # Base system message
        base_message = """You are an AI assistant that helps users with various tasks. You have access to tools that can help you provide more accurate and helpful responses."""
        
        # Add guardrails context
        if not self.settings.guardrails.enable_general_chat:
            base_message += """ You should only respond to requests related to the available tools and decline general conversation requests politely."""
        
        system_parts.append(base_message)
        
        # Add available tools information
        available_tools = self.tool_registry.list_tools()
        if available_tools:
            tools_info = "Available tools:\n"
            for tool_name, tool_info in available_tools.items():
                tools_info += f"- {tool_name}: {tool_info.get('description', 'No description')}\n"
            system_parts.append(tools_info)
        
        # Add tool response context if available
        if tool_response:
            if tool_response['success']:
                tool_context = f"Tool '{tool_response['tool_name']}' was executed successfully with result: {tool_response['result']}"
            else:
                tool_context = f"Tool '{tool_response['tool_name']}' execution failed: {tool_response.get('error', 'Unknown error')}"
            system_parts.append(tool_context)
        
        # Add flow state context
        if flow_state:
            if flow_state.get('awaiting_input'):
                system_parts.append(f"You are currently waiting for user input: {flow_state.get('waiting_for', 'additional information')}")
        
        # Guidelines
        guidelines = """
Guidelines:
- Be helpful, accurate, and concise
- If you need to use a tool but don't have all required parameters, ask for the missing information
- If a tool execution fails, explain the issue and suggest alternatives
- Maintain conversation context and refer back to previous exchanges when relevant
"""
        system_parts.append(guidelines)
        
        return "\n\n".join(system_parts)
    
    def _format_messages_for_token_counting(self, messages: List[Dict[str, str]]) -> str:
        """
        Format messages for token counting.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Formatted string for token counting
        """
        
        formatted_parts = []
        for msg in messages:
            formatted_parts.append(f"{msg['role']}: {msg['content']}")
        
        return "\n".join(formatted_parts)
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session information dictionary or None
        """
        
        try:
            session = await self.session_manager.get_session(session_id)
            if not session:
                return None
            
            message_count = await self.session_manager.get_message_count(session_id)
            recent_activity = await self.session_manager.get_recent_message_count(session_id, minutes=5)
            
            return {
                "session_id": session_id,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "last_activity": session.last_activity.isoformat() if session.last_activity else None,
                "total_messages": message_count,
                "recent_activity": recent_activity,
                "is_active": session.is_active,
                "request_id": self.request_id
            }
            
        except Exception as e:
            logger.error(f"Error getting session info - Session: {session_id[:16]}... Error: {str(e)}")
            raise ChatBotException(f"Failed to get session info: {str(e)}")
    
    async def clear_session(self, session_id: str) -> bool:
        """
        Clear a session and its history.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was cleared successfully
        """
        
        try:
            logger.info(f"Clearing session: {session_id[:16]}... - Request: {self.request_id}")
            
            success = await self.session_manager.clear_session(session_id)
            
            if success:
                logger.info(f"Session cleared successfully: {session_id[:16]}...")
            else:
                logger.warning(f"Failed to clear session: {session_id[:16]}...")
            
            return success
            
        except Exception as e:
            logger.error(f"Error clearing session - Session: {session_id[:16]}... Error: {str(e)}")
            raise ChatBotException(f"Failed to clear session: {str(e)}")
    
    async def list_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List active sessions.
        
        Args:
            limit: Maximum number of sessions to return
            offset: Offset for pagination
            
        Returns:
            List of session information
        """
        
        try:
            logger.debug(f"Listing sessions - Limit: {limit}, Offset: {offset} - Request: {self.request_id}")
            
            sessions = await self.session_manager.list_sessions(limit=limit, offset=offset)
            
            session_list = []
            for session in sessions:
                message_count = await self.session_manager.get_message_count(session.session_id)
                
                session_list.append({
                    "session_id": session.session_id,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "last_activity": session.last_activity.isoformat() if session.last_activity else None,
                    "total_messages": message_count,
                    "is_active": session.is_active
                })
            
            return session_list
            
        except Exception as e:
            logger.error(f"Error listing sessions - Error: {str(e)}")
            raise ChatBotException(f"Failed to list sessions: {str(e)}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get chat system statistics.
        
        Returns:
            Statistics dictionary
        """
        
        try:
            logger.debug(f"Getting chat stats - Request: {self.request_id}")
            
            stats = await self.session_manager.get_statistics()
            
            # Add LLM and tool statistics
            stats.update({
                "llm_provider": self.settings.llm.provider,
                "tools_enabled": self.settings.tools.enabled,
                "available_tools": len(self.tool_registry.list_tools()),
                "guardrails_enabled": {
                    "general_chat": self.settings.guardrails.enable_general_chat,
                    "content_filter": self.settings.guardrails.content_filter_enabled,
                    "max_conversation_length": self.settings.guardrails.max_conversation_length
                }
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting chat stats - Error: {str(e)}")
            raise ChatBotException(f"Failed to get statistics: {str(e)}")