#!/usr/bin/env python3
"""
Simple MCP Server for Smithery Testing
Minimal implementation to ensure compatibility
"""

import asyncio
import json
import sys
import os
import logging
from pathlib import Path
from datetime import datetime
from aiohttp import web

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleMCPServer:
    """Simple MCP Server for testing Smithery compatibility"""
    
    def __init__(self):
        self.sessions = {}
        
    def get_tools(self):
        """Get MCP tools list"""
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
                "description": "Aktif session durumunu kontrol et",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    
    async def handle_initialize(self, request):
        """MCP initialize endpoint"""
        try:
            if request.method == 'GET':
                data = {}
            else:
                try:
                    data = await request.json()
                except:
                    data = {}
            
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id", 1),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        }
                    },
                    "serverInfo": {
                        "name": "YOK Academic MCP Server",
                        "version": "3.0.0"
                    }
                }
            }
            
            logger.info("✅ MCP Initialize request handled")
            return web.json_response(response)
            
        except Exception as e:
            logger.error(f"Initialize error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id", 1) if 'data' in locals() else 1,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status=500)
    
    async def handle_tools_list(self, request):
        """MCP tools/list endpoint"""
        try:
            if request.method == 'GET':
                data = {}
            else:
                try:
                    data = await request.json()
                except:
                    data = {}
            
            tools = self.get_tools()
            
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id", 1),
                "result": {
                    "tools": tools
                }
            }
            
            logger.info(f"📋 Tools listed: {len(tools)} tools")
            return web.json_response(response)
            
        except Exception as e:
            logger.error(f"Tools list error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id", 1) if 'data' in locals() else 1,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }, status=500)
    
    async def handle_tools_call(self, request):
        """MCP tools/call endpoint"""
        try:
            data = await request.json()
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})
            
            # Simple mock responses
            if tool_name == "search_profile":
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Mock search result for: {arguments.get('name', 'Unknown')}"
                        }
                    ]
                }
            else:
                result = {
                    "content": [
                        {
                            "type": "text", 
                            "text": f"Mock result for tool: {tool_name}"
                        }
                    ]
                }
            
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": result
            }
            
            logger.info(f"🔧 Tool called: {tool_name}")
            return web.json_response(response)
            
        except Exception as e:
            logger.error(f"Tools call error: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Tool execution failed: {str(e)}"
                }
            }, status=500)
    
    async def handle_mcp_request(self, request):
        """Main MCP request handler"""
        try:
            if request.method == "GET":
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
                            "version": "3.0.0"
                        }
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
            elif method == "notifications/initialized":
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
            
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response
        return middleware_handler
    
    app = web.Application(middlewares=[cors_middleware])
    mcp_server = SimpleMCPServer()
    
    # MCP endpoints
    app.router.add_post("/mcp", mcp_server.handle_mcp_request)
    app.router.add_get("/mcp", mcp_server.handle_mcp_request)
    
    # Health check
    async def health_handler(request):
        return web.json_response({
            "status": "ok",
            "service": "Simple YOK Academic MCP Server",
            "version": "3.0.0"
        })
    
    # Root endpoint
    async def root_handler(request):
        return web.json_response({
            "name": "YOK Academic MCP Server",
            "version": "3.0.0",
            "status": "ready",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health"
            }
        })
    
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_handler)
    
    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    
    logger.info("=" * 60)
    logger.info("Simple YÖK Akademik MCP Server")
    logger.info("=" * 60)
    logger.info(f"Server: http://localhost:{port}")
    logger.info(f"MCP Endpoint: http://localhost:{port}/mcp")
    logger.info(f"Health Check: http://localhost:{port}/health")
    logger.info("=" * 60)
    
    web.run_app(app, host="0.0.0.0", port=port)
