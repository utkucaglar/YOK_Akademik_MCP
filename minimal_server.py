#!/usr/bin/env python3
"""
Ultra-minimal HTTP server for Smithery deployment
Using only Python stdlib - no external dependencies
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Minimal tools data
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

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        """Handle GET requests"""
        path = urlparse(self.path).path
        
        try:
            if path == '/health':
                self.send_json_response({
                    "status": "ok",
                    "service": "YOK Academic MCP Server",
                    "version": "1.0.0"
                })
            
            elif path == '/':
                self.send_json_response({
                    "name": "YOK Academic MCP Server",
                    "version": "1.0.0", 
                    "tools": len(TOOLS),
                    "endpoints": ["/health", "/mcp", "/search_profile", "/get_session_status"]
                })
            
            elif path == '/get_session_status':
                result = execute_tool("get_session_status", {})
                self.send_json_response(result)
            
            elif path == '/mcp':
                # MCP GET capabilities
                self.send_json_response({
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "YOK Academic MCP Server", "version": "1.0.0"}
                    }
                })
            
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            self.send_error(500, str(e))
    
    def do_POST(self):
        """Handle POST requests"""
        path = urlparse(self.path).path
        
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body = self.rfile.read(content_length).decode('utf-8')
                try:
                    data = json.loads(body)
                except:
                    data = {}
            else:
                data = {}
            
            if path == '/search_profile':
                name = data.get('name', '')
                if not name:
                    self.send_json_response({"error": "Name required"}, 400)
                    return
                result = execute_tool("search_profile", {"name": name})
                self.send_json_response(result)
            
            elif path == '/mcp':
                # Handle MCP protocol
                method = data.get('method')
                
                if method == 'initialize':
                    self.send_json_response({
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {"name": "YOK Academic MCP Server", "version": "1.0.0"}
                        }
                    })
                
                elif method == 'tools/list':
                    self.send_json_response({
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {"tools": TOOLS}
                    })
                
                elif method == 'tools/call':
                    tool_name = data.get("params", {}).get("name")
                    arguments = data.get("params", {}).get("arguments", {})
                    
                    if not tool_name:
                        self.send_json_response({
                            "jsonrpc": "2.0",
                            "id": data.get("id"),
                            "error": {"code": -32602, "message": "Tool name required"}
                        }, 400)
                        return
                    
                    result = execute_tool(tool_name, arguments)
                    self.send_json_response({
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(result)}]
                        }
                    })
                
                else:
                    self.send_json_response({
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "error": {"code": -32601, "message": f"Method not found: {method}"}
                    }, 404)
            
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            self.send_error(500, str(e))
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def send_json_response(self, data, status=200):
        """Send JSON response with CORS headers"""
        response = json.dumps(data, ensure_ascii=False)
        
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response.encode('utf-8'))))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
    
    def send_cors_headers(self):
        """Send CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    def log_message(self, format, *args):
        """Override to customize logging"""
        print(f"[{self.address_string()}] {format % args}")

def run_server():
    """Run the HTTP server"""
    port = int(os.environ.get('PORT', 8080))
    
    print("=" * 50)
    print("🚀 Minimal YÖK Academic MCP Server")
    print("=" * 50)
    print(f"Port: {port}")
    print(f"Health: http://0.0.0.0:{port}/health")
    print(f"MCP: http://0.0.0.0:{port}/mcp")
    print(f"Tools: {len(TOOLS)}")
    print("=" * 50)
    
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    
    try:
        print(f"✅ Server starting on port {port}...")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped")
        server.server_close()
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    run_server()
