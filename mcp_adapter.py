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
                "description": "YÖK Akademik platformunda akademisyen profili ara (real-time streaming ile sonuçları sunar)",
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
                "name": "get_profile",
                "description": "Session'daki tüm profil verilerini JSON formatında döndürür",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Profil verilerini alınacak session ID (opsiyonel, verilmezse en son session kullanılır)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_collaborators",
                "description": "Seçilen profil için işbirlikçi araştırması başlatır",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID"
                        },
                        "profile_index": {
                            "type": "integer",
                            "description": "İşbirlikçileri aranacak profilin index numarası (1'den başlar)",
                            "minimum": 1
                        }
                    },
                    "required": ["session_id", "profile_index"]
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
        elif tool_name == "get_profile":
            return await self._get_profile_details(arguments)
        elif tool_name == "get_collaborators":
            return await self._get_collaborators(arguments)
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
        """Seçilen profil için işbirlikçi tarama başlat"""
        try:
            session_id = arguments.get("session_id")
            profile_index = arguments.get("profile_index", 1)
            
            if not session_id:
                return {
                    "error": "Session ID is required",
                    "status": "failed"
                }
            
            # Session'ın var olduğunu kontrol et
            session_dir = SESSIONS_DIR / session_id
            if not session_dir.exists():
                return {
                    "error": f"Session not found: {session_id}",
                    "status": "failed"
                }
            
            # main_profile.json'ın var olduğunu kontrol et
            main_profile_file = session_dir / "main_profile.json"
            if not main_profile_file.exists():
                return {
                    "error": "Main profile file not found. Please run search_profile first.",
                    "status": "failed"
                }
            
            # Profil index'inin geçerli olduğunu kontrol et
            with open(main_profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
                total_profiles = profile_data.get('total_profiles', 0)
            
            if profile_index < 1 or profile_index > total_profiles:
                return {
                    "error": f"Invalid profile index. Available: 1-{total_profiles}",
                    "status": "failed"
                }
            
            print(f"[MCP_INFO] Starting collaborators scraping for profile index: {profile_index}")
            print(f"[MCP_INFO] Using session: {session_id}")
            
            return {
                "session_id": session_id,
                "profile_index": profile_index,
                "status": "started",
                "message": f"Collaborators scraping started for profile index {profile_index}",
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }
    
    async def _get_profile_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Session'daki tüm profil verilerini JSON formatında döndür"""
        try:
            session_id = arguments.get("session_id")
            
            # Eğer session_id verilmezse, en son oluşturulan session'ı bul
            if not session_id:
                session_id = await self._get_latest_session()
                if not session_id:
                    return {
                        "error": "No session ID provided and no recent sessions found. Please run search_profile first.",
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
            
            # main_profile.json'ı tamamen oku
            with open(main_profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            print(f"[MCP_INFO] Returning complete profile data for session: {session_id}")
            print(f"[MCP_INFO] Total profiles: {profile_data.get('total_profiles', 0)}")
            print(f"[MCP_INFO] Status: {profile_data.get('status', 'unknown')}")
            
            return {
                "status": "success",
                "session_id": session_id,
                "profile_data": profile_data
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def _get_latest_session(self) -> str:
        """En son oluşturulan session ID'sini döndür"""
        try:
            # Sessions directory'den en son oluşturulan session'ı bul
            if not SESSIONS_DIR.exists():
                return None
            
            session_dirs = [d for d in SESSIONS_DIR.iterdir() if d.is_dir() and d.name.startswith('session_')]
            if not session_dirs:
                return None
            
            # En son oluşturulan session'ı bul (timestamp'e göre)
            latest_session = max(session_dirs, key=lambda x: x.stat().st_mtime)
            return latest_session.name
            
        except Exception as e:
            print(f"[MCP_ERROR] Error finding latest session: {e}")
            return None
    


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
