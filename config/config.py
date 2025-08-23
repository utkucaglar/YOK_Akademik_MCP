#!/usr/bin/env python3
"""
YÖK Akademik Asistanı - Konfigürasyon Dosyası
Proje genelinde kullanılan ayarlar ve sabitler
"""

import os
from pathlib import Path

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent.parent

# Session dosyaları için dizin
SESSIONS_DIR = PROJECT_ROOT / "public" / "collaborator-sessions"

# SSE Events için endpoint
SSE_EVENTS = {
    "main_profile_found": "main_profile_found",
    "main_profile_complete": "main_profile_complete", 
    "collaborator_found": "collaborator_found",
    "collaborators_complete": "collaborators_complete",
    "error": "error",
    "no_collaborators_found": "no_collaborators_found",
    "collaborators_completed": "collaborators_completed"
}

# YÖK Akademik platform URL'leri
YOK_BASE_URL = "https://akademik.yok.gov.tr/"
YOK_SEARCH_URL = f"{YOK_BASE_URL}AkademikArama/"

# Web scraping ayarları
WEBDRIVER_OPTIONS = {
    "headless": True,
    "disable_gpu": True,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "window_size": (1920, 1080),
    "prefs": {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
    }
}

# Timeout ayarları (saniye)
TIMEOUTS = {
    "page_load": 15,
    "element_wait": 10,
    "cookie_button": 5,
    "search_results": 15
}

# Dosya ayarları
FILE_SETTINGS = {
    "encoding": "utf-8",
    "json_indent": 2,
    "ensure_ascii": False
}

# Session ayarları
SESSION_SETTINGS = {
    "max_sessions": 100,
    "session_timeout": 3600,  # 1 saat
    "cleanup_interval": 300   # 5 dakika
}

# Logging ayarları
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S"
}

# MCP Server ayarları
MCP_SERVER_CONFIG = {
    "host": "localhost",
    "port": 5000,
    "protocol_version": "2024-11-05",
    "server_name": "YOK Academic MCP Server",
    "server_version": "1.0.0"
}

# Scraping ayarları
SCRAPING_CONFIG = {
    "max_profiles_per_search": 50,
    "max_collaborators_per_profile": 100,
    "retry_attempts": 3,
    "retry_delay": 2,
    "save_photos": True,
    "photo_quality": 0.8
}

# Fields.json dosya yolu
FIELDS_FILE = PROJECT_ROOT / "public" / "fields.json"

# Backup ayarları
BACKUP_CONFIG = {
    "enable_backup": True,
    "backup_suffix": ".backup",
    "max_backups": 5
}

# SSE Streaming ayarları
SSE_CONFIG = {
    "content_type": "text/event-stream",
    "cache_control": "no-cache",
    "connection": "keep-alive",
    "retry_interval": 3000  # milisaniye
}

# Error mesajları
ERROR_MESSAGES = {
    "session_not_found": "Session bulunamadı",
    "profile_not_found": "Profil bulunamadı",
    "scraping_failed": "Scraping işlemi başarısız",
    "timeout_error": "Zaman aşımı hatası",
    "network_error": "Ağ bağlantı hatası",
    "invalid_input": "Geçersiz giriş parametresi"
}

# Başarı mesajları
SUCCESS_MESSAGES = {
    "session_created": "Session başarıyla oluşturuldu",
    "profiles_found": "Profil(ler) bulundu",
    "collaborators_found": "İşbirlikçi(ler) bulundu",
    "scraping_completed": "Scraping işlemi tamamlandı"
}

# Emoji'ler (terminal output için)
EMOJIS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "search": "🔍",
    "profile": "👤",
    "collaborator": "👥",
    "institution": "🏢",
    "email": "📧",
    "title": "📋",
    "loading": "⏳",
    "complete": "🎉"
}

# CSS Selector'lar (web scraping için)
CSS_SELECTORS = {
    "search_input": "#aramaTerim",
    "search_button": "#searchButton",
    "cookie_button": "//button[contains(text(),'Tümünü Kabul Et')]",
    "profile_cards": ".card",
    "profile_header": ".profile-header",
    "profile_name": "h1",
    "profile_title": ".title",
    "profile_institution": ".institution",
    "profile_email": ".email",
    "profile_photo": "img",
    "collaborator_tabs": ".nav-tabs .nav-link",
    "collaborator_items": ".collaborator-item, .collaborator-card, .collaborator",
    "collaborator_name": "h3, h4, .name, .title",
    "collaborator_title": ".title, .position, .rank",
    "collaborator_institution": ".institution, .university, .faculty",
    "collaborator_email": ".email, a[href^='mailto:']"
}

# Process state enum'ları
class ProcessState:
    INITIALIZING = "INITIALIZING"
    MAIN_PROFILE_SCRAPING = "MAIN_PROFILE_SCRAPING"
    AWAITING_SELECTION = "AWAITING_SELECTION"
    COLLABORATOR_SCRAPING = "COLLABORATOR_SCRAPING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"

# Session info class
class SessionInfo:
    def __init__(self, session_id: str, state: str = ProcessState.INITIALIZING):
        from datetime import datetime
        self.session_id = session_id
        self.state = state
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.selected_profile = None
        self.error_message = None
        self.progress = 0.0  # 0.0 to 1.0

# Dizinleri oluştur
def ensure_directories():
    """Gerekli dizinlerin varlığını kontrol et ve oluştur"""
    directories = [
        SESSIONS_DIR,
        PROJECT_ROOT / "public",
        PROJECT_ROOT / "logs"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ Dizin kontrol edildi: {directory}")

# Konfigürasyonu doğrula
def validate_config():
    """Konfigürasyon ayarlarını doğrula"""
    errors = []
    
    # Dizinlerin yazılabilir olduğunu kontrol et
    if not os.access(SESSIONS_DIR, os.W_OK):
        errors.append(f"SESSIONS_DIR yazılabilir değil: {SESSIONS_DIR}")
    
    # Fields.json dosyasının varlığını kontrol et
    if not FIELDS_FILE.exists():
        errors.append(f"FIELDS_FILE bulunamadı: {FIELDS_FILE}")
    
    if errors:
        print("❌ Konfigürasyon hataları:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("✅ Konfigürasyon doğrulandı")
    return True

# Başlangıçta dizinleri oluştur
if __name__ == "__main__":
    ensure_directories()
    validate_config()

