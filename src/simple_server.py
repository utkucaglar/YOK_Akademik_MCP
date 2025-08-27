#!/usr/bin/env python3
"""
Basit MCP Server - Sadece standard library
Smithery için minimal working implementation
"""

import json
import os
import sys
import logging
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our existing adapter with fallback
try:
    from mcp_adapter import YOKAcademicMCPAdapter
    adapter = YOKAcademicMCPAdapter()
    logger.info("✅ Loaded YOKAcademicMCPAdapter successfully")
except ImportError as e:
    logger.warning(f"⚠️ Could not import MCP adapter: {e}")
    # Simple fallback
    class SimpleAdapter:
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
                "note": "Running in simple fallback mode"
            }
    
    adapter = SimpleAdapter()

def create_app():
    """Create ASGI app manually"""
    
    async def app(scope, receive, send):
        """ASGI application"""
        
        # Handle CORS preflight
        if scope["type"] == "http" and scope["method"] == "OPTIONS":
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    [b"access-control-allow-origin", b"*"],
                    [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
                    [b"access-control-allow-headers", b"*"],
                ],
            })
            await send({"type": "http.response.body", "body": b""})
            return
        
        # Only handle HTTP requests
        if scope["type"] != "http":
            return
        
        path = scope["path"]
        method = scope["method"]
        
        logger.info(f"📡 {method} {path}")
        
        # Route handling
        if path == "/" and method == "GET":
            await handle_root(scope, receive, send)
        elif path == "/health" and method == "GET":
            await handle_health(scope, receive, send)
        elif path == "/mcp" and method in ["GET", "POST"]:
            await handle_mcp(scope, receive, send)
        else:
            await handle_404(scope, receive, send)
    
    return app

async def handle_root(scope, receive, send):
    """Root endpoint"""
    response_data = {
        "service": "YOK Academic MCP Server",
        "version": "3.0.0",
        "protocol": "MCP 2024-11-05",
        "status": "running",
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health"
        }
    }
    await send_json_response(send, response_data)

async def handle_health(scope, receive, send):
    """Health check endpoint"""
    response_data = {
        "status": "healthy",
        "service": "YOK Academic MCP Server",
        "version": "3.0.0",
        "protocol": "MCP 2024-11-05"
    }
    await send_json_response(send, response_data)

async def handle_mcp(scope, receive, send):
    """MCP protocol endpoint"""
    method = scope["method"]
    
    if method == "GET":
        # GET request for capabilities
        response_data = {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "logging": {},
                    "experimental": {}
                },
                "serverInfo": {
                    "name": "YOK Academic MCP Server",
                    "version": "3.0.0"
                }
            }
        }
        await send_json_response(send, response_data)
        return
    
    # POST request - handle JSON-RPC
    try:
        # Read request body
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
        
        # Parse JSON
        if body:
            data = json.loads(body.decode())
        else:
            data = {}
        
        json_rpc_method = data.get("method", "")
        logger.info(f"🔧 MCP Method: {json_rpc_method}")
        
        if json_rpc_method == "initialize":
            response_data = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "logging": {},
                        "experimental": {}
                    },
                    "serverInfo": {
                        "name": "YOK Academic MCP Server",
                        "version": "3.0.0"
                    },
                    "instructions": "Use this server to search and analyze YÖK Academic profiles and collaborations."
                }
            }
            
        elif json_rpc_method == "tools/list":
            tools = adapter.get_tools()
            response_data = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {"tools": tools}
            }
            
        elif json_rpc_method == "tools/call":
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})
            
            if hasattr(adapter, 'execute_tool') and callable(adapter.execute_tool):
                # Async call
                import asyncio
                result = await adapter.execute_tool(tool_name, arguments)
            else:
                # Sync fallback
                result = {
                    "status": "success",
                    "message": f"Tool {tool_name} executed",
                    "arguments": arguments
                }
            
            response_data = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, indent=2, ensure_ascii=False)
                    }]
                }
            }
            
        elif json_rpc_method == "logging/setLevel":
            response_data = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {}
            }
            
        elif json_rpc_method.startswith("notifications/"):
            # Notifications - no response or empty response
            if data.get("id") is not None:
                response_data = {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "result": {}
                }
            else:
                # True notification - 204 No Content
                await send({
                    "type": "http.response.start",
                    "status": 204,
                    "headers": [[b"access-control-allow-origin", b"*"]],
                })
                await send({"type": "http.response.body", "body": b""})
                return
        else:
            response_data = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {json_rpc_method}"
                }
            }
        
        await send_json_response(send, response_data)
        
    except Exception as e:
        logger.error(f"❌ MCP Error: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": data.get("id") if 'data' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        await send_json_response(send, error_response, status=500)

async def handle_404(scope, receive, send):
    """404 handler"""
    response_data = {"error": "Not found"}
    await send_json_response(send, response_data, status=404)

async def send_json_response(send, data, status=200):
    """Send JSON response with CORS headers"""
    body = json.dumps(data, ensure_ascii=False).encode()
    
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"],
            [b"access-control-allow-origin", b"*"],
            [b"access-control-allow-methods", b"GET, POST, OPTIONS"],
            [b"access-control-allow-headers", b"*"],
        ],
    })
    await send({"type": "http.response.body", "body": body})

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment (Smithery uses PORT=8081)
    port = int(os.environ.get("PORT", 8081))
    
    logger.info("=" * 60)
    logger.info("🚀 YÖK Academic MCP Server - Simple Implementation")
    logger.info("=" * 60)
    logger.info(f"📡 Starting on 0.0.0.0:{port}")
    logger.info(f"🔧 MCP endpoint: http://0.0.0.0:{port}/mcp")
    logger.info(f"❤️  Health check: http://0.0.0.0:{port}/health")
    logger.info("=" * 60)
    
    # Create and run the app
    app = create_app()
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True
        )
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
