#!/usr/bin/env python3
"""
Quick launcher for the Visual Logger server.
Run this script to start the monitoring dashboard.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visual_logger.server import run_server

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Visual Logger Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=8765, help="Port to listen on (default: 8765)")
    
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port)

