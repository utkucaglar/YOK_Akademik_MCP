#!/usr/bin/env python3
"""
YÖK Akademik MCP Server - Smithery Deployment Entry Point

Bu modül Smithery platformu için optimize edilmiş giriş noktasıdır.
python -m server komutuyla çalıştırılır.
"""

import os
import sys
import logging
from pathlib import Path

# Ensure the project root is in Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def setup_environment():
    """Smithery deployment için gerekli environment variables"""
    # Minimal defaults for faster startup
    defaults = {
        'MCP_SERVER_HOST': '0.0.0.0',
        'MCP_SERVER_PORT': '8000',
        'HEADLESS_MODE': 'true',
        'CHROME_BIN': '/usr/bin/chromium',
        'PYTHON_ENV': 'production',
        'CORS_ENABLED': 'true',
        'SSE_HEARTBEAT_INTERVAL': '60',  # Increased for less resource usage
        'MAX_CONCURRENT_SESSIONS': '5'   # Reduced for less memory usage
    }
    
    # Set defaults if not already set
    for key, value in defaults.items():
        if key not in os.environ:
            os.environ[key] = value

def setup_logging():
    """Production logging setup"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Simple logging for container environment
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=== YÖK Akademik MCP Server Starting ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Server host: {os.getenv('MCP_SERVER_HOST')}")
    logger.info(f"Server port: {os.getenv('MCP_SERVER_PORT')}")
    logger.info(f"Chrome binary: {os.getenv('CHROME_BIN')}")
    logger.info(f"Headless mode: {os.getenv('HEADLESS_MODE')}")
    
    return logger

def ensure_directories():
    """Create necessary directories"""
    directories = [
        'public/collaborator-sessions',
        'logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

def main():
    """Main entry point for Smithery deployment"""
    try:
        # Setup environment and logging
        setup_environment()
        logger = setup_logging()
        ensure_directories()
        
        # Get host and port from environment
        host = os.getenv('MCP_SERVER_HOST', '0.0.0.0')
        port = int(os.getenv('MCP_SERVER_PORT', '8000'))
        
        logger.info(f"Starting MCP server on {host}:{port}")
        
        # Import and start the MCP server
        from mcp_server_streaming_real import create_app, run_server
        
        app = create_app()
        run_server(app, host, port)
        
    except Exception as e:
        print(f"Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
