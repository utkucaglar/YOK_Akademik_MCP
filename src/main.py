#!/usr/bin/env python3
"""
YÖK Akademik MCP Server - FastMCP Implementation
Migration to Smithery's new custom container format
"""

import os
import sys
import uvicorn
import json
import base64
from pathlib import Path
from urllib.parse import parse_qs, unquote
from fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from typing import Optional, Dict, Any
import logging

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our existing adapter
try:
    from mcp_adapter import YOKAcademicMCPAdapter
except ImportError as e:
    logging.error(f"Failed to import MCP adapter: {e}")
    # Create a minimal fallback adapter
    class YOKAcademicMCPAdapter:
        def __init__(self):
            pass
        
        def get_tools(self):
            return [
                {
                    "name": "search_profile",
                    "description": "YÖK Akademik platformunda akademisyen profili ara",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Aranacak akademisyenin adı"}
                        },
                        "required": ["name"]
                    }
                }
            ]
        
        async def execute_tool(self, tool_name, arguments):
            return {
                "status": "success",
                "message": f"Tool {tool_name} executed with args: {arguments}",
                "note": "Running in fallback mode"
            }

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP(name="YOK Academic MCP Server")

# Global adapter instance
adapter = YOKAcademicMCPAdapter()

# Import middleware from separate file
try:
    from middleware import SmitheryConfigMiddleware
except ImportError:
    # Fallback middleware if import fails
    class SmitheryConfigMiddleware:
        """Middleware to extract Smithery configuration from URL parameters"""
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope.get('type') == 'http':
                query = scope.get('query_string', b'').decode()
                
                if 'config=' in query:
                    try:
                        config_b64 = unquote(parse_qs(query)['config'][0])
                        config = json.loads(base64.b64decode(config_b64))
                        
                        # Store config in scope for request handlers to access
                        scope['smithery_config'] = config
                        logger.info(f"Extracted Smithery config: {config}")
                    except Exception as e:
                        logger.warning(f"Failed to parse config from URL: {e}")
                        scope['smithery_config'] = {}
                else:
                    scope['smithery_config'] = {}
            
            await self.app(scope, receive, send)

def get_request_config() -> dict:
    """Get full config from current request context."""
    try:
        import contextvars
        
        # Try to get from request context if available
        request = contextvars.copy_context().get('request')
        if hasattr(request, 'scope') and request.scope:
            return request.scope.get('smithery_config', {})
    except:
        pass
    return {}

def get_config_value(key: str, default=None):
    """Get a specific config value from current request."""
    config = get_request_config()
    return config.get(key, default)

def validate_server_access(server_token: Optional[str]) -> bool:
    """Validate server token - accepts any string including empty ones for demo."""
    return server_token is not None and len(server_token.strip()) > 0 if server_token else True

# Store server token only for stdio mode (backwards compatibility)
_server_token: Optional[str] = None

def handle_config(config: dict):
    """Handle configuration from Smithery - for backwards compatibility with stdio mode."""
    global _server_token
    if server_token := config.get('serverToken'):
        _server_token = server_token

@mcp.tool()
def search_profile(name: str) -> str:
    """YÖK Akademik platformunda akademisyen profili ara ve işbirliklerini tara"""
    
    # Get configuration for this request
    config = get_request_config()
    server_token = config.get('serverToken') or _server_token
    
    # Validate server access (your custom validation logic)
    if not validate_server_access(server_token):
        raise ValueError("Server access validation failed. Please provide a valid serverToken.")
    
    # Execute the search
    import asyncio
    result = asyncio.run(adapter.search_profile(name))
    
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
def get_session_status() -> str:
    """Aktif session'ın durumunu kontrol et"""
    
    # Get configuration for this request
    config = get_request_config()
    server_token = config.get('serverToken') or _server_token
    
    # Validate server access
    if not validate_server_access(server_token):
        raise ValueError("Server access validation failed. Please provide a valid serverToken.")
    
    # Get session status
    import asyncio
    result = asyncio.run(adapter.get_session_status())
    
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
def get_collaborators(session_id: str) -> str:
    """Belirtilen session için işbirlikçi taraması başlat"""
    
    # Get configuration for this request
    config = get_request_config()
    server_token = config.get('serverToken') or _server_token
    
    # Validate server access
    if not validate_server_access(server_token):
        raise ValueError("Server access validation failed. Please provide a valid serverToken.")
    
    # Get collaborators
    import asyncio
    result = asyncio.run(adapter.get_collaborators(session_id))
    
    return json.dumps(result, indent=2, ensure_ascii=False)

