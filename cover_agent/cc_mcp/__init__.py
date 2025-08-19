"""
Cover Agent MCP Package

This package provides Model Context Protocol (MCP) integration for Cover Agent,
allowing AI models to access Cover Agent's test generation and coverage analysis capabilities.
"""

__version__ = "1.0.0"
__author__ = "Cover Agent Team"

from .hybrid_server import HybridCoverAgentMCPServer

__all__ = [
    "HybridCoverAgentMCPServer",
]
