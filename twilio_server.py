#!/usr/bin/env python3
"""
AI Assistant Project - Twilio Server Entry Point
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Import Twilio server components
from twilio_server import app, initialize_application, SoundManager
from twilio_server.src import logger
from twilio_server.server_main import kill_process_on_port, is_port_in_use

if __name__ == "__main__":
    try:
        logger.info("Starting AI Assistant Project Twilio Server...")
        
        port = int(os.getenv("PORT", 5001))
        host = os.getenv("HOST", "0.0.0.0")
        # Free the port if in use
        if is_port_in_use(port):
            logger.info(f"Port {port} in use, freeing...")
            kill_process_on_port(port)
            if is_port_in_use(port):
                logger.error(f"Could not free port {port}. Please try again.")
                sys.exit(1)
        
        if not asyncio.run(initialize_application()):
            logger.error("Initialization failed")
            sys.exit(1)
        
        logger.info(f"Server ready on {host}:{port}")
        app.run(host=host, port=port, debug=False)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("Server stopped")