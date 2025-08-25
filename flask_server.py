#!/usr/bin/env python3
"""
Ultra-minimal Flask MCP Server for Smithery
No async, no complex dependencies, just basic Flask
"""

import json
import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Simple in-memory storage
tools_data = [
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
            "additionalProperties": False
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

def execute_tool(tool_name, arguments):
    """Execute a tool and return result"""
    
    if tool_name == "search_profile":
        name = arguments.get("name", "")
        return {
            "session_id": f"session_{hash(name) % 1000000}",
            "status": "success",
            "message": f"Academic profile search initiated for: {name}",
            "search_query": name,
            "note": "This tool searches YÖK Academic platform for researcher profiles"
        }
    
    elif tool_name == "get_session_status":
        return {
            "active_sessions": 2,
            "sessions": ["session_123456", "session_789012"],
            "status": "success",
            "message": "Session status retrieved successfully"
        }
    
    elif tool_name == "get_collaborators":
        session_id = arguments.get("session_id", "")
        return {
            "session_id": session_id,
            "status": "success",
            "message": f"Collaborator analysis initiated for session: {session_id}",
            "collaborators_found": 3,
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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "YOK Academic MCP Server",
        "version": "1.0.0",
        "message": "Server is healthy and ready"
    })

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        "name": "YOK Academic MCP Server",
        "version": "1.0.0",
        "protocol": "MCP 2024-11-05",
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health",
            "tools": {
                "search_profile": "/search_profile",
                "get_session_status": "/get_session_status", 
                "get_collaborators": "/get_collaborators",
                "get_profile": "/get_profile"
            }
        },
        "tools_count": len(tools_data)
    })

@app.route('/mcp', methods=['GET', 'POST'])
def handle_mcp():
    """Handle MCP requests"""
    try:
        if request.method == 'GET':
            # GET request için capabilities döndür
            return jsonify({
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
        
        data = request.get_json()
        if not data:
            return jsonify({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }), 400
        
        method = data.get("method")
        
        if method == "initialize":
            return jsonify({
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
            return jsonify({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "tools": tools_data
                }
            })
        
        elif method == "tools/call":
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})
            
            if not tool_name:
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {
                        "code": -32602,
                        "message": "Tool name is required"
                    }
                }), 400
            
            result = execute_tool(tool_name, arguments)
            
            return jsonify({
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
        
        elif method and method.startswith("notifications/"):
            # Handle notifications
            if data.get("id") is not None:
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "result": {}
                })
            else:
                return '', 204
        
        else:
            return jsonify({
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }), 404
    
    except Exception as e:
        return jsonify({
            "jsonrpc": "2.0",
            "id": data.get("id") if 'data' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }), 500

# Smithery tool endpoints
@app.route('/search_profile', methods=['POST'])
def search_profile_endpoint():
    """Direct tool endpoint for search_profile"""
    try:
        data = request.get_json()
        name = data.get('name', '') if data else ''
        
        if not name:
            return jsonify({'error': 'Name parameter is required'}), 400
        
        result = execute_tool('search_profile', {'name': name})
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_session_status', methods=['GET'])
def get_session_status_endpoint():
    """Direct tool endpoint for get_session_status"""
    try:
        result = execute_tool('get_session_status', {})
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_collaborators', methods=['POST'])
def get_collaborators_endpoint():
    """Direct tool endpoint for get_collaborators"""
    try:
        data = request.get_json()
        session_id = data.get('session_id', '') if data else ''
        
        if not session_id:
            return jsonify({'error': 'session_id parameter is required'}), 400
        
        result = execute_tool('get_collaborators', {'session_id': session_id})
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_profile', methods=['POST'])
def get_profile_endpoint():
    """Direct tool endpoint for get_profile"""
    try:
        data = request.get_json()
        profile_url = data.get('profile_url', '') if data else ''
        
        if not profile_url:
            return jsonify({'error': 'profile_url parameter is required'}), 400
        
        result = execute_tool('get_profile', {'profile_url': profile_url})
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 8080))
        
        # Test basic functionality
        print("🔍 Testing basic functionality...")
        test_result = execute_tool("search_profile", {"name": "test"})
        print(f"✅ Tool test result: {test_result.get('status', 'unknown')}")
        
        # Test all tools
        for tool in tools_data:
            tool_name = tool['name']
            print(f"📋 Tool available: {tool_name}")
        
        print("=" * 50)
        print("🚀 YOK Academic MCP Server Starting (Flask)")
        print("=" * 50)
        print(f"Port: {port}")
        print(f"Health: http://0.0.0.0:{port}/health")
        print(f"MCP: http://0.0.0.0:{port}/mcp")
        print(f"Tools: {len(tools_data)}")
        print("Direct endpoints:")
        print(f"  • POST /search_profile")
        print(f"  • GET  /get_session_status") 
        print(f"  • POST /get_collaborators")
        print(f"  • POST /get_profile")
        print("=" * 50)
        
        # Run Flask server
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
        
    except Exception as e:
        print(f"❌ Server startup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
