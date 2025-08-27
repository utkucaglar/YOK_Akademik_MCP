#!/usr/bin/env python3
"""
Smithery Configuration Middleware
Extracts configuration from URL parameters for custom container deployments
"""

import json
import base64
import logging
from urllib.parse import parse_qs, unquote

logger = logging.getLogger(__name__)

class SmitheryConfigMiddleware:
    """Middleware to extract Smithery configuration from URL parameters"""
    
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') == 'http':
            query = scope.get('query_string', b'').decode()
            
            if 'config=' in query:
                try:
                    config_b64 = unquote(parse_qs(query)['config'][0])
                    config = json.loads(base64.b64decode(config_b64))
                    
                    # Store config in scope for request handlers to access
                    scope['smithery_config'] = config
                    logger.info(f"Extracted Smithery config: {list(config.keys())}")
                except Exception as e:
                    logger.warning(f"Failed to parse config from URL: {e}")
                    scope['smithery_config'] = {}
            else:
                scope['smithery_config'] = {}
        
        await self.app(scope, receive, send)
