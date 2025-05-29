#!/usr/bin/env python3
"""
配置包
"""

from .settings import (
    get_config, 
    validate_azure_config, 
    print_config_info,
    AZURE_CONFIG,
    EDGE_CONFIG, 
    TTS_CONFIG,
    FLASK_CONFIG,
    CORS_CONFIG,
    LANGUAGE_NAMES
)

__all__ = [
    'get_config',
    'validate_azure_config', 
    'print_config_info',
    'AZURE_CONFIG',
    'EDGE_CONFIG',
    'TTS_CONFIG', 
    'FLASK_CONFIG',
    'CORS_CONFIG',
    'LANGUAGE_NAMES'
] 