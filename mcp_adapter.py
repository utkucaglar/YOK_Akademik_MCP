#!/usr/bin/env python3
"""
YÖK Akademik Asistanı - MCP Adapter
MCP Inspector ile entegrasyon için adapter
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import subprocess
import os

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.mcp_orchestrator import YOKAcademicAssistant
try:
    from config.config import SESSIONS_DIR
except ImportError:
    # Fallback: Manuel path oluştur
    from pathlib import Path
    SESSIONS_DIR = Path(__file__).parent / "public" / "collaborator-sessions"
    print(f"[WARNING] Config import failed, using fallback path: {SESSIONS_DIR}")

class YOKAcademicMCPAdapter:
    def __init__(self):
        self.orchestrator = YOKAcademicAssistant()
        self.active_sessions = {}
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """MCP Inspector için tools listesi"""
        return [
            {
                "name": "search_profile",
                "description": "YÖK Akademik platformunda akademisyen profili ara ve işbirlikçilerini tara",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Aranacak akademisyenin adı (zorunlu)"
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
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "get_collaborators",
                "description": "Belirtilen session için işbirlikçi tarama başlat",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "get_profile",
                "description": "Main profile scraping sonrası hangi profilin işbirlikçilerinin taranacağını seç",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID"
                        },
                        "profile_id": {
                            "type": "integer",
                            "description": "Seçilecek profilin ID'si (main_profile.json'dan)"
                        }
                    },
                    "required": ["session_id", "profile_id"]
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Tool çalıştır"""
        print(f"[MCP_DEBUG] execute_tool called with tool_name: {tool_name}")
        print(f"[MCP_DEBUG] arguments: {arguments}")
        
        if tool_name == "search_profile":
            print(f"[MCP_DEBUG] Calling _search_profile...")
            result = await self._search_profile(arguments)
            print(f"[MCP_DEBUG] _search_profile result: {result}")
            return result
        elif tool_name == "get_session_status":
            return await self._get_session_status(arguments)
        elif tool_name == "get_collaborators":
            return await self._get_collaborators(arguments)
        elif tool_name == "get_profile":
            return await self._get_profile(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def _search_profile(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Akademik profil arama ve işbirlikçi tarama"""
        try:
            name = arguments.get("name", "")
            
            if not name:
                return {
                    "error": "Name is required",
                    "status": "failed"
                }
            
            # Session ID oluştur
            session_id = self.orchestrator.create_session_id()
            
            # Session'ı başlat
            from core.mcp_orchestrator import SessionInfo, ProcessState
            session_info = SessionInfo(
                session_id=session_id,
                state=ProcessState.INITIALIZING
            )
            self.orchestrator.sessions[session_id] = session_info
            
            # File watcher'ı kur
            self.orchestrator.setup_file_watcher(session_id)
            
            # Event handler'ı override et - stream output'ları düzenli göster
            async def send_sse_event(event_data: Dict):
                # Sadece SSE kuyruğuna yayınla (stdout yok)
                try:
                    from core.mcp_orchestrator import YOKAcademicAssistant
                    await YOKAcademicAssistant.send_sse_event(self.orchestrator, event_data)
                except Exception:
                    pass
            
            self.orchestrator.send_sse_event = send_sse_event
            
            # User info hazırla
            user_info = {
                "name": name
            }
            
            print(f"[MCP_INFO] Starting academic profile search for: {name}")
            print(f"[MCP_INFO] Session ID: {session_id}")
            print(f"[MCP_INFO] User info: {user_info}")
            
            # Scraping'i başlat
            print(f"[MCP_INFO] Calling orchestrator.start_main_profile_scraping...")
            result = await self.orchestrator.start_main_profile_scraping(session_id, user_info)
            print(f"[MCP_INFO] start_main_profile_scraping result: {result}")
            
            # Session'ı aktif listeye ekle
            self.active_sessions[session_id] = {
                "name": name,
                "started_at": session_info.created_at.isoformat(),
                "status": "running"
            }
            
            return {
                "session_id": session_id,
                "status": "started",
                "message": f"Academic profile search started for '{name}'",
                "timestamp": session_info.created_at.isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }
    
    async def _get_collaborators(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """İşbirlikçi tarama başlat"""
        try:
            session_id = arguments.get("session_id", "")
            
            if not session_id:
                return {
                    "error": "Session ID is required",
                    "status": "failed"
                }
            
            if session_id not in self.orchestrator.sessions:
                return {
                    "error": "Session not found",
                    "status": "failed"
                }
            
            print(f"[MCP_INFO] Starting collaborators scraping for session: {session_id}")
            
            # Collaborators scraping'i başlat
            # Önce session'daki profilleri ve varsa seçimi al
            session_info = self.orchestrator.sessions[session_id]
            selected_profile = session_info.selected_profile
            profiles = session_info.profiles or []

            if selected_profile:
                profile = selected_profile
            else:
                if not profiles:
                    raise ValueError("No profiles found in session")
                if len(profiles) == 1:
                    profile = profiles[0]
                else:
                    return {
                        "error": "Multiple profiles found. Please select a profile first using get_profile",
                        "status": "awaiting_selection"
                    }

            await self.orchestrator.start_collaborator_scraping(session_id, profile)
            
            return {
                "session_id": session_id,
                "status": "started",
                "message": f"Collaborators scraping started for session '{session_id}'",
                "timestamp": self.orchestrator.sessions[session_id].created_at.isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }
    
    async def _get_profile(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Profil seç ve işbirlikçi tarama başlat"""
        try:
            session_id = arguments.get("session_id", "")
            profile_id = arguments.get("profile_id")
            
            if not session_id:
                return {
                    "error": "Session ID is required",
                    "status": "failed"
                }
            
            if profile_id is None:
                return {
                    "error": "Profile ID is required",
                    "status": "failed"
                }
            
            if session_id not in self.orchestrator.sessions:
                return {
                    "error": "Session not found",
                    "status": "failed"
                }
            
            # Session dosyasından profilleri oku
            session_dir = SESSIONS_DIR / session_id
            main_profile_file = session_dir / "main_profile.json"
            
            if not main_profile_file.exists():
                return {
                    "error": "Main profile file not found. Please run search_profile first.",
                    "status": "failed"
                }
            
            # main_profile.json'dan profilleri oku
            with open(main_profile_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                profiles = data.get('profiles', [])
            
            # Seçilen profili bul
            selected_profile = None
            for profile in profiles:
                if profile.get('author_id') == profile_id:
                    selected_profile = profile
                    break
            
            if not selected_profile:
                return {
                    "error": f"Profile with ID {profile_id} not found in session",
                    "status": "failed"
                }
            
            print(f"[MCP_INFO] Selected profile: {selected_profile.get('name', 'N/A')}")
            print(f"[MCP_INFO] Profile ID: {profile_id}")
            print(f"[MCP_INFO] Profile selected successfully, ready for collaborator scraping...")
            
            # Session'a seçilen profili kaydet
            session_info = self.orchestrator.sessions[session_id]
            session_info.selected_profile = selected_profile
            from core.mcp_orchestrator import ProcessState
            session_info.state = ProcessState.AWAITING_SELECTION
            
            return {
                "session_id": session_id,
                "profile_id": profile_id,
                "profile_name": selected_profile.get('name', 'N/A'),
                "status": "selected",
                "message": f"Profile '{selected_profile.get('name', 'N/A')}' selected successfully. Use get_collaborators to begin collaborator scraping.",
                "timestamp": session_info.created_at.isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }
    
    async def _get_session_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Session durumunu kontrol et"""
        try:
            session_id = arguments.get("session_id", "")
            
            if not session_id:
                return {
                    "error": "Session ID is required",
                    "status": "failed"
                }
            
            if session_id not in self.orchestrator.sessions:
                return {
                    "error": "Session not found",
                    "status": "failed"
                }
            
            session_info = self.orchestrator.sessions[session_id]
            
            # Session dosyalarını kontrol et
            session_dir = SESSIONS_DIR / session_id
            main_profile_file = session_dir / "main_profile.json"
            collaborators_file = session_dir / "collaborators.json"
            main_done_file = session_dir / "main_done.txt"
            collaborators_done_file = session_dir / "collaborators_done.txt"
            
            status_info = {
                "session_id": session_id,
                "state": session_info.state.value,
                "created_at": session_info.created_at.isoformat(),
                "profiles_found": len(session_info.profiles),
                "collaborators_found": len(session_info.collaborators),
                "files": {
                    "main_profile_exists": main_profile_file.exists(),
                    "collaborators_exists": collaborators_file.exists(),
                    "main_done_exists": main_done_file.exists(),
                    "collaborators_done_exists": collaborators_done_file.exists()
                }
            }
            
            if session_info.error_message:
                status_info["error"] = session_info.error_message
            
            return status_info
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }

# MCP Adapter instance
mcp_adapter = YOKAcademicMCPAdapter()

# MCP Inspector için gerekli fonksiyonlar
def get_tools():
    return mcp_adapter.get_tools()

async def execute_tool(tool_name: str, arguments: Dict[str, Any]):
    return await mcp_adapter.execute_tool(tool_name, arguments)

if __name__ == "__main__":
    print("YÖK Akademik Asistanı - MCP Adapter")
    print("MCP Inspector ile test için hazır")
    print("Kullanım: npx @modelcontextprotocol/inspector@latest")
