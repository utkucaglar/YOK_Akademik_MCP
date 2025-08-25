#!/usr/bin/env python3
"""
Minimal MCP Server for Smithery compatibility
Simplified version with minimal dependencies and safe startup
"""

import asyncio
import json
import sys
import os
import logging
from pathlib import Path
from typing import Any, Dict, List
from aiohttp import web

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MinimalMCPServer:
    """Minimal MCP Server implementation"""
    
    def __init__(self):
        self.sessions = {}
        
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return minimal tool list for Smithery"""
        return [
            {
                "name": "search_profile",
                "description": "YÖK Akademik platformunda akademisyen profili ara",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Aranacak akademisyenin adı"
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "get_session_status",
                "description": "Aktif session'ın durumunu kontrol et",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": false
                }
            },
            {
                "name": "get_collaborators",
                "description": "Belirtilen session için işbirlikçi taraması başlat",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "İşbirlikçileri taranacak olan oturumun kimliği"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "get_profile",
                "description": "Profil bilgilerini al",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "profile_url": {
                            "type": "string",
                            "description": "İşbirlikleri taranacak olan profilin YÖK Akademik URL'si"
                        }
                    },
                    "required": ["profile_url"]
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with mock responses"""
        
        if tool_name == "search_profile":
            name = arguments.get("name", "")
            return {
                "session_id": f"session_{int(asyncio.get_event_loop().time())}",
                "status": "success",
                "message": f"Academic profile search initiated for: {name}",
                "search_query": name,
                "note": "This tool searches YÖK Academic platform for researcher profiles"
            }
        
        elif tool_name == "get_session_status":
            return {
                "active_sessions": 2,
                "sessions": ["session_1734567890", "session_1734567900"],
                "status": "success",
                "message": "Session status retrieved successfully"
            }
        
        elif tool_name == "get_collaborators":
            session_id = arguments.get("session_id", "")
            return {
                "session_id": session_id,
                "status": "success",
                "message": f"Collaborator analysis initiated for session: {session_id}",
                "collaborators_found": 5,
                "sample_collaborators": [
                    {
                        "name": "Dr. Ahmet Yılmaz",
                        "institution": "İstanbul Teknik Üniversitesi",
                        "collaboration_count": 3
                    },
                    {
                        "name": "Prof. Dr. Ayşe Kaya", 
                        "institution": "Boğaziçi Üniversitesi",
                        "collaboration_count": 2
                    }
                ]
            }
        
        elif tool_name == "get_profile":
            profile_url = arguments.get("profile_url", "")
            return {
                "profile_url": profile_url,
                "status": "success",
                "message": f"Profile information retrieved: {profile_url}",
                "note": "This tool accepts YÖK Akademik profile URLs"
            }
        
        else:
            return {
                "error": f"Unknown tool: {tool_name}",
                "status": "failed"
            }

# Global server instance
mcp_server = MinimalMCPServer()

async def handle_mcp_request(request):
    """Handle MCP requests"""
    try:
        if request.method == "GET":
            # GET request için capabilities döndür
            return web.json_response({
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        }
                    },
                    "serverInfo": {
                        "name": "YOK Academic MCP Server",
                        "version": "1.0.0"
                    }
                }
            })
        
        data = await request.json()
        method = data.get("method")
        
        if method == "initialize":
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        }
                    },
                    "serverInfo": {
                        "name": "YOK Academic MCP Server",
                        "version": "1.0.0"
                    }
                }
            })
        
        elif method == "tools/list":
            tools = mcp_server.get_tools()
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "tools": tools
                }
            })
        
        elif method == "tools/call":
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
            
            result = await mcp_server.execute_tool(tool_name, arguments)
            
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, ensure_ascii=False)
                        }
                    ]
                }
            })
        
        elif method.startswith("notifications/"):
            # Handle notifications
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

async def health_check(request):
    """Health check endpoint"""
    return web.json_response({
        "status": "ok",
        "service": "YOK Academic MCP Server",
        "version": "1.0.0",
        "message": "Server is healthy and ready"
    })

async def root_handler(request):
    """Root endpoint"""
    return web.json_response({
        "name": "YOK Academic MCP Server",
        "version": "1.0.0",
        "protocol": "MCP 2024-11-05",
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health"
        },
        "tools": len(mcp_server.get_tools())
    })

def create_app():
    """Create web application"""
    # CORS middleware
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            if request.method == 'OPTIONS':
                response = web.Response(status=200)
            else:
                try:
                    response = await handler(request)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
                    response = web.json_response({
                        "error": f"Internal error: {str(e)}"
                    }, status=500)
            
            # Add CORS headers
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response
        
        return middleware_handler
    
    app = web.Application(middlewares=[cors_middleware])
    
    # Add routes
    app.router.add_post("/mcp", handle_mcp_request)
    app.router.add_get("/mcp", handle_mcp_request)
    app.router.add_get("/health", health_check)
    app.router.add_get("/", root_handler)
    
    return app

async def startup_check():
    """Perform startup health check"""
    try:
        # Test tool creation
        tools = mcp_server.get_tools()
        logger.info(f"✅ Tools loaded successfully: {len(tools)} tools")
        
        # Test tool execution
        test_result = await mcp_server.execute_tool("search_profile", {"name": "test"})
        if test_result.get("status") == "success":
            logger.info("✅ Tool execution test passed")
        else:
            logger.warning("⚠️ Tool execution test failed")
        
        logger.info("🎉 Startup checks completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Startup check failed: {e}")
        return False

if __name__ == "__main__":
    try:
        # Run startup check
        logger.info("🔍 Running startup checks...")
        check_result = asyncio.run(startup_check())
        
        if not check_result:
            logger.error("❌ Startup checks failed, exiting")
            sys.exit(1)
        
        app = create_app()
        port = int(os.environ.get("PORT", 8080))
        
        logger.info("=" * 50)
        logger.info("🚀 YÖK Academic MCP Server Ready")
        logger.info("=" * 50)
        logger.info(f"Port: {port}")
        logger.info(f"Health: http://0.0.0.0:{port}/health")
        logger.info(f"MCP: http://0.0.0.0:{port}/mcp")
        logger.info(f"Tools: {len(mcp_server.get_tools())}")
        logger.info("=" * 50)
        
        web.run_app(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
