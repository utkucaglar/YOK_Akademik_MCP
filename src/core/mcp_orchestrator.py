import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
try:
    from config.config import SESSIONS_DIR, SSE_EVENTS
except ImportError:
    # Fallback: Manuel path oluştur
    from pathlib import Path
    SESSIONS_DIR = Path(__file__).parent.parent.parent / "public" / "collaborator-sessions"
    SSE_EVENTS = {
        "main_profile_found": "main_profile_found",
        "main_profile_complete": "main_profile_complete", 
        "collaborator_found": "collaborator_found",
        "collaborators_complete": "collaborators_complete",
        "error": "error",
        "no_collaborators_found": "no_collaborators_found",
        "collaborators_completed": "collaborators_completed"
    }
    # Config fallback in use; suppress stdout

class ProcessState(Enum):
    INITIALIZING = "initializing"
    SCRAPING_MAIN = "scraping_main"
    ANALYZING = "analyzing"
    AWAITING_SELECTION = "awaiting_selection"
    SCRAPING_COLLABS = "scraping_collabs"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class SessionInfo:
    session_id: str
    state: ProcessState
    profiles: List[Dict] = None
    selected_profile: Optional[Dict] = None
    collaborators: List[Dict] = None
    error_message: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.profiles is None:
            self.profiles = []
        if self.collaborators is None:
            self.collaborators = []

