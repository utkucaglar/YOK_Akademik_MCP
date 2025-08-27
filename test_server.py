#!/usr/bin/env python3
"""
Local test script for debugging MCP server
"""

import asyncio
import aiohttp
import json

async def test_endpoints():
    """Test MCP server endpoints locally"""
    
    base_url = "http://localhost:8081"
    
    # Test endpoints
    endpoints = [
        ("/", "GET", "Root endpoint"),
        ("/health", "GET", "Health check"),
        ("/mcp", "GET", "MCP capabilities"),
    ]
    
    async with aiohttp.ClientSession() as session:
        print("🔧 Testing MCP Server Endpoints")
        print("=" * 50)
        
        for path, method, description in endpoints:
            url = f"{base_url}{path}"
            
            try:
                if method == "GET":
                    async with session.get(url) as response:
                        print(f"✅ {description}: {response.status}")
                        if response.status == 200:
                            text = await response.text()
                            data = json.loads(text)
                            print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
                        print()
                        
            except Exception as e:
                print(f"❌ {description}: Error - {e}")
                print()
        
        # Test MCP protocol
        print("🔧 Testing MCP Protocol")
        print("=" * 50)
        
        # Test initialize
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "Test Client",
                    "version": "1.0.0"
                }
            }
        }
        
        try:
            async with session.post(f"{base_url}/mcp", json=initialize_payload) as response:
                print(f"✅ MCP Initialize: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   Response: {json.dumps(data, indent=2)}")
                print()
        except Exception as e:
            print(f"❌ MCP Initialize: Error - {e}")
            print()
        
        # Test tools/list
        tools_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        try:
            async with session.post(f"{base_url}/mcp", json=tools_payload) as response:
                print(f"✅ MCP Tools List: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   Response: {json.dumps(data, indent=2)}")
                print()
        except Exception as e:
            print(f"❌ MCP Tools List: Error - {e}")
            print()

if __name__ == "__main__":
    print("🚀 Starting MCP Server Test")
    print("Make sure your server is running on localhost:8081")
    print()
    
    asyncio.run(test_endpoints())
