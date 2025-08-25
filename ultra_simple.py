#!/usr/bin/env python3
"""
Ultra-simple single-file MCP server
Absolute minimal implementation for Smithery deployment
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_json({"status": "ok", "service": "YOK Academic MCP"})
        elif self.path == '/':
            self.send_json({"name": "YOK Academic MCP", "version": "1.0"})
        elif self.path == '/get_session_status':
            self.send_json({"status": "success", "sessions": 1})
        elif self.path == '/mcp':
            self.send_json({"jsonrpc": "2.0", "result": {"protocolVersion": "2024-11-05"}})
        else:
            self.send_error(404)
    
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length).decode()) if length > 0 else {}
        except:
            data = {}
        
        if self.path == '/search_profile':
            name = data.get('name', 'test')
            self.send_json({"status": "success", "name": name, "session_id": "123"})
        elif self.path == '/mcp':
            method = data.get('method')
            if method == 'initialize':
                result = {"protocolVersion": "2024-11-05", "serverInfo": {"name": "YOK MCP"}}
            elif method == 'tools/list':
                result = {"tools": [{"name": "search_profile", "description": "Search profiles"}]}
            elif method == 'tools/call':
                result = {"content": [{"type": "text", "text": '{"status": "success"}'}]}
            else:
                result = {}
            self.send_json({"jsonrpc": "2.0", "id": data.get("id"), "result": result})
        else:
            self.send_error(404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def send_json(self, data):
        response = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)
    
    def log_message(self, format, *args):
        print(f"[{self.client_address[0]}] {format % args}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"YOK Academic MCP Server starting on port {port}")
    
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"Server ready at http://0.0.0.0:{port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
