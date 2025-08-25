#!/usr/bin/env python3
"""
Simple health check script for the MCP server
"""

import asyncio
import aiohttp
import json
import sys

async def test_health():
    """Test if the server is healthy"""
    try:
        async with aiohttp.ClientSession() as session:
            # Test health endpoint
            async with session.get('http://localhost:8080/health') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Health check passed: {data.get('status', 'unknown')}")
                    return True
                else:
                    print(f"❌ Health check failed with status: {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ Health check failed with error: {e}")
        return False

async def test_mcp_endpoint():
    """Test MCP endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            # Test MCP initialize
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "health-check",
                        "version": "1.0.0"
                    }
                }
            }
            
            async with session.post(
                'http://localhost:8080/mcp',
                json=mcp_request,
                headers={'Content-Type': 'application/json'}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'result' in data:
                        print("✅ MCP initialize test passed")
                        return True
                    else:
                        print(f"❌ MCP initialize failed: {data}")
                        return False
                else:
                    print(f"❌ MCP endpoint failed with status: {resp.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ MCP endpoint test failed with error: {e}")
        return False

async def test_tools_list():
    """Test tools list endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            # Test tools/list
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            async with session.post(
                'http://localhost:8080/mcp',
                json=tools_request,
                headers={'Content-Type': 'application/json'}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'result' in data and 'tools' in data['result']:
                        tools = data['result']['tools']
                        print(f"✅ Tools list test passed - found {len(tools)} tools")
                        for tool in tools:
                            print(f"   - {tool.get('name', 'unnamed')}: {tool.get('description', 'no description')}")
                        return True
                    else:
                        print(f"❌ Tools list failed: {data}")
                        return False
                else:
                    print(f"❌ Tools list endpoint failed with status: {resp.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Tools list test failed with error: {e}")
        return False

async def main():
    """Run all health checks"""
    print("🔍 Starting health checks...")
    
    tests = [
        ("Health Check", test_health),
        ("MCP Initialize", test_mcp_endpoint),
        ("Tools List", test_tools_list)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        if await test_func():
            passed += 1
        
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All health checks passed!")
        sys.exit(0)
    else:
        print("💥 Some health checks failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
