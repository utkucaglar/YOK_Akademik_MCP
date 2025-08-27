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
from aiohttp_cors import setup as cors_setup, ResourceOptions
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

if log_format == "structured":
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.getenv("LOG_FILE_PATH", "logs/mcp_server.log"), mode='a')
        ]
    )
else:
    logging.basicConfig(level=getattr(logging, log_level))

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
            logger.info(f"📁 Directory ensured: {dir_path}")
        
    def generate_session_id(self):
        """Generate a readable and sortable session ID"""
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        # Add milliseconds for uniqueness
        milliseconds = int(time.time() * 1000) % 1000
        return f"session_{timestamp}_{milliseconds:03d}"
    
    async def handle_initialize(self, request):
        """MCP initialize endpoint"""
        try:
            data = await request.json()
            session_id = self.generate_session_id()
            
            # Session'ı kaydet
            self.sessions[session_id] = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "client_info": data.get("params", {}).get("clientInfo", {}),
                "status": "initialized"
            }
            
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
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
            
            # Session ID'yi header'a ekle
            resp = web.json_response(response)
            resp.headers['mcp-session-id'] = session_id
            logger.info(f"✅ Session initialized: {session_id}")
            return resp
            
        except Exception as e:
            logger.error(f"Initialize error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status=500)
    
    async def handle_tools_list(self, request):
        """MCP tools/list endpoint"""
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
        
        # Check session limits
        async with self.session_semaphore:
            # Create streaming response with optimized headers
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
                    'X-Accel-Buffering': 'no',  # Disable nginx buffering
                    'Transfer-Encoding': 'chunked'
                }
            )
            await response.prepare(request)
        
        # Start streaming task
        task = asyncio.create_task(
            self.stream_tool_execution(response, tool_name, arguments, session_id)
        )
        self.streaming_tasks[session_id] = task
        self.active_streams[session_id] = response
        
        try:
            # Send initial response with heartbeat setup
            await self.send_sse_event(response, {
                'status': 'started', 
                'tool': tool_name,
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            })
            
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self.heartbeat_task(response, session_id)
            )
            
            # Keep connection alive until task completes
            await task
            heartbeat_task.cancel()
            
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
        
        # Send search started event
        await self.send_sse_event(response, {
            'event': 'search_started',
            'data': {'name': name, 'timestamp': datetime.now().isoformat()}
        })
        
        # Create session directory
        session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
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
            await response.write(f"data: {json.dumps({
                'event': 'progress_update',
                'data': {
                    'step': 2,
                    'total_steps': 5,
                    'message': 'Profil arama başlatılıyor...',
                    'progress': '40.0%',
                    'timestamp': datetime.now().isoformat()
                }
            })}\n\n".encode('utf-8'))
            await response.drain()
            
            # Start scraping process
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(scraping_script), name, session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.base_dir
            )
            
            # Send scraping in progress event
            await response.write(f"data: {json.dumps({
                'event': 'progress_update',
                'data': {
                    'step': 3,
                    'total_steps': 5,
                    'message': 'Profiller taranıyor...',
                    'progress': '60.0%',
                    'timestamp': datetime.now().isoformat()
                }
            })}\n\n".encode('utf-8'))
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
                            await response.write(f"data: {json.dumps({
                                'event': 'profiles_update',
                                'data': {
                                    'profiles_found': total_profiles,
                                    'profiles': profiles,
                                    'timestamp': datetime.now().isoformat(),
                                    'message': f'Found {total_profiles} profiles so far...'
                                }
                            })}\n\n".encode('utf-8'))
                            await response.drain()
                            
                            logger.info(f"📡 Streamed {total_profiles} profiles in real-time")
                            
                            # Update tracking
                            last_file_size = current_size
                            last_modified = current_modified
                            
                        except Exception as e:
                            logger.warning(f"⚠️  Error reading file: {e}")
                
                # Send heartbeat/progress update
                await response.write(f"data: {json.dumps({
                    'event': 'scraping_progress',
                    'data': {
                        'message': 'Scraping in progress...',
                        'timestamp': datetime.now().isoformat()
                    }
                })}\n\n".encode('utf-8'))
                await response.drain()
                
                # Wait a bit before next update
                await asyncio.sleep(1)
            
            # Get final output
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Send processing event
                await response.write(f"data: {json.dumps({
                    'event': 'progress_update',
                    'data': {
                        'step': 4,
                        'total_steps': 5,
                        'message': 'Sonuçlar işleniyor...',
                        'progress': '80.0%',
                        'timestamp': datetime.now().isoformat()
                    }
                })}\n\n".encode('utf-8'))
                await response.drain()
                
                # Read the results
                main_profile_path = session_dir / "main_profile.json"
                if main_profile_path.exists():
                    with open(main_profile_path, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                    
                    # Send completion with real results
                    await response.write(f"data: {json.dumps({
                        'event': 'search_completed',
                        'data': {
                            'profiles_found': result_data.get('total_profiles', 0),
                            'results': result_data.get('profiles', []),
                            'status': result_data.get('status', 'completed'),
                            'timestamp': datetime.now().isoformat()
                        }
                    })}\n\n".encode('utf-8'))
                    
                    logger.info(f"✅ Real profile search completed: {result_data.get('total_profiles', 0)} profiles found")
                else:
                    # Send error if no results file
                    await response.write(f"data: {json.dumps({
                        'event': 'search_error',
                        'data': {
                            'error': 'No results file found after scraping',
                            'timestamp': datetime.now().isoformat()
                        }
                    })}\n\n".encode('utf-8'))
            else:
                # Send error if scraping failed
                error_output = stderr.decode('utf-8', errors='ignore')
                await response.write(f"data: {json.dumps({
                    'event': 'search_error',
                    'data': {
                        'error': f'Scraping failed with return code {process.returncode}',
                        'stderr': error_output,
                        'timestamp': datetime.now().isoformat()
                    }
                })}\n\n".encode('utf-8'))
                
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
            
            # Select profile based on user choice or default to first
            profile_index = arguments.get('profile_index', 0)
            if profile_index >= len(profiles):
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
        """Main MCP request handler"""
        try:
            data = await request.json()
            method = data.get("method")
            
            if method == "initialize":
                return await self.handle_initialize(request)
            elif method == "tools/list":
                return await self.handle_tools_list(request)
            elif method == "tools/call":
                return await self.handle_tools_call(request)
            elif method == "logging/setLevel":
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "result": {}
                })
            else:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }, status=404)
                
        except Exception as e:
            logger.error(f"MCP request error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }, status=400)

def create_app():
    """Create web application with CORS and optimization"""
    app = web.Application()
    mcp_server = RealScrapingMCPProtocolServer()
    
    # CORS setup
    if CORS_ENABLED:
        cors = cors_setup(app, defaults={
            "*": ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
    
    # MCP Protocol endpoints
    app.router.add_post("/mcp", mcp_server.handle_mcp_request)
    app.router.add_get("/mcp", mcp_server.handle_mcp_request)
    app.router.add_options("/mcp", mcp_server.handle_options)
    
    # Health check endpoint
    async def health_check_handler(request):
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
    
    app.router.add_get("/health", health_check_handler)
    
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
    
    # Add CORS to all routes if enabled
    if CORS_ENABLED:
        for route in list(app.router.routes()):
            cors.add(route)
    
    return app

if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    app = create_app()
    logger.info("=" * 80)
    logger.info("🎓 YÖK Akademik Asistanı - MCP Real Scraping Server v3.0.0")
    logger.info("=" * 80)
    logger.info(f"🌐 Server: http://{SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"🔧 MCP Endpoint: http://{SERVER_HOST}:{SERVER_PORT}/mcp")
    logger.info(f"❤️  Health Check: http://{SERVER_HOST}:{SERVER_PORT}/health")
    logger.info(f"📊 Metrics: http://{SERVER_HOST}:{SERVER_PORT}/metrics")
    logger.info("=" * 80)
    logger.info(f"🚀 Environment: {os.getenv('NODE_ENV', 'development')}")
    logger.info(f"📡 Real-time streaming: {HEADLESS_MODE and 'Enabled' or 'Development Mode'}")
    logger.info(f"🔒 CORS: {CORS_ENABLED and 'Enabled' or 'Disabled'}")
    logger.info(f"👥 Max Sessions: {MAX_CONCURRENT_SESSIONS}")
    logger.info(f"💓 Heartbeat: {SSE_HEARTBEAT_INTERVAL}s")
    logger.info("=" * 80)
    logger.info("✅ Server ready for MCP connections!")
    logger.info("=" * 80)
    
    try:
        web.run_app(
            app, 
            host=SERVER_HOST, 
            port=SERVER_PORT,
            access_log=logger,
            shutdown_timeout=60,
            keepalive_timeout=30,
            client_timeout=60
        )
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        sys.exit(1)
