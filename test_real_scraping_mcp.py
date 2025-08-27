#!/usr/bin/env python3
"""
Test Script for Real Scraping MCP Server
Tests real-time streaming with actual YÖK scraping operations
"""

import asyncio
import json
import aiohttp
import logging
from datetime import datetime
from typing import Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealScrapingMCPTester:
    """Test the real scraping MCP server functionality with real-time streaming"""
    
    def __init__(self, server_url: str = "http://localhost:5000/mcp"):
        self.server_url = server_url
        self.session_id = None
        self.request_id = 0
        self.total_collaborators = 0
        self.collaborators_received = 0
        self.all_collaborators = []
        
        # Initialize counters for tracking new items
        self.last_profile_count = 0
        self.last_collaborator_count = 0
        
    def next_id(self) -> int:
        """Generate next request ID"""
        self.request_id += 1
        return self.request_id
    
    async def test_real_scraping(self):
        """Test real scraping with real-time streaming"""
        logger.info("🚀 MCP Real Scraping Test Script Starting...")
        logger.info(f"Testing MCP Server: {self.server_url}")
        logger.info("=" * 60)
        logger.info("⚠️  This will perform REAL YÖK scraping operations!")
        logger.info("⚠️  Make sure you have Chrome/ChromeDriver installed!")
        logger.info("=" * 60)
        
        # Test 1: Initialize MCP session
        logger.info("\n🔍 Test 1: MCP Protocol Initialize")
        if not await self.test_initialize():
            logger.error("❌ Failed to initialize MCP session")
            return False
        
        # Test 2: List available tools
        logger.info("\n🔍 Test 2: List Available Tools")
        if not await self.test_list_tools():
            logger.error("❌ Failed to list tools")
            return False
        
        # Test 3: Test profile search with real-time streaming
        logger.info("\n🔍 Test 3: search_profile Tool with REAL YÖK Scraping")
        logger.info("⚠️  This will perform actual web scraping!")
        
        name = input("\n🔍 Enter a name to search for (or press Enter for 'Ahmet Yılmaz'): ").strip()
        if not name:
            name = "Ahmet Yılmaz"
        
        logger.info(f"🔍 Searching for: {name}")
        if not await self.test_real_profile_search(name):
            logger.error("❌ Profile search failed")
            return False
        
        # Test 4: Test collaborator search with real-time streaming
        logger.info("\n🔍 Test 4: get_collaborators Tool with REAL YÖK Scraping")
        logger.info("⚠️  This will perform actual collaborator scraping!")
        
        if not await self.test_real_collaborators_search():
            logger.error("❌ Collaborator search failed")
            return False
        
        logger.info("\n✅ All real scraping tests completed!")
        return True
    
    async def test_initialize(self):
        """Test MCP session initialization"""
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "Python Test Client",
                    "version": "1.0.0"
                }
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.server_url,
                json=request,
                headers={'Accept': 'application/json, text/event-stream'}
            ) as response:
                logger.info(f"Status: {response.status}")
                
                if response.status == 200:
                    # Extract session ID from headers
                    if 'mcp-session-id' in response.headers:
                        self.session_id = response.headers['mcp-session-id']
                        logger.info(f"📄 Session ID: {self.session_id}")
                    
                    # Parse response
                    try:
                        data = await response.json()
                        if 'result' in data:
                            server_info = data['result'].get('serverInfo', {})
                            logger.info(f"✅ MCP initialize successful")
                            logger.info(f"Server: {server_info.get('name', 'Unknown')} v{server_info.get('version', 'Unknown')}")
                            logger.info(f"Protocol: {data['result'].get('protocolVersion', 'Unknown')}")
                            return True
                    except Exception as e:
                        logger.error(f"❌ Failed to parse response: {e}")
                        return False
                else:
                    logger.error(f"❌ Initialize failed with status: {response.status}")
                    return False
    
    async def test_list_tools(self):
        """Test listing available tools"""
        if not self.session_id:
            logger.error("❌ No session ID available")
            return False
        
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "tools/list",
            "params": {}
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.server_url,
                json=request,
                headers={
                    'Accept': 'application/json, text/event-stream',
                    'mcp-session-id': self.session_id
                }
            ) as response:
                logger.info(f"Status: {response.status}")
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        if 'result' in data and 'tools' in data['result']:
                            tools = data['result']['tools']
                            logger.info(f"✅ Tools list retrieved successfully")
                            logger.info(f"📋 Available tools ({len(tools)}):")
                            for i, tool in enumerate(tools, 1):
                                logger.info(f"  {i}. {tool['name']} - {tool['description']}")
                            return True
                    except Exception as e:
                        logger.error(f"❌ Failed to parse tools response: {e}")
                        return False
                else:
                    logger.error(f"❌ Tools list failed with status: {response.status}")
                    return False
    
    async def test_real_profile_search(self, name: str):
        """Test real profile search with real-time streaming"""
        if not self.session_id:
            logger.error("❌ No session ID available")
            return False
        
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "tools/call",
            "params": {
                "name": "search_profile",
                "arguments": {
                    "name": name,
                    "session_id": self.session_id
                }
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.server_url,
                json=request,
                headers={
                    'Accept': 'application/json, text/event-stream',
                    'mcp-session-id': self.session_id
                }
            ) as response:
                logger.info(f"Status: {response.status}")
                logger.info(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
                
                if response.status == 200:
                    logger.info("✅ search_profile call successful")
                    logger.info("📨 Receiving real-time streaming response...")
                    logger.info("⏳ This may take several minutes for real scraping...")
                    
                    # Check if it's SSE streaming
                    if 'text/event-stream' in response.headers.get('content-type', ''):
                        logger.info("📡 SSE streaming detected!")
                        return await self.handle_real_streaming_response(response, "search_profile")
                    else:
                        logger.info("📄 Non-streaming response received")
                        return await self.handle_regular_response(response)
                else:
                    logger.error(f"❌ search_profile failed with status: {response.status}")
                    return False
    
    async def test_real_collaborators_search(self):
        """Test real collaborator search with real-time streaming"""
        if not self.session_id:
            logger.error("❌ No session ID available")
            return False
        
        # First check if we have main_profile.json
        import os
        session_dir = f"public/collaborator-sessions/{self.session_id}"
        main_profile_path = os.path.join(session_dir, "main_profile.json")
        
        if not os.path.exists(main_profile_path):
            logger.error("❌ No main_profile.json found. Run profile search first.")
            return False
        
        # Read profiles for selection
        try:
            with open(main_profile_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
                profiles = profile_data.get('profiles', [])
        except Exception as e:
            logger.error(f"❌ Failed to read main_profile.json: {e}")
            return False
        
        if not profiles:
            logger.error("❌ No profiles found in main_profile.json")
            return False
        
        # Show available profiles for selection
        logger.info(f"📋 Found {len(profiles)} profiles:")
        logger.info("=" * 80)
        for i, profile in enumerate(profiles, 1):
            title = profile.get('title', '')
            name = profile.get('name', 'Unknown')
            author_id = profile.get('author_id', 'N/A')
            email = profile.get('email', 'N/A')
            education = profile.get('education', 'N/A')
            
            # Extract university from education field
            university = "N/A"
            if education and education != 'N/A':
                # Education format: "UNIVERSITY/FACULTY/FACULTY/DEPARTMENT/..."
                parts = education.split('/')
                if len(parts) > 0:
                    university = parts[0]
            
            logger.info(f"   {i}. {title} {name}")
            logger.info(f"      🆔 {author_id}")
            logger.info(f"      🏫 {university}")
            logger.info(f"      📧 {email}")
            logger.info("")
        
        logger.info("=" * 80)
        
        # Auto-select if only one profile, otherwise ask user
        if len(profiles) == 1:
            profile_index = 0
            selected_profile = profiles[0]
            logger.info(f"✅ Auto-selected (only profile): {selected_profile.get('title', '')} {selected_profile.get('name', 'Unknown')}")
            logger.info(f"      🆔 {selected_profile.get('author_id', 'N/A')}")
            logger.info(f"      🏫 {university}")
            logger.info(f"      📧 {selected_profile.get('email', 'N/A')}")
            logger.info("🚀 Starting collaborator search automatically...")
        else:
            # Ask user to select profile
            while True:
                try:
                    choice = input(f"\n👥 Select a profile (1-{len(profiles)}) for collaborator search: ").strip()
                    profile_index = int(choice) - 1
                    if 0 <= profile_index < len(profiles):
                        selected_profile = profiles[profile_index]
                        logger.info(f"✅ Selected profile: {selected_profile.get('title', '')} {selected_profile.get('name', 'Unknown')}")
                        logger.info(f"      🆔 {selected_profile.get('author_id', 'N/A')}")
                        logger.info(f"      🏫 {university}")
                        logger.info(f"      📧 {selected_profile.get('email', 'N/A')}")
                        break
                    else:
                        logger.warning("⚠️  Invalid selection. Please enter a number within the range.")
                except ValueError:
                    logger.warning("⚠️  Invalid input. Please enter a number.")
        
        # Now call get_collaborators
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "tools/call",
            "params": {
                "name": "get_collaborators",
                "arguments": {
                    "session_id": self.session_id,
                    "profile_index": profile_index
                }
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.server_url,
                json=request,
                headers={
                    'Accept': 'application/json, text/event-stream',
                    'mcp-session-id': self.session_id
                }
            ) as response:
                logger.info(f"Status: {response.status}")
                logger.info(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
                
                if response.status == 200:
                    logger.info("✅ get_collaborators call successful")
                    logger.info("📨 Receiving real-time streaming response...")
                    logger.info("⏳ This may take several minutes for real scraping...")
                    
                    # Check if it's SSE streaming
                    if 'text/event-stream' in response.headers.get('content-type', ''):
                        logger.info("📡 SSE streaming detected!")
                        return await self.handle_real_streaming_response(response, "get_collaborators")
                    else:
                        logger.info("📄 Non-streaming response received")
                        return await self.handle_regular_response(response)
                else:
                    logger.error(f"❌ get_collaborators failed with status: {response.status}")
                    return False
    
    async def handle_real_streaming_response(self, response, tool_name: str):
        """Handle real-time streaming SSE response"""
        try:
            # Reset state for new streaming
            self.total_collaborators = 0
            self.collaborators_received = 0
            self.all_collaborators = []
            
            async for line in response.content:
                line = line.decode('utf-8').strip()
                
                if line.startswith('data: '):
                    data_str = line[6:]  # Remove 'data: ' prefix
                    
                    if data_str == '[DONE]':
                        logger.info(f"✅ {tool_name} streaming completed")
                        break
                    
                    try:
                        data = json.loads(data_str)
                        await self.handle_real_streaming_event(data, tool_name)
                    except json.JSONDecodeError as e:
                        logger.warning(f"⚠️  Failed to parse SSE data: {e}")
                        logger.debug(f"Raw data: {data_str}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
            return False
    
    async def handle_real_streaming_event(self, data, tool_name: str):
        """Handle individual streaming events in real-time"""
        event_type = data.get('event', 'unknown')
        
        if event_type == 'search_started':
            results = data.get('data', {})
            name = results.get('name', 'Unknown')
            logger.info(f"🚀 {tool_name} started")
            logger.info(f"🔍 Search started for: {name}")
        
        elif event_type == 'progress_update':
            results = data.get('data', {})
            step = results.get('step', 0)
            total_steps = results.get('total_steps', 0)
            message = results.get('message', '')
            progress = results.get('progress', '')
            
            logger.info(f"📊 Progress: {progress} - {message}")
        
        elif event_type == 'scraping_progress':
            results = data.get('data', {})
            message = results.get('message', '')
            timestamp = results.get('timestamp', '')
            
            logger.info(f"🔄 {message} - {timestamp}")
        
        elif event_type == 'profiles_update':
            results = data.get('data', {})
            profiles_found = results.get('profiles_found', 0)
            profiles = results.get('profiles', [])
            message = results.get('message', '')
            timestamp = results.get('timestamp', '')
            
            logger.info(f"📊 {message} - {timestamp}")
            logger.info(f"👥 Current profiles found: {profiles_found}")
            
            # Show only newly found profiles
            if profiles and len(profiles) > self.last_profile_count:
                new_profiles = profiles[self.last_profile_count:]
                logger.info(f"🆕 Newly found profiles ({len(new_profiles)}):")
                for i, profile in enumerate(new_profiles, self.last_profile_count + 1):
                    title = profile.get('title', '')
                    name = profile.get('name', 'Unknown')
                    education = profile.get('education', 'N/A')
                    
                    # Extract university from education
                    university = "N/A"
                    if education and education != 'N/A':
                        parts = education.split('/')
                        if len(parts) > 0:
                            university = parts[0]
                    
                    logger.info(f"  {i:2d}. {title} {name} - {university}")
                logger.info("")  # Empty line for readability
                
                # Update the count
                self.last_profile_count = len(profiles)
        
        elif event_type == 'collaborators_update':
            results = data.get('data', {})
            collaborators_found = results.get('collaborators_found', 0)
            collaborators = results.get('collaborators', [])
            chunk_start = results.get('chunk_start', 1)
            chunk_end = results.get('chunk_end', 1)
            message = results.get('message', '')
            timestamp = results.get('timestamp', '')
            
            logger.info(f"📊 {message} - {timestamp}")
            logger.info(f"👥 Current collaborators found: {collaborators_found}")
            
            # Show collaborators from this chunk
            if collaborators:
                logger.info(f"🆕 Collaborators chunk ({chunk_start}-{chunk_end}):")
                for i, collaborator in enumerate(collaborators, chunk_start):
                    name = collaborator.get('name', 'Unknown')
                    info = collaborator.get('info', 'N/A')
                    logger.info(f"  {i:2d}. {name} - {info}")
                logger.info("")  # Empty line for readability
        
        elif event_type == 'search_completed':
            results = data.get('data', {})
            profiles_found = results.get('profiles_found', 0)
            
            logger.info(f"🎯 Search completed! Found {profiles_found} profiles")
            logger.info(f"✅ {tool_name} completed")
        
        elif event_type == 'collaborator_search_completed':
            results = data.get('data', {})
            self.total_collaborators = results.get('total_collaborators', 0)
            self.collaborators_received = 0
            self.all_collaborators = []
            selected_profile = results.get('selected_profile', 'Unknown')
            
            logger.info(f"🎯 Collaborator search completed!")
            logger.info(f"📊 Found {self.total_collaborators} collaborators for {selected_profile}")
            logger.info(f"📋 Total collaborators: {self.total_collaborators}")
            logger.info(f"👤 Selected profile: {selected_profile}")
            logger.info("⏳ Waiting for collaborator chunks...")
        
        elif event_type == 'collaborators_chunk':
            results = data.get('data', {})
            collaborators = results.get('collaborators', [])
            start_index = results.get('start_index', 0)
            
            # Add to our collection
            self.all_collaborators.extend(collaborators)
            self.collaborators_received += len(collaborators)
            
            # Show this chunk's collaborators
            for i, collab in enumerate(collaborators):
                global_index = start_index + i
                logger.info(f"  👤 {global_index:2d}. {collab.get('name', 'Unknown')}")
                logger.info(f"     🆔 {collab.get('author_id', 'N/A')}")
                logger.info(f"     📊 {collab.get('info', 'N/A')}")
                if i < len(collaborators) - 1:
                    logger.info("")
            
            if self.collaborators_received >= self.total_collaborators:
                logger.info(f"✅ All {self.total_collaborators} collaborators received and displayed!")
                logger.info(f"📋 Summary: {len(self.all_collaborators)} collaborators received")
                logger.info(f"✅ {tool_name} completed")
        
        elif event_type == 'search_error':
            results = data.get('data', {})
            error = results.get('error', 'Unknown error')
            logger.error(f"❌ {tool_name} error: {error}")
        
        elif event_type == 'status':
            status = data.get('status', 'unknown')
            tool = data.get('tool', 'unknown')
            if status == 'started':
                logger.info(f"🚀 {tool} started")
            elif status == 'completed':
                logger.info(f"✅ {tool} completed")
        
        else:
            logger.debug(f"📡 Unknown event type: {event_type}")
    
    async def handle_regular_response(self, response):
        """Handle non-streaming regular JSON response"""
        try:
            data = await response.json()
            logger.info("📄 Regular JSON response received")
            logger.info(f"Response: {data}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to parse regular response: {e}")
            return False

async def main():
    """Main test function"""
    print("🚀 MCP Real Scraping Test")
    print("=" * 50)
    print("⚠️  WARNING: This will perform REAL web scraping!")
    print("⚠️  Make sure you have:")
    print("   • Chrome browser installed")
    print("   • Internet connection")
    print("   • Permission to scrape YÖK Akademik")
    print("=" * 50)
    
    choice = input("Continue with real scraping? (y/n): ").strip().lower()
    if choice != 'y':
        print("❌ Test cancelled")
        return
    
    tester = RealScrapingMCPTester()
    success = await tester.test_real_scraping()
    
    if success:
        print("\n🎉 All tests completed successfully!")
    else:
        print("\n❌ Some tests failed")

if __name__ == "__main__":
    asyncio.run(main())