@mcp.tool()
def get_profile(profile_url: str) -> str:
    """Main profile scraping sonrası hangi profilin işbirliklerinin taranacağını seç"""
    
    # Get configuration for this request
    config = get_request_config()
    server_token = config.get('serverToken') or _server_token
    
    # Validate server access
    if not validate_server_access(server_token):
        raise ValueError("Server access validation failed. Please provide a valid serverToken.")
    
    # Get profile
    import asyncio
    result = asyncio.run(adapter.get_profile(profile_url))
    
    return json.dumps(result, indent=2, ensure_ascii=False)

# Manual MCP Protocol Implementation for Smithery compatibility
async def handle_mcp_request(request):
    """Handle MCP protocol requests directly"""
    try:
        # Handle GET request for capabilities
        if request.method == "GET":
            return JSONResponse({
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
                        "name": "YOK Academic MCP Server",
                        "version": "3.0.0"
                    },
                    "instructions": "YÖK Academic research and collaboration analysis server"
                }
            })
        
        # Handle POST requests
        data = await request.json()
        method = data.get("method")
        
        logger.info(f"MCP Request: {method}")
        
        if method == "initialize":
            return JSONResponse({
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
                        "name": "YOK Academic MCP Server",
                        "version": "3.0.0"
                    },
                    "instructions": "Use this server to search and analyze YÖK Academic profiles and collaborations."
                }
            })
        
        elif method == "tools/list":
            tools = adapter.get_tools()
            return JSONResponse({
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
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32602,
                        "message": "Tool name is required"
                    }
                }, status_code=400)
            
            try:
                result = await adapter.execute_tool(tool_name, arguments)
                return JSONResponse({
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
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Tool execution failed: {str(e)}"
                    }
                }, status_code=500)
        
        elif method == "logging/setLevel":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {}
            })
        
        elif method.startswith("notifications/"):
            # Handle notifications
            logger.info(f"Received notification: {method}")
            if data.get("id") is not None:
                return JSONResponse({
                    "jsonrpc": "2.0", 
                    "id": data.get("id"),
                    "result": {}
                })
            else:
                return JSONResponse({}, status_code=204)
        
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }, status_code=404)
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        }, status_code=400)
    except Exception as e:
        logger.error(f"MCP request error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": data.get("id") if 'data' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }, status_code=500)

async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "YOK Academic MCP Server",
        "version": "3.0.0",
        "protocol": "MCP 2024-11-05",
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health"
        }
    })

async def root_handler(request):
    """Root endpoint"""
    return JSONResponse({
        "service": "YOK Academic MCP Server",
        "version": "3.0.0",
        "protocol": "MCP 2024-11-05",
        "status": "running",
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health"
        }
    })

def create_hybrid_app():
    """Create a hybrid app with both manual MCP endpoints and FastMCP"""
    
    # Define routes
    routes = [
        Route('/', root_handler, methods=["GET"]),
        Route('/health', health_check, methods=["GET"]),
        Route('/mcp', handle_mcp_request, methods=["GET", "POST", "OPTIONS"]),
    ]
    
    # Create Starlette app
    app = Starlette(routes=routes)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "mcp-protocol-version"],
        max_age=86400,
    )
    
    # Apply custom middleware for config extraction
    app = SmitheryConfigMiddleware(app)
    
    return app

def main():
    transport_mode = os.getenv("TRANSPORT", "stdio")
    
    if transport_mode == "http":
        # HTTP mode with manual MCP implementation for Smithery compatibility
        logger.info("=" * 60)
        logger.info("YÖK Academic MCP Server - Hybrid Implementation")
        logger.info("=" * 60)
        logger.info("🚀 Starting in HTTP mode...")
        
        try:
            # Create hybrid app with manual MCP endpoints
            app = create_hybrid_app()
            
            # Use Smithery-required PORT environment variable (default 8081)
            port = int(os.environ.get("PORT", 8081))
            
            logger.info(f"📡 Server starting on 0.0.0.0:{port}")
            logger.info(f"🔧 MCP endpoint: http://0.0.0.0:{port}/mcp")
            logger.info(f"❤️  Health check: http://0.0.0.0:{port}/health")
            logger.info(f"🏠 Root endpoint: http://0.0.0.0:{port}/")
            logger.info("=" * 60)

            uvicorn.run(
                app, 
                host="0.0.0.0", 
                port=port, 
                log_level="info",
                access_log=True
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to start HTTP server: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    else:
        # STDIO mode using FastMCP for backwards compatibility
        logger.info("YÖK Academic MCP Server starting in stdio mode...")
        
        server_token = os.getenv("SERVER_TOKEN")
        # Set the server token for stdio mode (can be None)
        handle_config({"serverToken": server_token})
        
        # Run with stdio transport (default)
        mcp.run()

if __name__ == "__main__":
    main()