class FileWatcher(FileSystemEventHandler):
    def __init__(self, orchestrator, session_id: str):
        self.orchestrator = orchestrator
        self.session_id = session_id
        self.session_dir = SESSIONS_DIR / session_id
    
    def on_modified(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.name == "main_profile.json":
                self.orchestrator.handle_main_profile_update(self.session_id)
            elif file_path.name == "collaborators.json":
                self.orchestrator.handle_collaborators_update(self.session_id)

class YOKAcademicAssistant:
    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.observers: Dict[str, Observer] = {}
        self.base_dir = Path(__file__).parent.parent.parent
        self.sessions_dir = SESSIONS_DIR
        
        
        # SSE subscribers: session_id -> list of asyncio.Queue
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
        # Gerekli dizinleri oluştur
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    
    def subscribe(self, session_id: str) -> asyncio.Queue:
        """Register an SSE subscriber queue for a session."""
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.setdefault(session_id, []).append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        """Remove the queue from subscribers for a session."""
        try:
            lst = self.subscribers.get(session_id, [])
            if q in lst:
                lst.remove(q)
            if not lst and session_id in self.subscribers:
                del self.subscribers[session_id]
        except Exception:
            pass
    def extract_user_info(self, query: str) -> Dict[str, Any]:
        """Kullanıcı sorgusundan isim bilgisini çıkar"""
        info = {
            "name": ""
        }
        
        # İsim genellikle ilk kelimeler
        words = query.strip().split()
        if words:
            # İlk 2-3 kelimeyi isim olarak al
            info["name"] = " ".join(words[:min(3, len(words))])
        
        return info
    
    def create_session_id(self) -> str:
        """Benzersiz session ID oluştur"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"session_{timestamp}_{unique_id}"
    
    def setup_file_watcher(self, session_id: str):
        """Dosya izleyici kur"""
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(exist_ok=True)
        
        event_handler = FileWatcher(self, session_id)
        observer = Observer()
        observer.schedule(event_handler, str(session_dir), recursive=False)
        observer.start()
        
        self.observers[session_id] = observer
    
    def cleanup_session(self, session_id: str):
        """Session temizliği"""
        if session_id in self.observers:
            self.observers[session_id].stop()
            self.observers[session_id].join()
            del self.observers[session_id]
        
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    async def start_main_profile_scraping(self, session_id: str, user_info: Dict[str, Any]) -> bool:
        """Ana profil scraping işlemini başlat"""
        try:
            print(f"[DEBUG] start_main_profile_scraping called with session_id: {session_id}, user_info: {user_info}")
            session_info = self.sessions[session_id]
            session_info.state = ProcessState.SCRAPING_MAIN
            
            # Komut oluştur
            cmd = [
                sys.executable,
                str(self.base_dir / "src" / "tools" / "scrape_main_profile.py"),
                user_info["name"],
                session_id
            ]
            
            print(f"[DEBUG] Command to execute: {cmd}")
            print(f"[DEBUG] Current working directory: {self.base_dir}")
            
            # Subprocess başlat
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=str(self.base_dir)
            )
            
            # stdout'u asenkron olarak oku
            async def read_output():
                # Suppressed stdout: reading subprocess output started
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        # Suppressed stdout: subprocess completed
                        break
                    if line:
                        # Suppressed stdout: forwarding log via SSE
                        await self.handle_scraping_log(session_id, line.strip())
                
                # Process tamamlandığında
                return_code = process.poll()
                if return_code != 0:
                    stderr_output = process.stderr.read()
                    await self.handle_scraping_error(session_id, f"Process failed with return code {return_code}: {stderr_output}")
                    return False
                
                return True
            
            # Arka planda çalıştır
            print(f"[DEBUG] Subprocess started with PID: {process.pid}")
            asyncio.create_task(read_output())
            print(f"[DEBUG] start_main_profile_scraping returning True")
            return True
            
        except Exception as e:
            await self.handle_scraping_error(session_id, f"Failed to start scraping: {str(e)}")
            return False
    
    async def handle_scraping_log(self, session_id: str, log_line: str):
        """Scraping log mesajlarını işle"""
        if session_id not in self.sessions:
            return
        
        # Log seviyesini belirle
        if "[ERROR]" in log_line:
            level = "error"
        elif "[WARNING]" in log_line:
            level = "warning"
        elif "[INFO]" in log_line:
            level = "info"
        elif "[DEBUG]" in log_line:
            level = "debug"
        else:
            level = "info"
        
        # SSE event gönder
        event_data = {
            "session_id": session_id,
            "event": "log_message",
            "data": {
                "source": "main_profile_scraping",
                "level": level,
                "message": log_line,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.send_sse_event(event_data)
        
        # Özel durumları kontrol et
        if "[COLLABORATORS]" in log_line:
            # Otomatik collaborator scraping başlatıldı
            await self.handle_auto_collaborator_start(session_id)
    
    async def handle_scraping_error(self, session_id: str, error_message: str):
        """Scraping hatasını işle"""
        if session_id in self.sessions:
            session_info = self.sessions[session_id]
            session_info.state = ProcessState.FAILED
            session_info.error_message = error_message
        
        event_data = {
            "session_id": session_id,
            "event": "error",
            "data": {
                "message": error_message,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.send_sse_event(event_data)
    
    def handle_main_profile_update(self, session_id: str):
        """main_profile.json güncellemesini işle"""
        try:
            main_profile_path = self.sessions_dir / session_id / "main_profile.json"
            main_done_path = self.sessions_dir / session_id / "main_done.txt"
            
            if not main_profile_path.exists():
                return
            
            with open(main_profile_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        # JSON parse hatası durumunda boş data kullan
                        data = {"profiles": [], "total_profiles": 0, "status": "failed", "searched_name": ""}
                else:
                    data = {"profiles": [], "total_profiles": 0, "status": "failed", "searched_name": ""}
            
            profiles = data.get('profiles', [])
            total_profiles = data.get('total_profiles', len(profiles))
            status = data.get('status', 'unknown')
            searched_name = data.get('searched_name', '')
            
            if session_id in self.sessions:
                self.sessions[session_id].profiles = profiles
            
            # Progress update gönder
            event_data = {
                "session_id": session_id,
                "event": "progress_update",
                "data": {
                    "profiles_found": len(profiles),
                    "total_profiles": total_profiles,
                    "status": status,
                    "searched_name": searched_name,
                    "limit": 100,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Asenkron olarak SSE event gönder
            try:
                asyncio.create_task(self.send_sse_event(event_data))
            except RuntimeError:
                # Event loop yoksa senkron olarak çalıştır
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.send_sse_event(event_data))
                except Exception as loop_error:
                    print(f"Error in event loop handling: {loop_error}")
                finally:
                    # Event loop'u düzgün şekilde kapat
                    try:
                        loop.close()
                    except:
                        pass
            
            # Main scraping tamamlandıysa ve sadece 1 profil varsa otomatik collaborator scraping başlat
            if main_done_path.exists() and len(profiles) == 1:
                # Eğer zaten collaborator scraping başlatılmışsa tekrar başlatma
                collaborators_done_path = self.sessions_dir / session_id / "collaborators_done.txt"
                if collaborators_done_path.exists():
                    return
                
                # Suppressed stdout: auto collaborator start
                
                # Terminal'de bilgi göster
                # Suppressed stdout: pretty banner
                
                # Asenkron olarak collaborator scraping başlat
                # Email odaklı minimal JSON durumunda profile URL olmayabilir
                first_profile = profiles[0]
                if "profile_url" not in first_profile or not first_profile.get("profile_url"):
                    # URL yoksa sadece uyarı yayımla; manuel seçim veya tam arama gerekebilir
                    url_missing_event = {
                        "session_id": session_id,
                        "event": "profile_url_missing",
                        "data": {
                            "message": "Seçilen profil için URL bulunamadı. İşbirlikçiler otomatik başlatılamadı.",
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    try:
                        asyncio.create_task(self.send_sse_event(url_missing_event))
                    except RuntimeError:
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.send_sse_event(url_missing_event))
                        except Exception:
                            pass
                        finally:
                            # Event loop'u düzgün şekilde kapat
                            try:
                                loop.close()
                            except:
                                pass
                else:
                    try:
                        asyncio.create_task(self.start_collaborator_scraping(session_id, first_profile))
                    except RuntimeError:
                        # Event loop yoksa senkron olarak çalıştır
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.start_collaborator_scraping(session_id, first_profile))
                        except Exception:
                            pass
                        finally:
                            # Event loop'u düzgün şekilde kapat
                            try:
                                loop.close()
                            except:
                                pass
            
        except Exception as e:
            pass
    
    def handle_collaborators_update(self, session_id: str):
        """collaborators.json güncellemesini işle"""
        try:
            collaborators_path = self.sessions_dir / session_id / "collaborators.json"
            if not collaborators_path.exists():
                return
            
            with open(collaborators_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    try:
                        collaborators = json.loads(content)
                    except json.JSONDecodeError:
                        # JSON parse hatası durumunda boş liste kullan
                        collaborators = []
                else:
                    collaborators = []
            
            if session_id in self.sessions:
                # Önceki collaborator sayısını kontrol et
                previous_count = len(self.sessions[session_id].collaborators) if self.sessions[session_id].collaborators else 0
                current_count = len(collaborators)
                
                # Session'daki collaborator listesini güncelle
                self.sessions[session_id].collaborators = collaborators
                
                # Collaborator bulunamadı durumunu kontrol et
                if current_count == 0 and previous_count == 0:
                    # İlk kez boş liste geldi - collaborator bulunamadı
                    event_data = {
                        "session_id": session_id,
                        "event": "no_collaborators_found",
                        "data": {
                            "message": "Seçilen profilin hiç collaborator'ı bulunamadı",
                            "total_count": 0,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    
                    # Asenkron olarak SSE event gönder
                    try:
                        asyncio.create_task(self.send_sse_event(event_data))
                    except RuntimeError:
                        # Event loop yoksa senkron olarak çalıştır
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.send_sse_event(event_data))
                        except Exception as loop_error:
                            print(f"Error in event loop handling: {loop_error}")
                        finally:
                            # Event loop'u düzgün şekilde kapat
                            try:
                                loop.close()
                            except:
                                pass
                    
                    # Done event'i de gönder
                    done_event_data = {
                        "session_id": session_id,
                        "event": "collaborators_completed",
                        "data": {
                            "message": "Collaborator scraping tamamlandı - Hiç collaborator bulunamadı",
                            "total_count": 0,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    
                    try:
                        asyncio.create_task(self.send_sse_event(done_event_data))
                    except RuntimeError:
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.send_sse_event(done_event_data))
                        except Exception as loop_error:
                            print(f"Error in done event loop handling: {loop_error}")
                        finally:
                            # Event loop'u düzgün şekilde kapat
                            try:
                                loop.close()
                            except:
                                pass
                
                # Sadece yeni collaborator eklendiyse event gönder
                elif current_count > previous_count and collaborators:
                    latest_collaborator = collaborators[-1]
                    event_data = {
                        "session_id": session_id,
                        "event": "collaborator_found",
                        "data": {
                            "collaborator": latest_collaborator,
                            "total_count": current_count,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    
                    # Asenkron olarak SSE event gönder
                    try:
                        asyncio.create_task(self.send_sse_event(event_data))
                    except RuntimeError:
                        # Event loop yoksa senkron olarak çalıştır
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.send_sse_event(event_data))
                            loop.close()
                        except Exception as loop_error:
                            print(f"Error in event loop handling: {loop_error}")
            
        except Exception as e:
            pass
    
    async def handle_auto_collaborator_start(self, session_id: str):
        """Otomatik collaborator scraping başlatıldığını işle"""
        if session_id in self.sessions:
            session_info = self.sessions[session_id]
            session_info.state = ProcessState.SCRAPING_COLLABS
        
        event_data = {
            "session_id": session_id,
            "event": "auto_collaborator_start",
            "data": {
                "message": "Email eşleşmesi bulundu, işbirlikçi analizi otomatik başlatıldı",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.send_sse_event(event_data)
    
    async def analyze_results(self, session_id: str):
        """Sonuçları analiz et ve karar ver"""
        try:
            session_info = self.sessions[session_id]
            session_info.state = ProcessState.ANALYZING
            
            main_profile_path = self.sessions_dir / session_id / "main_profile.json"
            if not main_profile_path.exists():
                await self.handle_no_results(session_id)
                return
            
            with open(main_profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            profiles = data.get('profiles', [])
            
            if not profiles:
                await self.handle_no_results(session_id)
            elif len(profiles) == 1:
                await self.handle_unique_profile(session_id, profiles[0])
            else:
                await self.handle_multiple_profiles(session_id, profiles)
                
        except Exception as e:
            await self.handle_scraping_error(session_id, f"Analysis failed: {str(e)}")
    
    async def handle_no_results(self, session_id: str):
        """Sonuç bulunamadı durumunu işle"""
        if session_id in self.sessions:
            self.sessions[session_id].state = ProcessState.COMPLETED
        
        event_data = {
            "session_id": session_id,
            "event": "no_results",
            "data": {
                "message": "Belirtilen kriterlere uygun akademisyen profili bulunamadı.",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.send_sse_event(event_data)
    
    async def handle_unique_profile(self, session_id: str, profile: Dict):
        """Tek profil bulundu durumunu işle"""
        if session_id in self.sessions:
            session_info = self.sessions[session_id]
            session_info.selected_profile = profile
            session_info.state = ProcessState.SCRAPING_COLLABS
        
        event_data = {
            "session_id": session_id,
            "event": "unique_profile_found",
            "data": {
                "profile": profile,
                "message": "Tek bir eşleşme bulundu. İşbirlikçi analizi başlatılıyor...",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.send_sse_event(event_data)
        
        # Otomatik collaborator scraping başlat
        await self.start_collaborator_scraping(session_id, profile)
    
    async def handle_multiple_profiles(self, session_id: str, profiles: List[Dict]):
        """Birden çok profil bulundu durumunu işle"""
        if session_id in self.sessions:
            self.sessions[session_id].state = ProcessState.AWAITING_SELECTION
        
        event_data = {
            "session_id": session_id,
            "event": "multiple_profiles_found",
            "data": {
                "profiles": profiles,
                "message": "Birden fazla profil bulundu. Lütfen işbirlikçilerini görmek istediğiniz profili seçin.",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.send_sse_event(event_data)
    
    async def start_collaborator_scraping(self, session_id: str, profile: Dict):
        """İşbirlikçi scraping işlemini başlat"""
        try:
            session_info = self.sessions[session_id]
            session_info.state = ProcessState.SCRAPING_COLLABS
            
            # Suppressed stdout: collaborator scraping start banner
            
            # Komut oluştur
            cmd = [
                sys.executable,
                str(self.base_dir / "src" / "tools" / "scrape_collaborators.py"),
                profile["name"],
                session_id,
                "--profile-url",
                profile["profile_url"]
            ]
            
            # Subprocess başlat
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=str(self.base_dir)
            )
            
            # stdout'u asenkron olarak oku
            async def read_collaborator_output():
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        await self.handle_collaborator_log(session_id, line.strip())
                
                # Process tamamlandığında
                return_code = process.poll()
                if return_code == 0:
                    await self.handle_collaborator_completion(session_id)
                else:
                    stderr_output = process.stderr.read()
                    await self.handle_scraping_error(session_id, f"Collaborator scraping failed: {stderr_output}")
            
            # Arka planda çalıştır
            asyncio.create_task(read_collaborator_output())
            
        except Exception as e:
            await self.handle_scraping_error(session_id, f"Failed to start collaborator scraping: {str(e)}")
    
    async def handle_collaborator_log(self, session_id: str, log_line: str):
        """Collaborator scraping log mesajlarını işle"""
        if session_id not in self.sessions:
            return
        
        # Log seviyesini belirle
        if "[ERROR]" in log_line:
            level = "error"
        elif "[WARNING]" in log_line:
            level = "warning"
        elif "[INFO]" in log_line:
            level = "info"
        elif "[DEBUG]" in log_line:
            level = "debug"
        else:
            level = "info"
        
        # SSE event gönder
        event_data = {
            "session_id": session_id,
            "event": "log_message",
            "data": {
                "source": "collaborator_scraping",
                "level": level,
                "message": log_line,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.send_sse_event(event_data)
    
    async def handle_collaborator_completion(self, session_id: str):
        """Collaborator scraping tamamlandığını işle"""
        if session_id in self.sessions:
            session_info = self.sessions[session_id]
            session_info.state = ProcessState.COMPLETED
        
        # Sonuçları oku
        collaborators_path = self.sessions_dir / session_id / "collaborators.json"
        total_collaborators = 0
        collaborators = []
        if collaborators_path.exists():
            with open(collaborators_path, 'r', encoding='utf-8') as f:
                collaborators = json.load(f)
                total_collaborators = len(collaborators)
        
        # Suppressed stdout: completion banner and list
        
        event_data = {
            "session_id": session_id,
            "event": "process_complete",
            "data": {
                "message": f"Tarama tamamlandı. Toplam {total_collaborators} işbirlikçi bulundu.",
                "total_collaborators": total_collaborators,
                "results_path": f"/collaborator-sessions/{session_id}/",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await self.send_sse_event(event_data)

    async def send_sse_event(self, event_data: Dict):
        """Publish SSE event to all subscribers of this session."""
        try:
            session_id = event_data.get("session_id")
            if not session_id:
                session_id = event_data.get("data", {}).get("session_id")
            payload = json.dumps(event_data, ensure_ascii=False)
            targets = self.subscribers.get(session_id, [])
            for q in list(targets):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    continue
        except Exception as e:
            print(f"[SSE_PUBLISH_ERROR] {e}", file=sys.stderr)

    async def process_user_request(self, query: str) -> str:
        """Kullanıcı isteğini işle"""
        try:
            # Kullanıcı bilgilerini çıkar
            user_info = self.extract_user_info(query)
            
            # Session oluştur
            session_id = self.create_session_id()
            session_info = SessionInfo(
                session_id=session_id,
                state=ProcessState.INITIALIZING
            )
            self.sessions[session_id] = session_info
            
            # File watcher kur
            self.setup_file_watcher(session_id)
            
            # Session başlatma eventi gönder
            event_data = {
                "session_id": session_id,
                "event": "session_started",
                "data": {
                    "message": "Akademisyen arama oturumu başlatıldı...",
                    "user_info": user_info,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            await self.send_sse_event(event_data)
            
            # Ana profil scraping başlat
            success = await self.start_main_profile_scraping(session_id, user_info)
            
            if not success:
                return f"Session {session_id} başlatılamadı."
            
            return f"Session {session_id} başarıyla başlatıldı. SSE eventleri takip edin."
            
        except Exception as e:
            return f"Hata oluştu: {str(e)}"
    
    def get_session_status(self, session_id: str) -> Optional[Dict]:
        """Session durumunu al"""
        if session_id not in self.sessions:
            return None
        
        session_info = self.sessions[session_id]
        return {
            "session_id": session_id,
            "state": session_info.state.value,
            "profiles_count": len(session_info.profiles),
            "collaborators_count": len(session_info.collaborators) if session_info.collaborators else 0,
            "selected_profile": session_info.selected_profile,
            "error_message": session_info.error_message,
            "created_at": session_info.created_at.isoformat()
        }

# Global orchestrator instance
orchestrator = YOKAcademicAssistant()

# Test fonksiyonu
async def test_orchestrator():
    """Test fonksiyonu"""
    query = "Ahmet Yılmaz adlı araştırmacıyı bulur musun?"
    result = await orchestrator.process_user_request(query)
    # Suppressed stdout in test

if __name__ == "__main__":
    # Test çalıştır
    asyncio.run(test_orchestrator())
