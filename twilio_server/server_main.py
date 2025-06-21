#!/usr/bin/env python3
"""
AI God Project - Main Entry Point
A sophisticated voice assistant system with dual personalities.
"""

import os
import sys
import asyncio
import logging
import hashlib
import subprocess
import time
import signal
import json
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, send_from_directory
from twilio.twiml.voice_response import VoiceResponse
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Import our modular components
from twilio_server.src import (
    config,
    logger,  # This is our centralized logger
    personality_manager,
    tts_manager,
    speech_recognizer,
    user_manager,
    interaction_coordinator,
    performance_monitor,
    entertainment_manager,
    log_structured_data
)
from twilio_server.src.sounds import SoundManager

# Initialize Flask app
app = Flask(__name__)

# Configure rate limiter with memory storage
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="memory://",
    strategy="fixed-window",
    default_limits=["200 per day", "50 per hour", "20 per minute"]
)

# Log rate limiter configuration
log_structured_data(
    logging.INFO,
    "rate_limiter_config",
    {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "storage": "memory",
        "strategy": "fixed-window",
        "limits": ["200 per day", "50 per hour", "20 per minute"]
    }
)

# Suppress noisy logs using the logging module
for logger_name in ['flask_limiter', 'werkzeug', 'urllib3', 'pygame']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

# Custom filter to remove emoji and clean up logs
class CleanLogFilter(logging.Filter):
    def filter(self, record):
        # Remove emoji and asterisks
        record.msg = record.msg.replace('🔊', '').replace('*', '')
        return True

# Add filter to our logger
logger.addFilter(CleanLogFilter())

# Initialize sound manager (only once)
sound_manager = SoundManager()

# Load environment variables
load_dotenv()

