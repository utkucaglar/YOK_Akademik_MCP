#!/usr/bin/env python3
"""
WSGI-compatible server for deployment platforms
Some platforms prefer WSGI applications
"""

import json
import os
from urllib.parse import parse_qs

# Minimal tools data - same as minimal_server.py
TOOLS = [
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
    },
    {
        "name": "get_session_status", 
        "description": "Aktif session durumunu kontrol et",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    }
]

def execute_tool(tool_name, arguments):
    """Execute tool with mock response"""
    if tool_name == "search_profile":
        name = arguments.get("name", "")
        return {
            "status": "success",
            "message": f"Academic profile search for: {name}",
            "session_id": f"session_{hash(name) % 1000000}"
        }
    elif tool_name == "get_session_status":
        return {
            "status": "success", 
            "active_sessions": 1,
            "message": "Session status retrieved"
        }
    else:
        return {"error": f"Unknown tool: {tool_name}"}

def application(environ, start_response):
    """WSGI application"""
    method = environ['REQUEST_METHOD']
    path = environ['PATH_INFO']
    
    # CORS headers
    headers = [
        ('Content-Type', 'application/json; charset=utf-8'),
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    ]
    
    try:
        if method == 'OPTIONS':
            # CORS preflight
            start_response('200 OK', headers)
            return [b'']
        
        elif method == 'GET':
            if path == '/health':
                response = {
                    "status": "ok",
                    "service": "YOK Academic MCP Server",
                    "version": "1.0.0"
                }
            elif path == '/':
                response = {
                    "name": "YOK Academic MCP Server",
                    "version": "1.0.0", 
                    "tools": len(TOOLS),
                    "endpoints": ["/health", "/mcp", "/search_profile", "/get_session_status"]
                }
            elif path == '/get_session_status':
                response = execute_tool("get_session_status", {})
            elif path == '/mcp':
                response = {
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "YOK Academic MCP Server", "version": "1.0.0"}
                    }
                }
            else:
                start_response('404 Not Found', headers)
                return [json.dumps({"error": "Not Found"}).encode('utf-8')]
        
        elif method == 'POST':
            # Read request body
            try:
                content_length = int(environ.get('CONTENT_LENGTH', '0'))
            except (ValueError, TypeError):
                content_length = 0
            
            if content_length > 0:
                body = environ['wsgi.input'].read(content_length).decode('utf-8')
                try:
                    data = json.loads(body)
                except:
                    data = {}
            else:
                data = {}
            
            if path == '/search_profile':
                name = data.get('name', '')
                if not name:
                    start_response('400 Bad Request', headers)
                    return [json.dumps({"error": "Name required"}).encode('utf-8')]
                response = execute_tool("search_profile", {"name": name})
            
            elif path == '/mcp':
                method_name = data.get('method')
                
                if method_name == 'initialize':
                    response = {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {"name": "YOK Academic MCP Server", "version": "1.0.0"}
                        }
                    }
                elif method_name == 'tools/list':
                    response = {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {"tools": TOOLS}
                    }
                elif method_name == 'tools/call':
                    tool_name = data.get("params", {}).get("name")
                    arguments = data.get("params", {}).get("arguments", {})
                    
                    if not tool_name:
                        start_response('400 Bad Request', headers)
                        return [json.dumps({
                            "jsonrpc": "2.0",
                            "id": data.get("id"),
                            "error": {"code": -32602, "message": "Tool name required"}
                        }).encode('utf-8')]
                    
                    result = execute_tool(tool_name, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(result)}]
                        }
                    }
                else:
                    start_response('404 Not Found', headers)
                    return [json.dumps({
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "error": {"code": -32601, "message": f"Method not found: {method_name}"}
                    }).encode('utf-8')]
            
            else:
                start_response('404 Not Found', headers)
                return [json.dumps({"error": "Not Found"}).encode('utf-8')]
        
        else:
            start_response('405 Method Not Allowed', headers)
            return [json.dumps({"error": "Method Not Allowed"}).encode('utf-8')]
        
        # Success response
        start_response('200 OK', headers)
        return [json.dumps(response, ensure_ascii=False).encode('utf-8')]
    
    except Exception as e:
        start_response('500 Internal Server Error', headers)
        return [json.dumps({"error": str(e)}).encode('utf-8')]

if __name__ == '__main__':
    # Simple WSGI server for testing
    from wsgiref.simple_server import make_server
    
    port = int(os.environ.get('PORT', 8080))
    
    print("=" * 50)
    print("🚀 WSGI YÖK Academic MCP Server")
    print("=" * 50)
    print(f"Port: {port}")
    print(f"Health: http://0.0.0.0:{port}/health")
    print(f"MCP: http://0.0.0.0:{port}/mcp")
    print(f"Tools: {len(TOOLS)}")
    print("=" * 50)
    
    with make_server('0.0.0.0', port, application) as httpd:
        print(f"✅ WSGI Server running on port {port}...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n⏹️  Server stopped")
