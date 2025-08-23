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

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_adapter import YOKAcademicMCPAdapter

# Logging
logging.basicConfig(level=logging.INFO)
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
        self.base_dir = Path(__file__).parent
        
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
                        "tools": {
                            "listChanged": False
                        },
                        "logging": {},
                        "experimental": {}
                    },
                    "serverInfo": {
                        "name": "YOK Academic MCP Real Scraping Server",
                        "version": "3.0.0"
                    },
                    "instructions": "Use this server to search and analyze YÖK Academic profiles and collaborations."
                }
            }
            
            # Session ID'yi header'a ekle
            resp = web.json_response(response)
            resp.headers['mcp-session-id'] = session_id
            logger.info(f"✅ MCP Session initialized: {session_id}")
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
            
            # Smithery compatibility: Don't require session for tools list
            tools = self.adapter.get_tools()
            
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "tools": tools
                }
            }
            
            logger.info(f"📋 Tools listed for MCP scan")
            return web.json_response(response)
            
        except Exception as e:
            logger.error(f"Tools list error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
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
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
        await response.prepare(request)
        
        # Start streaming task
        task = asyncio.create_task(
            self.stream_tool_execution(response, tool_name, arguments, session_id)
        )
        self.streaming_tasks[session_id] = task
        
        try:
            # Send initial response
            await response.write(f"data: {json.dumps({'status': 'started', 'tool': tool_name})}\n\n".encode('utf-8'))
            
            # Keep connection alive until task completes
            await task
            
        except asyncio.CancelledError:
            logger.info(f"Streaming cancelled for session: {session_id}")
        finally:
            if session_id in self.streaming_tasks:
                del self.streaming_tasks[session_id]
        
        return response
    
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
        data = {
            'event': 'search_started',
            'data': {'name': name, 'timestamp': datetime.now().isoformat()}
        }
        await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
        await response.drain()
        
        # Create session directory
        session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Send connecting event
        data = {
            'event': 'progress_update',
            'data': {
                'step': 1,
                'total_steps': 5,
                'message': 'YÖK Akademik platformuna bağlanılıyor...',
                'progress': '20.0%',
                'timestamp': datetime.now().isoformat()
            }
        }
        await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
        await response.drain()
        
        # Start real scraping process
        try:
            # Run the actual scraping script
            scraping_script = self.base_dir / "src" / "tools" / "scrape_main_profile.py"
            
            # Send scraping started event
            data = {
                'event': 'progress_update',
                'data': {
                    'step': 2,
                    'total_steps': 5,
                    'message': 'Profil arama başlatılıyor...',
                    'progress': '40.0%',
                    'timestamp': datetime.now().isoformat()
                }
            }
            await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
            await response.drain()
            
            # Start scraping process
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(scraping_script), name, session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.base_dir
            )
            
            # Send scraping in progress event
            data = {
                'event': 'progress_update',
                'data': {
                    'step': 3,
                    'total_steps': 5,
                    'message': 'Profiller taranıyor...',
                    'progress': '60.0%',
                    'timestamp': datetime.now().isoformat()
                }
            }
            await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
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
                            data = {
                                'event': 'profiles_update',
                                'data': {
                                    'profiles_found': total_profiles,
                                    'profiles': profiles,
                                    'timestamp': datetime.now().isoformat(),
                                    'message': f'Found {total_profiles} profiles so far...'
                                }
                            }
                            await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                            await response.drain()
                            
                            logger.info(f"📡 Streamed {total_profiles} profiles in real-time")
                            
                            # Update tracking
                            last_file_size = current_size
                            last_modified = current_modified
                            
                        except Exception as e:
                            logger.warning(f"⚠️  Error reading file: {e}")
                
                # Send heartbeat/progress update
                data = {
                    'event': 'scraping_progress',
                    'data': {
                        'message': 'Scraping in progress...',
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                await response.drain()
                
                # Wait a bit before next update
                await asyncio.sleep(1)
            
            # Get final output
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Send processing event
                data = {
                    'event': 'progress_update',
                    'data': {
                        'step': 4,
                        'total_steps': 5,
                        'message': 'Sonuçlar işleniyor...',
                        'progress': '80.0%',
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                await response.drain()
                
                # Read the results
                main_profile_path = session_dir / "main_profile.json"
                if main_profile_path.exists():
                    with open(main_profile_path, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                    
                    # Send completion with real results
                    data = {
                        'event': 'search_completed',
                        'data': {
                            'profiles_found': result_data.get('total_profiles', 0),
                            'results': result_data.get('profiles', []),
                            'status': result_data.get('status', 'completed'),
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                    await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                    
                    logger.info(f"✅ Real profile search completed: {result_data.get('total_profiles', 0)} profiles found")
                else:
                    # Send error if no results file
                    data = {
                        'event': 'search_error',
                        'data': {
                            'error': 'No results file found after scraping',
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                    await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
            else:
                # Send error if scraping failed
                error_output = stderr.decode('utf-8', errors='ignore')
                data = {
                    'event': 'search_error',
                    'data': {
                        'error': f'Scraping failed with return code {process.returncode}',
                        'stderr': error_output,
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                
        except Exception as e:
            # Send error event
            data = {
                'event': 'search_error',
                'data': {
                    'error': f'Scraping error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }
            }
            await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
            
            logger.error(f"❌ Profile search error: {e}")
    
    async def stream_real_collaborator_search(self, response, arguments: Dict, session_id: str):
        """Stream real collaborator search progress using actual scraping"""
        
        logger.info(f"👥 Starting REAL collaborator search for session: {session_id}")
        
        # Send search started event
        data = {
            'event': 'collaborator_search_started',
            'data': {'session_id': session_id, 'timestamp': datetime.now().isoformat()}
        }
        await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
        
        # Send connecting event
        data = {
            'event': 'progress_update',
            'data': {
                'step': 1,
                'total_steps': 4,
                'message': 'YÖK Akademik platformuna bağlanılıyor...',
                'progress': '25.0%',
                'timestamp': datetime.now().isoformat()
            }
        }
        await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
        
        try:
            # First, read existing profiles to select one for collaborator search
            session_dir = self.base_dir / "public" / "collaborator-sessions" / session_id
            main_profile_path = session_dir / "main_profile.json"
            
            if not main_profile_path.exists():
                data = {
                    'event': 'search_error',
                    'data': {
                        'error': 'No main profile data found. Please run search_profile first.',
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                return
            
            # Read profiles and select the first one for collaborator search
            with open(main_profile_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
                profiles = profile_data.get('profiles', [])
            
            if not profiles:
                data = {
                    'event': 'search_error',
                    'data': {
                        'error': 'No profiles found in main profile data.',
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
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
            data = {
                'event': 'progress_update',
                'data': {
                    'step': 2,
                    'total_steps': 4,
                    'message': f'İşbirlikçi arama başlatılıyor: {profile_name}',
                    'progress': '50.0%',
                    'timestamp': datetime.now().isoformat()
                }
            }
            await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
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
            data = {
                'event': 'progress_update',
                'data': {
                    'step': 3,
                    'total_steps': 4,
                    'message': 'İşbirlikçiler taranıyor...',
                    'progress': '75.0%',
                    'timestamp': datetime.now().isoformat()
                }
            }
            await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
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
                data = {
                    'event': 'scraping_progress',
                    'data': {
                        'message': 'Collaborator scraping in progress...',
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
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
                    data = {
                        'event': 'collaborator_search_completed',
                        'data': {
                            'total_collaborators': total_collaborators,
                            'selected_profile': profile_name,
                            'session_id': session_id,
                            'timestamp': datetime.now().isoformat(),
                            'message': f'Found {total_collaborators} collaborators for {profile_name}'
                        }
                    }
                    await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                    
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
                    data = {
                        'event': 'search_error',
                        'data': {
                            'error': 'No collaborators file found after scraping',
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                    await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
            else:
                # Send error if scraping failed
                error_output = stderr.decode('utf-8', errors='ignore')
                data = {
                    'event': 'search_error',
                    'data': {
                        'error': f'Collaborator scraping failed with return code {process.returncode}',
                        'stderr': error_output,
                        'timestamp': datetime.now().isoformat()
                    }
                }
                await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
                
        except Exception as e:
            # Send error event
            data = {
                'event': 'search_error',
                'data': {
                    'error': f'Collaborator search error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                }
            }
            await response.write(f"data: {json.dumps(data)}\n\n".encode('utf-8'))
            
            logger.error(f"❌ Collaborator search error: {e}")
    
    async def handle_mcp_request(self, request):
        """Main MCP request handler"""
        try:
            if request.method == "GET":
                # GET request için MCP server capabilities döndür
                return web.json_response({
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {
                                "listChanged": False
                            },
                            "logging": {},
                            "experimental": {}
                        },
                        "serverInfo": {
                            "name": "YOK Academic MCP Real Scraping Server",
                            "version": "3.0.0"
                        },
                        "instructions": "YÖK Academic research and collaboration analysis server"
                    }
                })
            
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
            elif method == "notifications/initialized":
                # MCP notification - no response needed for notifications per JSON-RPC spec
                logger.info("📡 Received notifications/initialized from client")
                if data.get("id") is not None:
                    # If there's an ID, it's a request not a notification
                    return web.json_response({
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {}
                    })
                else:
                    # True notification - no response
                    return web.Response(status=204)  # No content
            elif method.startswith("notifications/"):
                # Handle other notifications
                logger.info(f"📡 Received notification: {method}")
                if data.get("id") is not None:
                    return web.json_response({
                        "jsonrpc": "2.0", 
                        "id": data.get("id"),
                        "result": {}
                    })
                else:
                    return web.Response(status=204)
            else:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }, status=404)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }, status=400)
        except Exception as e:
            logger.error(f"MCP request error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status=500)

def create_app():
    """Create web application"""
    # CORS middleware for Smithery compatibility
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            # Handle OPTIONS preflight requests
            if request.method == 'OPTIONS':
                response = web.Response(status=200)
            else:
                try:
                    response = await handler(request)
                except web.HTTPException as e:
                    # Re-raise HTTP exceptions (like 404)
                    response = web.Response(status=e.status, text=str(e))
                except Exception as e:
                    # Handle any unhandled exceptions
                    logger.error(f"Unhandled error: {e}")
                    response = web.json_response({
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        }
                    }, status=500)
            
            # Add CORS headers
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, mcp-session-id'
            return response
        
        return middleware_handler
    
    app = web.Application(middlewares=[cors_middleware])
    mcp_server = RealScrapingMCPProtocolServer()
    
    # MCP Protocol endpoint
    app.router.add_post("/mcp", mcp_server.handle_mcp_request)
    app.router.add_get("/mcp", mcp_server.handle_mcp_request)
    
    # Smithery tool endpoints
    async def search_profile_handler(request):
        """Handle search_profile tool requests"""
        try:
            data = await request.json()
            name = data.get("name", "")
            
            if not name:
                return web.json_response({
                    "error": "Name parameter is required"
                }, status=400)
            
            # Delegate to MCP adapter's search functionality
            result = await mcp_server.adapter.search_profile(name)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error in search_profile_handler: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def get_session_status_handler(request):
        """Handle get_session_status tool requests"""
        try:
            # Return current sessions status
            sessions_info = {
                "active_sessions": len(mcp_server.sessions),
                "sessions": list(mcp_server.sessions.keys())
            }
            return web.json_response(sessions_info)
            
        except Exception as e:
            logger.error(f"Error in get_session_status_handler: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def get_collaborators_handler(request):
        """Handle get_collaborators tool requests"""
        try:
            data = await request.json()
            session_id = data.get("session_id", "")
            
            if not session_id:
                return web.json_response({
                    "error": "session_id parameter is required"
                }, status=400)
            
            # Get collaborators for the session
            result = await mcp_server.adapter.get_collaborators(session_id)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error in get_collaborators_handler: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def get_profile_handler(request):
        """Handle get_profile tool requests"""
        try:
            data = await request.json()
            profile_url = data.get("profile_url", "")
            
            if not profile_url:
                return web.json_response({
                    "error": "profile_url parameter is required"
                }, status=400)
            
            # Get profile information
            result = await mcp_server.adapter.get_profile(profile_url)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error in get_profile_handler: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    # MCP Config endpoint for Smithery discovery
    async def mcp_config_handler(request):
        """Handle .well-known/mcp-config requests"""
        return web.json_response({
            "mcpVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "YOK Academic MCP Real Scraping Server",
                "version": "3.0.0"
            },
            "endpoints": {
                "mcp": "/mcp"
            }
        })
    
    # Add tool endpoints
    app.router.add_get("/.well-known/mcp-config", mcp_config_handler)
    app.router.add_post("/search_profile", search_profile_handler)
    app.router.add_get("/get_session_status", get_session_status_handler)
    app.router.add_post("/get_collaborators", get_collaborators_handler)
    app.router.add_post("/get_profile", get_profile_handler)
    
    # Root endpoint for MCP capabilities
    async def root_handler(request):
        """Root endpoint showing MCP capabilities"""
        return web.json_response({
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "YOK Academic MCP Real Scraping Server",
                "version": "3.0.0"
            },
            "instructions": "This is an MCP (Model Context Protocol) server for YÖK Academic research.",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health",
                "tools": ["/search_profile", "/get_session_status", "/get_collaborators", "/get_profile"]
            }
        })
    
    # Health check
    async def health_check_handler(request):
        return web.json_response({
            "status": "ok",
            "service": "YOK Academic MCP Real Scraping Server",
            "version": "3.0.0",
            "protocol": "MCP 2024-11-05",
            "features": ["Real-time streaming", "Real scraping integration", "Progress updates", "Event-driven responses"],
            "endpoints": ["/mcp", "/search_profile", "/get_session_status", "/get_collaborators", "/get_profile", "/health"]
        })
    
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_check_handler)
    
    return app

if __name__ == "__main__":
    app = create_app()
    # Ortam değişkeninden portu al, yoksa 8080 kullan (Smithery uyumluluğu için)
    port = int(os.environ.get("PORT", 8080))
    
    # Debug: PORT environment variable'ını log'la
    logger.info(f"🐛 PORT env var: {os.environ.get('PORT', 'Not set')}")
    logger.info(f"🐛 Using port: {port}")

    logger.info("=" * 60)
    logger.info("YÖK Akademik Asistanı - MCP Real Scraping Server")
    logger.info("=" * 60)
    logger.info(f"Server: http://localhost:{port}")
    logger.info(f"MCP Endpoint: http://localhost:{port}/mcp")
    logger.info(f"Health Check: http://localhost:{port}/health")
    logger.info("=" * 60)
    logger.info("🚀 Now with REAL SCRAPING during streaming!")
    logger.info("📡 No more mock data - actual YÖK scraping!")
    logger.info("=" * 60)

    # 0.0.0.0'a bind ederek container dışından erişimi sağla
    web.run_app(app, host="0.0.0.0", port=port)