# Ensure required environment variables
required_env_vars = ["OPENAI_API_KEY", "ELEVENLABS_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize paths (using absolute path so that Flask always serves from twilio_server/static/cached_responses)
CACHE_DIR = config.paths.CACHE_DIR
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
CACHED_RESPONSES_DIR = STATIC_DIR / "cached_responses"
CACHED_RESPONSES_DIR.mkdir(exist_ok=True)

# Configure Flask to serve static files
app.static_folder = str(STATIC_DIR)
app.static_url_path = '/static'

# Define common response files
WELCOME_FILE = CACHED_RESPONSES_DIR / "welcome.mp3"
FALLBACK_FILE = CACHED_RESPONSES_DIR / "fallback.mp3"
EXIT_FILE = CACHED_RESPONSES_DIR / "exit.mp3"

# Store preloaded responses
PRELOADED_RESPONSES = {}

# Log startup information in a structured way
log_structured_data(
    logging.INFO,
    "server_startup",
    {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "configuration": {
            "cache_dir": str(CACHE_DIR),
            "static_dir": str(STATIC_DIR),
            "cached_responses_dir": str(CACHED_RESPONSES_DIR),
            "rate_limiter": {
                "storage": "memory",
                "strategy": "fixed-window",
                "limits": ["200 per day", "50 per hour", "20 per minute"]
            }
        },
        "components": {
            "flask": "initialized",
            "rate_limiter": "initialized",
            "sound_manager": "initialized"
        }
    }
)

def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    try:
        cmd = f"lsof -i :{port} -t"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return bool(result.stdout.strip())
    except Exception:
        return False

def kill_process_on_port(port: int) -> None:
    """Kill any process using the specified port."""
    try:
        cmd = f"lsof -i :{port} -t"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            pid = result.stdout.strip()
            logger.debug(f"Killing process {pid} on port {port}")
            subprocess.run(f"kill -9 {pid}", shell=True)
            for _ in range(5):
                if not is_port_in_use(port):
                    logger.debug(f"Port {port} freed")
                    return
                time.sleep(1)
            logger.warning(f"Port {port} still in use")
        else:
            logger.debug(f"Port {port} is free")
    except Exception as e:
        logger.error(f"Error freeing port {port}: {e}")

async def initialize_application():
    """Initialize all application components."""
    try:
        logger.info("Application initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        return False

############################### Flask Routes ###############################

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return {"status": "OK", "version": "1.0.0"}, 200

@app.route("/static/cached_responses/<path:filename>")
def serve_cached_response(filename):
    """Serve cached response files."""
    try:
        log_structured_data(
            logging.INFO,
            "static_file_request",
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "filename": filename,
                "primary_dir": str(CACHED_RESPONSES_DIR),
                "file_exists": (CACHED_RESPONSES_DIR / filename).exists()
            }
        )
        
        # First, try serving from twilio_server/static/cached_responses (using CACHED_RESPONSES_DIR).
        if (CACHED_RESPONSES_DIR / filename).exists():
            log_structured_data(
                logging.INFO,
                "static_file_served",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "filename": filename,
                    "directory": str(CACHED_RESPONSES_DIR)
                }
            )
            return send_from_directory(str(CACHED_RESPONSES_DIR), filename)
            
        # Fallback: try serving from the project root's static/cached_responses folder.
        fallback_dir = Path(__file__).parent.parent / "static" / "cached_responses"
        if fallback_dir.exists() and (fallback_dir / filename).exists():
            log_structured_data(
                logging.INFO,
                "static_file_served_fallback",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "filename": filename,
                    "directory": str(fallback_dir)
                }
            )
            return send_from_directory(str(fallback_dir), filename)
            
        # If we get here, the file wasn't found in either location
        log_structured_data(
            logging.ERROR,
            "static_file_not_found",
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "filename": filename,
                "primary_dir": str(CACHED_RESPONSES_DIR),
                "fallback_dir": str(fallback_dir),
                "primary_exists": (CACHED_RESPONSES_DIR / filename).exists(),
                "fallback_exists": (fallback_dir / filename).exists() if fallback_dir.exists() else False
            }
        )
        return "File not found", 404
        
    except Exception as e:
        log_structured_data(
            logging.ERROR,
            "static_file_error",
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "filename": filename,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        return str(e), 500

@app.route("/voice", methods=["POST", "GET"])
async def voice():
    """Main voice interaction endpoint."""
    try:
        response = VoiceResponse()
        call_status = request.values.get("CallStatus", "")
        call_sid = request.values.get("CallSid", "unknown")
        call_duration = int(request.values.get("CallDuration", "0"))
        
        # Handle GET requests (Twilio status callbacks)
        if request.method == "GET":
            # Log the GET request with full context
            log_structured_data(
                logging.INFO,
                "twilio_callback",
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "method": "GET",
                    "call_status": call_status,
                    "call_sid": call_sid,
                    "error_code": request.values.get("ErrorCode", "none"),
                    "error_url": request.values.get("ErrorUrl", "none"),
                    "duration": call_duration
                }
            )
            
            # Handle various call statuses
            if call_status in ["completed", "failed", "busy", "no-answer", "canceled"]:
                log_structured_data(
                    logging.INFO,
                    "call_ended",
                    {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "call_sid": call_sid,
                        "status": call_status,
                        "duration": call_duration
                    }
                )
                return str(response)
            
            # For other GET requests (like status updates), return empty response
            return str(response)
        
        # Handle initial greeting
        if not request.values.get("SpeechResult") and call_status == "ringing":
            log_structured_data(
                logging.INFO,
                "call_started",
                {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "call_sid": call_sid,
                    "trunk_sid": config.twilio.TRUNK_SID
                }
            )
            
            # Get welcome message
            welcome_file = await interaction_coordinator.handle_welcome()
            if welcome_file:
                # Play wake sound first
                wake_sound_url = await sound_manager.play_wake_sound()
                if wake_sound_url:
                    response.play(wake_sound_url)
                # Then play welcome message
                response.play(f"/static/cached_responses/{welcome_file}")
            
            # Set 3-minute time limit using dial with Trunk SID
            dial = response.dial(timeLimit=180)  # 180 seconds = 3 minutes
            dial.sip(f"sip:{config.twilio.TRUNK_SID}@sip.twilio.com")  # Use Trunk SID for dialing
            
            # Always gather for next input
            response.gather(
                input="speech",
                action="/voice",
                method="POST",
                timeout=5,
                speechTimeout="auto"
            )
            return str(response)
        
        # Get user input and confidence
        user_input = request.values.get("SpeechResult", "").strip()
        confidence = float(request.values.get("Confidence", 0))
        
        # Log the incoming request with confidence
        log_structured_data(
            logging.INFO,
            "speech_recognized",
            {
                "timestamp": time.strftime("%H:%M:%S"),
                "input": user_input,
                "confidence": f"{confidence:.2f}",
                "call_sid": call_sid,
                "call_duration": call_duration
            }
        )
        
        # Check if we're approaching the time limit (2:30)
        if call_duration >= 150 and call_duration < 180 and not interaction_coordinator.interaction_metrics.get("time_warning_given"):  # Between 2:30 and 3:00
            warning_file = await interaction_coordinator.handle_time_warning()
            if warning_file:
                response.play(f"/static/cached_responses/{warning_file}")
                interaction_coordinator.interaction_metrics["time_warning_given"] = True
            # Continue with normal flow after warning
        
        # Handle empty input
        if not user_input:
            log_structured_data(
                logging.INFO,
                "empty_input",
                {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "confidence": f"{confidence:.2f}",
                    "call_sid": call_sid,
                    "call_duration": call_duration
                }
            )
            fallback_file = await interaction_coordinator.handle_fallback()
            if fallback_file:
                response.play(f"/static/cached_responses/{fallback_file}")
            response.gather(
                input="speech",
                action="/voice",
                method="POST",
                timeout=5,
                speechTimeout="auto"
            )
            return str(response)
        
        # Process user input through the coordinator
        try:
            await interaction_coordinator.handle_user_input(user_input)
        except Exception as e:
            log_structured_data(
                logging.ERROR,
                "coordinator_error",
                {
                    "error": str(e),
                    "input": user_input,
                    "confidence": f"{confidence:.2f}",
                    "call_sid": call_sid,
                    "call_duration": call_duration
                }
            )
            fallback_file = await interaction_coordinator.handle_fallback()
            if fallback_file:
                response.play(f"/static/cached_responses/{fallback_file}")
            response.gather(
                input="speech",
                action="/voice",
                method="POST",
                timeout=5,
                speechTimeout="auto"
            )
            return str(response)
        
        # Get the response file from the coordinator's metrics
        response_file = interaction_coordinator.interaction_metrics.get("response_file")
        
        # Handle exit command with doom sound
        if "exit" in user_input.lower():
            log_structured_data(
                logging.INFO,
                "exit_command_detected",
                {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "input": user_input,
                    "confidence": f"{confidence:.2f}",
                    "call_sid": call_sid,
                    "call_duration": call_duration
                }
            )
            # Play doom sound first
            doom_sound_url = await sound_manager.play_doom_sound()
            if doom_sound_url:
                response.play(doom_sound_url)
            # Then play the farewell message
            if response_file:
                response.play(f"/static/cached_responses/{response_file}")
            # End call after exit
            response.hangup()
            return str(response)
        
        # If this was a voice switch, play the void sound first
        if any(phrase in user_input.lower() for phrase in ["switch to", "switched to", "change to", "changed to", "become", "became", "be", "is"]):
            void_sound_url = await sound_manager.play_void_sound()
            if void_sound_url:
                response.play(void_sound_url)
        
        # Then play the response
        if response_file:
            # First try the twilio_server/static/cached_responses directory
            response_path = CACHED_RESPONSES_DIR / response_file
            if response_path.exists():
                response.play(f"/static/cached_responses/{response_file}")
            else:
                # Try fallback first
                fallback_file = await interaction_coordinator.handle_fallback()
                if fallback_file:
                    response.play(f"/static/cached_responses/{fallback_file}")
                # Only say error message if no fallback was available
                elif not fallback_file:  # Explicitly check for None
                    response.say("I'm having trouble with my voice right now. Please try again.")
        else:
            # No response file generated, try fallback
            fallback_file = await interaction_coordinator.handle_fallback()
            if fallback_file:
                response.play(f"/static/cached_responses/{fallback_file}")
            # Only say error message if no fallback was available
            elif not fallback_file:  # Explicitly check for None
                response.say("I'm having trouble with my voice right now. Please try again.")
        
        # Always gather for next input
        response.gather(
            input="speech",
            action="/voice",
            method="POST",
            timeout=5,
            speechTimeout="auto"
        )
        return str(response)

    except Exception as e:
        log_structured_data(
            logging.ERROR,
            "server_error",
            {
                "error": str(e),
                "route": "/voice",
                "call_sid": request.values.get("CallSid", "unknown"),
                "call_status": request.values.get("CallStatus", "unknown")
            }
        )
        response = VoiceResponse()
        personality = interaction_coordinator.personality_manager.current_personality
        if personality == "major_tom":
            response.say("Ground Control, we're experiencing technical difficulties. Please try again.")
        else:
            response.say("A moment of patience, please. Let me resolve this.")
        response.gather(
            input="speech",
            action="/voice",
            method="POST",
            timeout=5,
            speechTimeout="auto"
        )
        return str(response)

