#!/usr/bin/env python3
"""
Enhanced MCP Server with Real Scraping Logic Integration
Real-time streaming during actual YÖK scraping operations
"""

import asyncio
import json
import sys
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime
import time
from aiohttp import web, ClientSession
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parent / "config.env")

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_adapter import YOKAcademicMCPAdapter

# Environment configuration
SERVER_HOST = os.getenv("MCP_SERVER_HOST", "localhost")
SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "5000"))
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").lower() == "true"
CORS_ENABLED = os.getenv("CORS_ENABLED", "true").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
SSE_HEARTBEAT_INTERVAL = int(os.getenv("SSE_HEARTBEAT_INTERVAL", "15"))
MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "10"))

# Logging configuration
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_format = os.getenv("LOG_FORMAT", "structured")

# Create logs directory if it doesn't exist
log_file_path = os.getenv("LOG_FILE_PATH", "logs/mcp_server.log")
log_dir = os.path.dirname(log_file_path)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

# Simple logging for local development
if os.getenv("NODE_ENV") == "production" and log_format == "structured":
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        ]
    )
else:
    # Simple format for local development (no emojis in console)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        ]
    )

logger = logging.getLogger(__name__)

class RealScrapingMCPProtocolServer:
    """
    Enhanced MCP Server with real-time streaming during actual scraping
    Integrates with real YÖK scraping tools
    """
    
    def __init__(self):
        self.sessions = {}
        self.adapter = YOKAcademicMCPAdapter()
        self.streaming_tasks = {}  # Track active streaming tasks
        self.active_streams = {}  # Track active SSE connections
        self.base_dir = Path(__file__).parent
        self.session_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)
        
        # Create necessary directories
        self.ensure_directories()
    
    def ensure_directories(self):
        """Ensure all required directories exist"""
        dirs_to_create = [
            self.base_dir / "public" / "collaborator-sessions",
            self.base_dir / "logs"
        ]
        
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory ensured: {dir_path}")
        
    def generate_session_id(self):
        """Generate a readable and sortable session ID"""
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        # Add milliseconds for uniqueness
        milliseconds = int(time.time() * 1000) % 1000
        return f"session_{timestamp}_{milliseconds:03d}"
    
    async def handle_initialize(self, request):
        """MCP initialize endpoint - MCP 2025-03-26 Streamable HTTP compatible"""
        try:
            # Handle both GET and POST requests as per new spec
            if request.method == "GET":
                # GET should support listening for server messages (SSE stream)
                return await self.handle_sse_stream(request)
            
            data = await request.json()
            method = data.get("method")
            
            # Only handle initialize method here
            if method != "initialize":
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found in initialize handler: {method}"
                    }
                }, status=404)
            
            session_id = self.generate_session_id()
            
            # Session'ı kaydet
            self.sessions[session_id] = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "client_info": data.get("params", {}).get("clientInfo", {}),
                "status": "initialized"
            }
            
            # MCP 2025-03-26 uyumlu response
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {
                        "tools": {},
                        "logging": {},
                        "experimental": {}
                    },
                    "serverInfo": {
                        "name": "YOK Academic MCP Real Scraping Server",
                        "version": "3.0.0"
                    }
                }
            }
            
            # Session ID'yi Mcp-Session-Id header'ına ekle (yeni spec)
            headers = {
                'Mcp-Session-Id': session_id,
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type, Mcp-Session-Id, Last-Event-ID',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE',
                'Access-Control-Expose-Headers': 'Mcp-Session-Id'
            }
            
            resp = web.json_response(response, headers=headers)
            logger.info(f"✅ MCP Session initialized: {session_id}")
            return resp
            
        except Exception as e:
            logger.error(f"Initialize error: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            return web.json_response(error_response, status=500, headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type, Mcp-Session-Id',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE'
            })
    
    async def handle_sse_stream(self, request):
        """Handle SSE stream for server-to-client messages - MCP 2025-03-26"""
        session_id = request.headers.get('Mcp-Session-Id')
        last_event_id = request.headers.get('Last-Event-ID')
        
        logger.info(f"📡 SSE Stream requested - Session: {session_id}, Last-Event-ID: {last_event_id}")
        
        # Create SSE response
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream; charset=utf-8',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type, Mcp-Session-Id, Last-Event-ID',
                'Access-Control-Expose-Headers': 'Mcp-Session-Id',
                'X-Accel-Buffering': 'no'
            }
        )
        await response.prepare(request)
        
        # Store stream for session
        if session_id:
            self.active_streams[session_id] = response
        
        try:
            # Send initial heartbeat
            await response.write(b": heartbeat\n\n")
            await response.drain()
            
            # Keep connection alive with periodic heartbeats
            while session_id in self.active_streams:
                await asyncio.sleep(SSE_HEARTBEAT_INTERVAL)
                if session_id in self.active_streams:
                    await response.write(b": heartbeat\n\n")
                    await response.drain()
                    
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for session: {session_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
        finally:
            if session_id and session_id in self.active_streams:
                del self.active_streams[session_id]
        
        return response
    
    async def handle_tools_list(self, request):
        """MCP tools/list endpoint"""
        try:
            data = await request.json()
            session_id = request.headers.get('Mcp-Session-Id')
            
            if not session_id or session_id not in self.sessions:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32001,
                        "message": "Invalid session"
                    }
                }, status=400)
            
            tools = self.adapter.get_tools()
            
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "tools": tools
                }
            }
            
            logger.info(f"📋 Tools listed for session: {session_id}")
            return web.json_response(response)
            
        except Exception as e:
            logger.error(f"Tools list error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status=500)
    
    async def handle_tools_call(self, request):
        """MCP tools/call endpoint with streaming support"""
        try:
            data = await request.json()
            session_id = request.headers.get('mcp-session-id')
            
            if not session_id or session_id not in self.sessions:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32001,
                        "message": "Invalid session"
                    }
                }, status=400)
            
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})
            
            if not tool_name:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32602,
                        "message": "Tool name is required"
                    }
                }, status=400)
            
            logger.info(f"🔧 Calling tool: {tool_name} with args: {arguments}")
            
            # Check if this is a streaming tool
            if tool_name in ['search_profile', 'get_collaborators']:
                # Return streaming response
                return await self.handle_streaming_tool_call(request, tool_name, arguments, session_id)
            else:
                # Return immediate response for non-streaming tools
                return await self.handle_immediate_tool_call(request, tool_name, arguments, session_id)
                
        except Exception as e:
            logger.error(f"Tools call error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status=500)
    
    async def handle_streaming_tool_call(self, request, tool_name: str, arguments: Dict, session_id: str):
        """Handle streaming tool calls with real-time updates"""
        
        # Create streaming response
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream; charset=utf-8',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, mcp-session-id',
                'X-Accel-Buffering': 'no'
            }
        )
        await response.prepare(request)
        
        try:
            # Start streaming task
            task = asyncio.create_task(
                self.stream_tool_execution(response, tool_name, arguments, session_id)
            )
            self.streaming_tasks[session_id] = task
            self.active_streams[session_id] = response
        
            # Send initial response
            await self.send_sse_event(response, {
                'status': 'started', 
                'tool': tool_name,
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Wait for completion
            await task
            
        except asyncio.CancelledError:
            logger.info(f"Streaming cancelled for session: {session_id}")
        except Exception as e:
            logger.error(f"Streaming error for session {session_id}: {e}")
            await self.send_sse_event(response, {
                'status': 'error',
                'error': str(e),
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            })
        finally:
            if session_id in self.streaming_tasks:
                del self.streaming_tasks[session_id]
            if session_id in self.active_streams:
                del self.active_streams[session_id]
        
        return response
    
    async def send_sse_event(self, response: web.StreamResponse, data: Dict):
        """Send SSE event with proper formatting"""
        try:
            event_data = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            message = f"data: {event_data}\n\n"
            await response.write(message.encode('utf-8'))
            await response.drain()
        except Exception as e:
            logger.error(f"Failed to send SSE event: {e}")
    
    async def heartbeat_task(self, response: web.StreamResponse, session_id: str):
        """Send periodic heartbeats to keep connection alive"""
        try:
            while session_id in self.active_streams:
                await asyncio.sleep(SSE_HEARTBEAT_INTERVAL)
                if session_id in self.active_streams:
                    await response.write(b": heartbeat\n\n")
                    await response.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Heartbeat failed for session {session_id}: {e}")
    
    async def handle_immediate_tool_call(self, request, tool_name: str, arguments: Dict, session_id: str):
        """Handle immediate tool calls with direct response"""
        try:
            result = await self.adapter.execute_tool(tool_name, arguments)
            
            response = {
                "jsonrpc": "2.0",
                "id": request.json().get("id"),
                "result": result
            }
            
            logger.info(f"✅ {tool_name} completed for session: {session_id}")
            return web.json_response(response)
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": request.json().get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Tool execution failed: {str(e)}"
                }
            }, status=500)
    
    async def stream_tool_execution(self, response, tool_name: str, arguments: Dict, session_id: str):
        """Stream real-time updates during tool execution"""
        
        try:
            if tool_name == 'search_profile':
                await self.stream_real_profile_search(response, arguments, session_id)
            elif tool_name == 'get_collaborators':
                await self.stream_real_collaborator_search(response, arguments, session_id)
            else:
                await response.write(f"data: {json.dumps({'error': f'Unknown streaming tool: {tool_name}'})}\n\n".encode('utf-8'))
                
        except Exception as e:
            error_msg = f"Streaming error: {str(e)}"
            logger.error(error_msg)
            await response.write(f"data: {json.dumps({'error': error_msg})}\n\n".encode('utf-8'))
        
        finally:
            # Send completion signal
            await response.write(f"data: {json.dumps({'status': 'completed', 'tool': tool_name})}\n\n".encode('utf-8'))
    
    async def stream_real_profile_search(self, response, arguments: Dict, session_id: str):
        """Stream real profile search progress using actual scraping"""
        
        name = arguments.get('name', 'Unknown')
        logger.info(f"🔍 Starting REAL profile search for: {name}")
        
        # Generate new scraping session ID for each search
        scraping_session_id = self.generate_session_id()
        logger.info(f"📝 Generated new scraping session ID: {scraping_session_id}")
        
        # Send search started event
        await self.send_sse_event(response, {
            'event': 'search_started',
            'data': {
                'name': name, 
                'scraping_session_id': scraping_session_id,
                'timestamp': datetime.now().isoformat()
            }
        })
        
        # Create session directory
        session_dir = self.base_dir / "public" / "collaborator-sessions" / scraping_session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Send connecting event
        await self.send_sse_event(response, {
            'event': 'progress_update',
            'data': {
                'step': 1,
                'total_steps': 5,
                'message': 'YÖK Akademik platformuna bağlanılıyor...',
                'progress': '20.0%',
                'timestamp': datetime.now().isoformat()
            }
        })
        
        # Start real scraping process
        try:
            # Run the actual scraping script
            scraping_script = self.base_dir / "src" / "tools" / "scrape_main_profile.py"
            
            # Send scraping started event
            event_data = {
                'event': 'progress_update',
                'data': {
                    'step': 2,
                    'total_steps': 5,
                    'message': 'Profil arama başlatılıyor...',
                    'progress': '40.0%',
                    'timestamp': datetime.now().isoformat()
                }
            }
            await response.write(f"data: {json.dumps(event_data)}\n\n".encode('utf-8'))
            await response.drain()
            
            # Start scraping process
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(scraping_script), name, scraping_session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.base_dir
            )
            
            # Send scraping in progress event
            event_data = {
                'event': 'progress_update',
                'data': {
                    'step': 3,
                    'total_steps': 5,
                    'message': 'Profiller taranıyor...',
                    'progress': '60.0%',
                    'timestamp': datetime.now().isoformat()
                }
            }
            await response.write(f"data: {json.dumps(event_data)}\n\n".encode('utf-8'))
            await response.drain()
            
            # Monitor the scraping process in real-time with file watching
            logger.info("🔍 Monitoring scraping process in real-time with file watching...")
            
            # Start file watching for real-time updates
            main_profile_path = session_dir / "main_profile.json"
            last_file_size = 0
            last_modified = 0
            
            # Send real-time updates while scraping
            while True:
                # Check if process is still running
                if process.returncode is not None:
                    break
                
                # Check for file changes
                if main_profile_path.exists():
                    current_size = main_profile_path.stat().st_size
                    current_modified = main_profile_path.stat().st_mtime
                    
                    # If file has changed, read and stream new data
                    if current_size != last_file_size or current_modified != last_modified:
                        try:
                            with open(main_profile_path, 'r', encoding='utf-8') as f:
                                current_data = json.load(f)
                            
                            profiles = current_data.get('profiles', [])
                            total_profiles = current_data.get('total_profiles', 0)
                            
                            # Send incremental update
                            event_data = {
                                'event': 'profiles_update',
                                'data': {
                                    'profiles_found': total_profiles,
                                    'profiles': profiles,
                                    'timestamp': datetime.now().isoformat(),
                                    'message': f'Found {total_profiles} profiles so far...'
                                }
                            }
                            await response.write(f"data: {json.dumps(event_data)}\n\n".encode('utf-8'))
                            await response.drain()
                            
                            logger.info(f"📡 Streamed {total_profiles} profiles in real-time")
                            
                            # Update tracking
                            last_file_size = current_size
                            last_modified = current_modified
                            
                        except Exception as e:
                            logger.warning(f"⚠️  Error reading file: {e}")
                
                # Send heartbeat/progress update
                event_data = {
                    'event': 'scraping_progress',
                    'data': {
                        'message': 'Scraping in progress...',
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(event_data)}\n\n".encode('utf-8'))
                await response.drain()
                
                # Wait a bit before next update
                await asyncio.sleep(1)
            
            # Get final output
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Send processing event
                event_data = {
                    'event': 'progress_update',
                    'data': {
                        'step': 4,
                        'total_steps': 5,
                        'message': 'Sonuçlar işleniyor...',
                        'progress': '80.0%',
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(event_data)}\n\n".encode('utf-8'))
                await response.drain()
                
                # Read the results
                main_profile_path = session_dir / "main_profile.json"
                if main_profile_path.exists():
                    with open(main_profile_path, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                    
                    # Send completion with real results
                    event_data = {
                        'event': 'search_completed',
                        'data': {
                            'profiles_found': result_data.get('total_profiles', 0),
                            'results': result_data.get('profiles', []),
                            'status': result_data.get('status', 'completed'),
                            'scraping_session_id': scraping_session_id,
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                    await response.write(f"data: {json.dumps(event_data)}\n\n".encode('utf-8'))
                    
                    logger.info(f"✅ Real profile search completed: {result_data.get('total_profiles', 0)} profiles found")
                else:
                    # Send error if no results file
                    event_data = {
                        'event': 'search_error',
                        'data': {
                            'error': 'No results file found after scraping',
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                    await response.write(f"data: {json.dumps(event_data)}\n\n".encode('utf-8'))
            else:
                # Send error if scraping failed
                error_output = stderr.decode('utf-8', errors='ignore')
                event_data = {
                    'event': 'search_error',
                    'data': {
                        'error': f'Scraping failed with return code {process.returncode}',
                        'stderr': error_output,
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(event_data)}\n\n".encode('utf-8'))
                
        except Exception as e:
            # Send error event
            await response.write(f"data: {json.dumps({
                'event': 'search_error',
                'data': {
                    'error': f'Scraping error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }
            })}\n\n".encode('utf-8'))
            
            logger.error(f"❌ Profile search error: {e}")
    
    async def stream_real_collaborator_search(self, response, arguments: Dict, session_id: str):
        """Stream real collaborator search progress using actual scraping"""
        
        logger.info(f"👥 Starting REAL collaborator search for session: {session_id}")
        
        # Send search started event
        await response.write(f"data: {json.dumps({
            'event': 'collaborator_search_started',
            'data': {'session_id': session_id, 'timestamp': datetime.now().isoformat()}
        })}\n\n".encode('utf-8'))
        
        # Send connecting event
        await response.write(f"data: {json.dumps({
            'event': 'progress_update',
            'data': {
                'step': 1,
                'total_steps': 4,
                'message': 'YÖK Akademik platformuna bağlanılıyor...',
                'progress': '25.0%',
                'timestamp': datetime.now().isoformat()
            }
        })}\n\n".encode('utf-8'))
        
        try:
            # First, read existing profiles to select one for collaborator search
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            main_profile_path = session_dir / "main_profile.json"
            
            if not main_profile_path.exists():
                await response.write(f"data: {json.dumps({
                    'event': 'search_error',
                    'data': {
                        'error': 'No main profile data found. Please run search_profile first.',
                        'timestamp': datetime.now().isoformat()
                    }
                })}\n\n".encode('utf-8'))
                return
            
            # Read profiles and select the first one for collaborator search
            with open(main_profile_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
                profiles = profile_data.get('profiles', [])
            
            if not profiles:
                await response.write(f"data: {json.dumps({
                    'event': 'search_error',
                    'data': {
                        'error': 'No profiles found in main profile data.',
                        'timestamp': datetime.now().isoformat()
                    }
                })}\n\n".encode('utf-8'))
                return
            
            # Select profile based on user choice (1-based) or default to first
            profile_index = arguments.get('profile_index', 1) - 1  # Convert to 0-based
            if profile_index < 0 or profile_index >= len(profiles):
                profile_index = 0
                logger.warning(f"⚠️  Invalid profile index {arguments.get('profile_index')}, using first profile")
            
            selected_profile = profiles[profile_index]
            profile_url = selected_profile.get('profile_url', '')
            profile_name = selected_profile.get('name', 'Unknown')
            
            logger.info(f"🔍 Selected profile for collaborator search: {profile_name} (index: {profile_index})")
            
            # Send scraping started event
            await response.write(f"data: {json.dumps({
                'event': 'progress_update',
                'data': {
                    'step': 2,
                    'total_steps': 4,
                    'message': f'İşbirlikçi arama başlatılıyor: {profile_name}',
                    'progress': '50.0%',
                    'timestamp': datetime.now().isoformat()
                }
            })}\n\n".encode('utf-8'))
            await response.drain()
            
            # Run the actual collaborator scraping script
            scraping_script = self.base_dir / "src" / "tools" / "scrape_collaborators.py"
            
            # Start scraping process with profile URL
            cmd_args = [sys.executable, str(scraping_script), profile_name, session_id, "--profile-url", profile_url]
            logger.info(f"🔧 Running collaborator scraping with args: {cmd_args}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.base_dir
            )
            
            # Send scraping in progress event
            await response.write(f"data: {json.dumps({
                'event': 'progress_update',
                'data': {
                    'step': 3,
                    'total_steps': 4,
                    'message': 'İşbirlikçiler taranıyor...',
                    'progress': '75.0%',
                    'timestamp': datetime.now().isoformat()
                }
            })}\n\n".encode('utf-8'))
            await response.drain()
            
            # Monitor the scraping process in real-time with file watching
            logger.info("🔍 Monitoring collaborator scraping process in real-time with file watching...")
            
            # Start file watching for real-time updates
            collaborators_path = session_dir / "collaborators.json"
            last_file_size = 0
            last_modified = 0
            
            # Send real-time updates while scraping
            last_collaborator_count = 0  # Track how many collaborators we've already sent
            
            while True:
                # Check if process is still running
                if process.returncode is not None:
                    break
                
                # Check for file changes
                if collaborators_path.exists():
                    current_size = collaborators_path.stat().st_size
                    current_modified = collaborators_path.stat().st_mtime
                    
                    # If file has changed, read and stream new data
                    if current_size != last_file_size or current_modified != last_modified:
                        try:
                            with open(collaborators_path, 'r', encoding='utf-8') as f:
                                current_data = json.load(f)
                            
                            collaborators = current_data.get('collaborator_profiles', [])
                            total_collaborators = len(collaborators)
                            
                            # Only send newly found collaborators
                            if total_collaborators > last_collaborator_count:
                                new_collaborators = collaborators[last_collaborator_count:]
                                
                                # Send incremental update in chunks to avoid "Chunk too big" error
                                chunk_size = 10
                                for i in range(0, len(new_collaborators), chunk_size):
                                    chunk = new_collaborators[i:i + chunk_size]
                                    chunk_data = {
                                        'event': 'collaborators_update',
                                        'data': {
                                            'collaborators_found': total_collaborators,
                                            'collaborators': chunk,
                                            'chunk_start': last_collaborator_count + i + 1,
                                            'chunk_end': last_collaborator_count + i + len(chunk),
                                            'timestamp': datetime.now().isoformat(),
                                            'message': f'Found {total_collaborators} collaborators so far...'
                                        }
                                    }
                                    await response.write(f"data: {json.dumps(chunk_data)}\n\n".encode('utf-8'))
                                    await asyncio.sleep(0.05)  # Small delay between chunks
                                
                                logger.info(f"📡 Streamed {len(new_collaborators)} new collaborators in real-time")
                                
                                # Update tracking
                                last_collaborator_count = total_collaborators
                            
                            # Update file tracking
                            last_file_size = current_size
                            last_modified = current_modified
                            
                        except Exception as e:
                            logger.warning(f"⚠️  Error reading collaborators file: {e}")
                
                # Send heartbeat/progress update
                await response.write(f"data: {json.dumps({
                    'event': 'scraping_progress',
                    'data': {
                        'message': 'Collaborator scraping in progress...',
                        'timestamp': datetime.now().isoformat()
                    }
                })}\n\n".encode('utf-8'))
                await response.drain()
                
                # Wait a bit before next update
                await asyncio.sleep(1)
            
            # Get final output
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Read the results
                session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
                collaborators_path = session_dir / "collaborators.json"
                
                if collaborators_path.exists():
                    with open(collaborators_path, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                    
                    collaborators = result_data.get('collaborator_profiles', [])
                    
                    # Send completion with real results in chunks to avoid "Chunk too big" error
                    total_collaborators = len(collaborators)
                    
                    # First send summary
                    await response.write(f"data: {json.dumps({
                        'event': 'collaborator_search_completed',
                        'data': {
                            'total_collaborators': total_collaborators,
                            'selected_profile': profile_name,
                            'session_id': session_id,
                            'timestamp': datetime.now().isoformat(),
                            'message': f'Found {total_collaborators} collaborators for {profile_name}'
                        }
                    })}\n\n".encode('utf-8'))
                    
                    # Send collaborators in smaller chunks (max 10 per chunk)
                    chunk_size = 10
                    for i in range(0, total_collaborators, chunk_size):
                        chunk = collaborators[i:i + chunk_size]
                        chunk_data = {
                            'event': 'collaborators_chunk',
                            'data': {
                                'chunk_index': i // chunk_size + 1,
                                'total_chunks': (total_collaborators + chunk_size - 1) // chunk_size,
                                'collaborators': chunk,
                                'start_index': i + 1,
                                'end_index': min(i + chunk_size, total_collaborators)
                            }
                        }
                        await response.write(f"data: {json.dumps(chunk_data)}\n\n".encode('utf-8'))
                        
                        # Small delay to prevent overwhelming the client
                        await asyncio.sleep(0.1)
                    
                    logger.info(f"✅ Real collaborator search completed: {len(collaborators)} collaborators found for {profile_name}")
                else:
                    # Send error if no results file
                    await response.write(f"data: {json.dumps({
                        'event': 'search_error',
                        'data': {
                            'error': 'No collaborators file found after scraping',
                            'timestamp': datetime.now().isoformat()
                        }
                    })}\n\n".encode('utf-8'))
            else:
                # Send error if scraping failed
                error_output = stderr.decode('utf-8', errors='ignore')
                await response.write(f"data: {json.dumps({
                    'event': 'search_error',
                    'data': {
                        'error': f'Collaborator scraping failed with return code {process.returncode}',
                        'stderr': error_output,
                        'timestamp': datetime.now().isoformat()
                    }
                })}\n\n".encode('utf-8'))
                
        except Exception as e:
            # Send error event
            await response.write(f"data: {json.dumps({
                'event': 'search_error',
                'data': {
                    'error': f'Collaborator search error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }
            })}\n\n".encode('utf-8'))
            
            logger.error(f"❌ Collaborator search error: {e}")
    
    async def handle_options(self, request):
        """Handle CORS preflight requests"""
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, mcp-session-id',
            'Access-Control-Max-Age': '3600'
        }
        return web.Response(headers=headers)
    
    async def handle_mcp_request(self, request):
        """Main MCP request handler - MCP 2025-03-26 Streamable HTTP"""
        try:
            # Handle GET requests for SSE stream
            if request.method == "GET":
                return await self.handle_sse_stream(request)
            
            # Handle DELETE requests for session termination
            if request.method == "DELETE":
                return await self.handle_session_delete(request)
            
            # Handle OPTIONS requests for CORS
            if request.method == "OPTIONS":
                return await self.handle_options(request)
            
            # Validate Content-Type for POST requests
            content_type = request.headers.get('Content-Type', '')
            if request.method == "POST" and not content_type.startswith('application/json'):
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Content-Type must be application/json"
                    }
                }, status=400)
            
            # Parse JSON for POST requests
            try:
                data = await request.json()
            except Exception as json_error:
                logger.error(f"JSON parse error: {json_error}")
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(json_error)}"
                    }
                }, status=400, headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type, Mcp-Session-Id',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE'
                })
            
            # Handle batch requests (array of requests)
            if isinstance(data, list):
                return await self.handle_batch_request(request, data)
            
            # Single request handling
            method = data.get("method")
            session_id = request.headers.get('Mcp-Session-Id')
            
            logger.info(f"📨 MCP Request: {method} (Session: {session_id})")
            
            # Check if streaming request contains JSON-RPC requests
            accept_header = request.headers.get('Accept', '')
            wants_streaming = 'text/event-stream' in accept_header
            
            if method == "initialize":
                return await self.handle_initialize(request)
            elif method == "tools/list":
                return await self.handle_tools_list(request)
            elif method == "tools/call":
                # Tools/call should support streaming response
                if wants_streaming:
                    return await self.handle_streaming_tools_call(request, data, session_id)
                else:
                    return await self.handle_tools_call(request)
            elif method == "logging/setLevel":
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "result": {}
                }, headers=self.get_cors_headers())
            else:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }, status=404, headers=self.get_cors_headers())
                
        except Exception as e:
            logger.error(f"MCP request error: {e}")
            import traceback
            traceback.print_exc()
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status=500, headers=self.get_cors_headers())
    
    def get_cors_headers(self):
        """Get standard CORS headers for MCP 2025-03-26"""
        return {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type, Mcp-Session-Id, Last-Event-ID',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE',
            'Access-Control-Expose-Headers': 'Mcp-Session-Id'
        }
    
    async def handle_session_delete(self, request):
        """Handle session termination - MCP 2025-03-26"""
        session_id = request.headers.get('Mcp-Session-Id')
        
        if not session_id:
            return web.json_response({
                "error": "Mcp-Session-Id header required"
            }, status=400, headers=self.get_cors_headers())
        
        # Remove session
        if session_id in self.sessions:
            del self.sessions[session_id]
        
        # Close any active streams
        if session_id in self.active_streams:
            del self.active_streams[session_id]
        
        logger.info(f"🗑️ Session terminated: {session_id}")
        return web.Response(status=204, headers=self.get_cors_headers())
    
    async def handle_batch_request(self, request, data_array):
        """Handle batch JSON-RPC requests - MCP 2025-03-26"""
        responses = []
        
        for item in data_array:
            if not isinstance(item, dict):
                continue
                
            method = item.get("method")
            if method == "initialize":
                resp = await self.handle_initialize(request)
            elif method == "tools/list":
                resp = await self.handle_tools_list(request)
            elif method == "tools/call":
                resp = await self.handle_tools_call(request)
            else:
                responses.append({
                    "jsonrpc": "2.0",
                    "id": item.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                })
                continue
            
            if hasattr(resp, 'body'):
                # Extract JSON from response
                try:
                    body_text = resp.body.decode('utf-8')
                    responses.append(json.loads(body_text))
                except:
                    responses.append({
                        "jsonrpc": "2.0",
                        "id": item.get("id"),
                        "error": {"code": -32603, "message": "Response parse error"}
                    })
        
        return web.json_response(responses, headers=self.get_cors_headers())
    
    async def handle_streaming_tools_call(self, request, data, session_id):
        """Handle streaming tools/call with JSON response - MCP 2025-03-26"""
        tool_name = data.get("params", {}).get("name")
        arguments = data.get("params", {}).get("arguments", {})
        
        logger.info(f"🔧 Tool call: {tool_name}")
        
        try:
            # Execute tool synchronously for Inspector compatibility
            if tool_name == "search_profile":
                name = arguments.get("name", "")
                
                # Generate new scraping session ID
                scraping_session_id = self.generate_session_id()
                
                # Start background scraping (non-blocking)
                asyncio.create_task(self.run_profile_scraping_sync(scraping_session_id, name))
                
                # Return immediate response
                result_text = f"🔍 Profil araması başlatıldı: '{name}'\n🆔 Scraping Session ID: {scraping_session_id}\n\n"
                result_text += "⚡ Scraping arka planda çalışıyor...\n"
                result_text += "📋 Sonuçları görmek için birkaç saniye bekleyip get_profile tool'unu kullanın\n\n"
                result_text += "💡 İpucu: get_profile ile profil listesini görün\n"
                result_text += "👥 İpucu: get_collaborators ile işbirlikçi araması yapın"
                
            elif tool_name == "get_profile":
                profile_index = arguments.get("profile_index", 1)
                profile_data = await self.get_profile_data(session_id, profile_index)
                if "error" in profile_data:
                    # Check if it's because scraping hasn't completed yet
                    session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
                    if session_dir.exists():
                        result_text = f"⏳ Scraping henüz tamamlanmamış olabilir...\n\n"
                        result_text += f"❌ Hata: {profile_data['error']}\n\n"
                        result_text += "💡 Birkaç saniye bekleyip tekrar deneyin\n"
                        result_text += f"📁 Session: {session_id}"
                    else:
                        result_text = f"❌ Hata: {profile_data['error']}"
                else:
                    profile = profile_data["profile"]
                    result_text = f"""📋 Profil Detayları (Index: {profile_index})

👤 İsim: {profile.get('name', 'N/A')}
🎓 Ünvan: {profile.get('title', 'N/A')}
🏫 Kurum: {profile.get('education', 'N/A')}
📧 Email: {profile.get('email', 'N/A')}
🔬 Alan: {profile.get('field', 'N/A')}
📚 Uzmanlık: {profile.get('speciality', 'N/A')}
🔑 Anahtar Kelimeler: {profile.get('keywords', 'N/A')}
🆔 Author ID: {profile.get('author_id', 'N/A')}
🔗 Profil URL: {profile.get('profile_url', 'N/A')}

📊 Toplam Profil Sayısı: {profile_data.get('total_profiles', 0)}

💡 İşbirlikçi araması için: get_collaborators {profile_index}"""
                
            elif tool_name == "get_collaborators":
                profile_index = arguments.get("profile_index", 1)
                
                # Start background collaborator scraping (non-blocking)
                asyncio.create_task(self.run_collaborator_scraping_sync(session_id, profile_index))
                
                # Return immediate response
                result_text = f"👥 İşbirlikçi araması başlatıldı (Profil Index: {profile_index})\n🆔 Session ID: {session_id}\n\n"
                result_text += "⚡ Collaborator scraping arka planda çalışıyor...\n"
                result_text += "📋 Bu işlem 1-2 dakika sürebilir\n\n"
                result_text += "💡 Sonuçlar hazır olduğunda session dosyalarında görünecek\n"
                result_text += f"📁 Konum: public/collaborator-sessions/{session_id}/collaborators.json"
                
            else:
                result_text = f"❌ Bilinmeyen tool: {tool_name}"
            
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text
                        }
                    ]
                }
            }, headers=self.get_cors_headers())
            
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Tool execution error: {str(e)}"
                }
            }, headers=self.get_cors_headers())
    
    async def background_profile_search(self, session_id: str, name: str):
        """Background task for profile search"""
        try:
            logger.info(f"🔍 Starting background profile search for: {name}")
            # Create a dummy response for streaming (will be used by SSE clients)
            # Tool execution completes immediately, streaming happens in background
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Run the actual scraping
            await self.run_profile_scraping(session_id, name)
            
        except Exception as e:
            logger.error(f"Background profile search error: {e}")
    
    async def background_collaborator_search(self, session_id: str, profile_index: int):
        """Background task for collaborator search"""
        try:
            logger.info(f"👥 Starting background collaborator search for profile {profile_index}")
            # Run the actual scraping
            await self.run_collaborator_scraping(session_id, profile_index)
            
        except Exception as e:
            logger.error(f"Background collaborator search error: {e}")
    
    async def run_profile_scraping(self, session_id: str, name: str):
        """Run actual profile scraping"""
        try:
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            script_path = self.base_dir / "src" / "tools" / "scrape_main_profile.py"
            
            # Execute scraping script
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path), name, session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_dir)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Profile scraping completed for: {name}")
            else:
                logger.error(f"❌ Profile scraping failed: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Profile scraping error: {e}")
    
    async def run_collaborator_scraping(self, session_id: str, profile_index: int):
        """Run actual collaborator scraping"""
        try:
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            script_path = self.base_dir / "src" / "tools" / "scrape_collaborators.py"
            
            # Execute scraping script
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path), str(profile_index), session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_dir)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Collaborator scraping completed for profile {profile_index}")
            else:
                logger.error(f"❌ Collaborator scraping failed: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"Collaborator scraping error: {e}")
    
    async def run_profile_scraping_sync(self, session_id: str, name: str):
        """Run profile scraping synchronously and wait for completion"""
        try:
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            script_path = self.base_dir / "src" / "tools" / "scrape_main_profile.py"
            
            logger.info(f"🔍 Starting synchronous profile scraping for: {name}")
            
            # Execute scraping script and wait for completion
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path), name, session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_dir)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Synchronous profile scraping completed for: {name}")
            else:
                error_output = stderr.decode('utf-8', errors='ignore')
                logger.error(f"❌ Synchronous profile scraping failed: {error_output}")
                raise Exception(f"Scraping failed with return code {process.returncode}: {error_output}")
                
        except Exception as e:
            logger.error(f"Synchronous profile scraping error: {e}")
            raise
    
    async def run_collaborator_scraping_sync(self, session_id: str, profile_index: int):
        """Run collaborator scraping synchronously and wait for completion"""
        try:
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            script_path = self.base_dir / "src" / "tools" / "scrape_collaborators.py"
            
            # First, read the selected profile from main_profile.json
            main_profile_path = session_dir / "main_profile.json"
            if not main_profile_path.exists():
                raise Exception(f"Main profile file not found: {main_profile_path}")
            
            with open(main_profile_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
                profiles = profile_data.get('profiles', [])
            
            if not profiles:
                raise Exception("No profiles found in main profile data")
            
            # Convert 1-based index to 0-based and validate
            array_index = profile_index - 1
            if array_index < 0 or array_index >= len(profiles):
                raise Exception(f"Invalid profile index {profile_index}. Available: 1-{len(profiles)}")
            
            selected_profile = profiles[array_index]
            profile_name = selected_profile.get('name', 'Unknown')
            profile_url = selected_profile.get('profile_url', '')
            
            if not profile_url:
                raise Exception(f"No profile URL found for profile: {profile_name}")
            
            logger.info(f"👥 Starting synchronous collaborator scraping for profile {profile_index}: {profile_name}")
            
            # Execute scraping script with correct parameters
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path), profile_name, session_id, "--profile-url", profile_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_dir)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Synchronous collaborator scraping completed for profile {profile_index}")
            else:
                error_output = stderr.decode('utf-8', errors='ignore')
                logger.error(f"❌ Synchronous collaborator scraping failed: {error_output}")
                raise Exception(f"Collaborator scraping failed with return code {process.returncode}: {error_output}")
                
        except Exception as e:
            logger.error(f"Synchronous collaborator scraping error: {e}")
            raise
    
    async def get_session_status(self, session_id: str):
        """Get session status"""
        try:
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            
            if not session_dir.exists():
                return {"status": "not_found", "message": "Session not found"}
            
            main_profile_file = session_dir / "main_profile.json"
            collaborators_file = session_dir / "collaborators.json"
            
            status = {
                "session_id": session_id,
                "profile_search": "completed" if main_profile_file.exists() else "not_started",
                "collaborator_search": "completed" if collaborators_file.exists() else "not_started"
            }
            
            if main_profile_file.exists():
                with open(main_profile_file, 'r', encoding='utf-8') as f:
                    profile_data = json.load(f)
                    status["total_profiles"] = profile_data.get("total_profiles", 0)
            
            if collaborators_file.exists():
                with open(collaborators_file, 'r', encoding='utf-8') as f:
                    collab_data = json.load(f)
                    status["total_collaborators"] = collab_data.get("total_profiles", 0)
            
            return status
            
        except Exception as e:
            logger.error(f"Get session status error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_profile_data(self, session_id: str, profile_index: int):
        """Get specific profile data"""
        try:
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            main_profile_file = session_dir / "main_profile.json"
            
            if not main_profile_file.exists():
                return {"error": "No profile data found. Run search_profile first."}
            
            with open(main_profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
                profiles = profile_data.get("profiles", [])
            
            if profile_index < 1 or profile_index > len(profiles):
                return {"error": f"Invalid profile index. Available: 1-{len(profiles)}"}
            
            selected_profile = profiles[profile_index - 1]
            return {
                "profile_index": profile_index,
                "profile": selected_profile,
                "total_profiles": len(profiles)
            }
            
        except Exception as e:
            logger.error(f"Get profile data error: {e}")
            return {"error": str(e)}

@web.middleware
async def cors_middleware(request, handler):
    """CORS middleware for all requests"""
    if request.method == "OPTIONS":
        # Handle preflight requests
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE',
            'Access-Control-Allow-Headers': 'Content-Type, Mcp-Session-Id, Last-Event-ID, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return web.Response(headers=headers)
    
    # Process the request
    response = await handler(request)
    
    # Add CORS headers to response
    response.headers.update({
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE',
        'Access-Control-Allow-Headers': 'Content-Type, Mcp-Session-Id, Last-Event-ID, Authorization',
        'Access-Control-Expose-Headers': 'Mcp-Session-Id'
    })
    
    return response

def run_server(app, host="0.0.0.0", port=8000):
    """Run the MCP server with proper configuration"""
    try:
        web.run_app(
            app, 
            host=host, 
            port=port,
            access_log=logger,
            shutdown_timeout=30
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

def create_app():
    """Create web application with CORS and optimization"""
    # Create middleware stack
    middlewares = []
    if CORS_ENABLED:
        middlewares.append(cors_middleware)
    
    app = web.Application(middlewares=middlewares)
    mcp_server = RealScrapingMCPProtocolServer()
    
    # MCP Protocol endpoints - Single endpoint for all methods (MCP 2025-03-26)
    app.router.add_post("/mcp", mcp_server.handle_mcp_request)
    app.router.add_get("/mcp", mcp_server.handle_mcp_request)
    app.router.add_options("/mcp", mcp_server.handle_mcp_request)
    app.router.add_delete("/mcp", mcp_server.handle_mcp_request)
    
    # Health check endpoint
    async def health_check_handler(request):
        try:
            return web.json_response({
                "status": "ok",
                "service": "YOK Academic MCP Real Scraping Server",
                "version": "3.0.0",
                "protocol": "MCP 2024-11-05",
                "environment": os.getenv("NODE_ENV", "development"),
                "features": [
                    "Real-time streaming", 
                    "Real scraping integration", 
                    "Progress updates", 
                    "Event-driven responses",
                    "CORS enabled" if CORS_ENABLED else "CORS disabled",
                    f"Max concurrent sessions: {MAX_CONCURRENT_SESSIONS}"
                ],
                "active_sessions": len(mcp_server.sessions),
                "active_streams": len(mcp_server.active_streams),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)
    
    app.router.add_get("/health", health_check_handler)
    
    # Simple ready check for Smithery
    async def ready_handler(request):
        return web.Response(text="OK", status=200)
    
    app.router.add_get("/ready", ready_handler)
    app.router.add_get("/", ready_handler)  # Root endpoint
    
    # MCP test endpoint
    async def mcp_test_handler(request):
        return web.json_response({
            "status": "ok",
            "mcp_server": "ready",
            "endpoint": "/mcp",
            "methods": ["GET", "POST", "OPTIONS"],
            "test_initialize": {
                "method": "POST",
                "url": "/mcp",
                "body": {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {}},
                        "clientInfo": {"name": "TestClient", "version": "1.0.0"}
                    }
                }
            }
        })
    
    app.router.add_get("/mcp/test", mcp_test_handler)
    
    # Metrics endpoint for monitoring
    async def metrics_handler(request):
        return web.json_response({
            "sessions": {
                "total": len(mcp_server.sessions),
                "active_streams": len(mcp_server.active_streams),
                "max_concurrent": MAX_CONCURRENT_SESSIONS
            },
            "server": {
                "uptime": datetime.now().isoformat(),
                "version": "3.0.0",
                "environment": os.getenv("NODE_ENV", "development")
            }
        })
    
    app.router.add_get("/metrics", metrics_handler)
    
    return app

if __name__ == "__main__":
    try:
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Test Chrome availability early
        chrome_bin = os.getenv("CHROME_BIN", "/usr/bin/chromium")
        if not os.path.exists(chrome_bin):
            logger.warning(f"Chrome binary not found at {chrome_bin}")
        
        app = create_app()
        logger.info("=" * 80)
        logger.info("YOK Akademik Asistani - MCP Real Scraping Server v3.0.0")
        logger.info("=" * 80)
        logger.info(f"Server: http://{SERVER_HOST}:{SERVER_PORT}")
        logger.info(f"MCP Endpoint: http://{SERVER_HOST}:{SERVER_PORT}/mcp")
        logger.info(f"Health Check: http://{SERVER_HOST}:{SERVER_PORT}/ready")
        logger.info(f"Metrics: http://{SERVER_HOST}:{SERVER_PORT}/metrics")
        logger.info("=" * 80)
        logger.info(f"Environment: {os.getenv('NODE_ENV', 'development')}")
        logger.info(f"Real-time streaming: {HEADLESS_MODE and 'Enabled' or 'Development Mode'}")
        logger.info(f"CORS: {CORS_ENABLED and 'Enabled' or 'Disabled'}")
        logger.info(f"Max Sessions: {MAX_CONCURRENT_SESSIONS}")
        logger.info(f"Heartbeat: {SSE_HEARTBEAT_INTERVAL}s")
        logger.info(f"Chrome: {chrome_bin}")
        logger.info("=" * 80)
        logger.info("Server starting...")
        
        run_server(app, SERVER_HOST, SERVER_PORT)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server startup error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