############################### Error Handlers ###############################

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler."""
    call_sid = request.values.get("CallSid", "unknown")
    call_status = request.values.get("CallStatus", "unknown")
    
    log_structured_data(
        logging.ERROR,
        "unhandled_exception",
        {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e),
            "error_type": type(e).__name__,
            "call_sid": call_sid,
            "call_status": call_status,
            "route": request.endpoint,
            "method": request.method
        }
    )
    
    response = VoiceResponse()
    personality = interaction_coordinator.personality_manager.current_personality
    
    if personality == "major_tom":
        response.say("Ground Control, we're experiencing technical difficulties. Please try again.")
    else:
        response.say("A moment of patience, please. Let me resolve this.")
    
    # Always gather for next input
    response.gather(
        input="speech",
        action="/voice",
        method="POST",
        timeout=5,
        speechTimeout="auto"
    )
    return str(response), 500

@app.errorhandler(429)
def rate_limit_exceeded(e):
    """Rate limit exceeded handler with personality-specific responses."""
    remote_address = get_remote_address()
    current_limits = str(limiter.current_limits)
    call_sid = request.values.get("CallSid", "unknown")
    call_status = request.values.get("CallStatus", "unknown")
    
    # Get current personality for response
    personality = interaction_coordinator.personality_manager.current_personality
    
    # Log the rate limit with more context
    log_structured_data(
        logging.WARNING,
        "rate_limit_exceeded",
        {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "remote_address": remote_address,
            "personality": personality,
            "limits": current_limits,
            "request_method": request.method,
            "endpoint": request.endpoint,
            "call_sid": call_sid,
            "call_status": call_status,
            "call_duration": request.values.get("CallDuration", "0")
        }
    )
    
    # Create response with personality-specific message
    response = VoiceResponse()
    if personality == "major_tom":
        response.say("Ground Control to Major Tom... your request frequency is too high. Please wait 5 seconds before trying again.")
    else:
        response.say("Please wait a moment before making another request. Let us proceed.")
    
    # Add a shorter pause before gathering again
    response.pause(length=5)  # 5 second pause for better UX
    
    # Then gather for next input
    response.gather(
        input="speech",
        action="/voice",
        method="POST",
        timeout=5,
        speechTimeout="auto"
    )
    return str(response), 429

@app.errorhandler(405)
def method_not_allowed(e):
    """Method not allowed handler with proper logging."""
    call_sid = request.values.get("CallSid", "unknown")
    call_status = request.values.get("CallStatus", "unknown")
    
    # Log the method not allowed with full context
    log_structured_data(
        logging.WARNING,
        "method_not_allowed",
        {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method": request.method,
            "url": request.url,
            "remote_address": get_remote_address(),
            "call_sid": call_sid,
            "call_status": call_status,
            "error_code": request.values.get("ErrorCode", "none"),
            "call_duration": request.values.get("CallDuration", "0")
        }
    )
    
    # Create response
    response = VoiceResponse()
    personality = interaction_coordinator.personality_manager.current_personality
    
    if personality == "major_tom":
        response.say("Ground Control, we're experiencing a communication protocol mismatch. Please try again.")
    else:
        response.say("A moment of patience, please. Let me resolve this.")
    
    # Add a short pause
    response.pause(length=2)
    
    # Then gather for next input
    response.gather(
        input="speech",
        action="/voice",
        method="POST",
        timeout=5,
        speechTimeout="auto"
    )
    return str(response), 405

############################### Main Entry Point ###############################

if __name__ == "__main__":
    try:
        logger.info("Starting AI God Project...")
        
        port = int(os.getenv("PORT", 5001))
        if is_port_in_use(port):
            logger.info("Port in use, freeing...")
            kill_process_on_port(port)
            if is_port_in_use(port):
                logger.error("Could not free port. Please try again.")
                sys.exit(1)
        
        def signal_handler(signum, frame):
            logger.info("Shutting down...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if not asyncio.run(initialize_application()):
            logger.error("Initialization failed")
            sys.exit(1)
        
        host = os.getenv("HOST", "0.0.0.0")
        logger.info(f"Server ready on {host}:{port}")
        app.run(host=host, port=port, debug=False)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        logger.info("Server stopped") 