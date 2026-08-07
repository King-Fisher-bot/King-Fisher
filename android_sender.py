#!/usr/bin/env python3
"""
King Fisher - Android Data Sender
This script runs on Android device via Termux and sends SMS/Call logs to the bot.

Requirements:
- Termux (F-Droid version)
- termux-api package
- Python 3.8+

Installation:
pkg update && pkg upgrade
pkg install python termux-api termux-tools
pip install requests

Usage:
export BOT_API_URL="https://your-bot-url.onrender.com"
export SECRET_KEY="your-secret-key"
export DEVICE_ID="my_android_phone"
python android_sender.py
"""

import os
import json
import time
import logging
import subprocess
import requests
from datetime import datetime
from typing import List, Dict, Optional

# ============ CONFIGURATION ============
BOT_API_URL = os.getenv("BOT_API_URL", "").rstrip("/")
SECRET_KEY = os.getenv("SECRET_KEY", "")
DEVICE_ID = os.getenv("DEVICE_ID", f"android_{os.uname().nodename if hasattr(os, 'uname') else 'device'}")
INTERVAL = int(os.getenv("INTERVAL", "30"))  # seconds
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "10"))  # items per request

# ============ LOGGING ============
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("KingFisher-Android")

# ============ VALIDATION ============
if not BOT_API_URL:
    logger.error("❌ BOT_API_URL environment variable is required!")
    logger.error("   Example: export BOT_API_URL=https://your-bot.onrender.com")
    exit(1)

if not SECRET_KEY:
    logger.warning("⚠️  SECRET_KEY not set. Using default (not recommended)")
    SECRET_KEY = "default_secret_key_change_me"

# ============ CORE CLASS ============
class AndroidDataSender:
    """Main class for collecting and sending Android data"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "X-Device-ID": DEVICE_ID,
            "X-Secret-Key": SECRET_KEY,
            "Content-Type": "application/json"
        })
        self.last_sms_ids = set()
        self.last_call_ids = set()
        self.is_termux = self._check_termux()
        
        if not self.is_termux:
            logger.warning("⚠️  Not running in Termux environment")
            logger.warning("   Some features may not work properly")
    
    def _check_termux(self) -> bool:
        """Check if running in Termux environment"""
        try:
            subprocess.run(["termux-info"], capture_output=True, check=True)
            return True
        except:
            return False
    
    def _run_termux_command(self, cmd: List[str]) -> Optional[str]:
        """Run a termux command and return output"""
        if not self.is_termux:
            return None
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout
            else:
                logger.error(f"Command failed: {' '.join(cmd)}")
                logger.error(f"Error: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"Command timeout: {' '.join(cmd)}")
            return None
        except Exception as e:
            logger.error(f"Error running command: {e}")
            return None
    
    def get_sms_messages(self, limit: int = 10) -> List[Dict]:
        """Get recent SMS messages using termux-api"""
        if not self.is_termux:
            return self._get_mock_sms()
        
        output = self._run_termux_command(["termux-sms-list", "-l", str(limit)])
        if not output:
            return []
        
        try:
            sms_list = json.loads(output)
            return sms_list
        except json.JSONDecodeError:
            logger.error("Failed to parse SMS data")
            return []
    
    def get_call_logs(self, limit: int = 10) -> List[Dict]:
        """Get recent call logs using termux-api"""
        if not self.is_termux:
            return self._get_mock_calls()
        
        output = self._run_termux_command(["termux-call-log", "-l", str(limit)])
        if not output:
            return []
        
        try:
            call_list = json.loads(output)
            return call_list
        except json.JSONDecodeError:
            logger.error("Failed to parse call log data")
            return []
    
    def _get_mock_sms(self) -> List[Dict]:
        """Return mock SMS data for testing (non-Termux)"""
        return [
            {
                "id": "mock_1",
                "address": "+8801712345678",
                "body": "Hello! This is a test message from King Fisher.",
                "date": datetime.now().isoformat(),
                "type": 1
            },
            {
                "id": "mock_2",
                "address": "+8801812345678",
                "body": "Your OTP is 123456. Please verify within 5 minutes.",
                "date": datetime.now().isoformat(),
                "type": 1
            }
        ]
    
    def _get_mock_calls(self) -> List[Dict]:
        """Return mock call data for testing (non-Termux)"""
        return [
            {
                "id": "mock_1",
                "number": "+8801712345678",
                "display_name": "Test Contact",
                "duration": "45",
                "date": datetime.now().isoformat(),
                "type": 1
            },
            {
                "id": "mock_2",
                "number": "+8801812345678",
                "display_name": "Unknown",
                "duration": "0",
                "date": datetime.now().isoformat(),
                "type": 3
            }
        ]
    
    def format_sms(self, sms: Dict) -> Dict:
        """Format SMS for API submission"""
        return {
            "id": str(sms.get("_id", sms.get("id", "unknown"))),
            "sender": sms.get("address", "Unknown"),
            "body": sms.get("body", "")[:500],
            "timestamp": sms.get("date", datetime.now().isoformat()),
            "type": "received" if sms.get("type", 1) in [1, 2] else "sent"
        }
    
    def format_call(self, call: Dict) -> Dict:
        """Format call log for API submission"""
        call_types = {
            1: "Incoming",
            2: "Outgoing", 
            3: "Missed",
            4: "Voicemail",
            5: "Rejected",
            6: "Blocked"
        }
        return {
            "id": str(call.get("_id", call.get("id", "unknown"))),
            "number": call.get("number", "Unknown"),
            "name": call.get("display_name", "Unknown"),
            "duration": str(call.get("duration", "0")),
            "timestamp": call.get("date", datetime.now().isoformat()),
            "type": call_types.get(call.get("type", 1), "Unknown")
        }
    
    def send_to_bot(self, data_type: str, data: List[Dict]) -> bool:
        """Send data to the bot API"""
        if not data:
            return True
        
        try:
            payload = {
                "device_id": DEVICE_ID,
                "type": data_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            response = self.session.post(
                f"{BOT_API_URL}/device/data",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Sent {len(data)} {data_type} items to bot")
                return True
            else:
                logger.error(f"❌ Failed to send data: {response.status_code}")
                logger.error(f"   Response: {response.text[:200]}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection error: Cannot reach bot server")
            return False
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout: Bot server not responding")
            return False
        except Exception as e:
            logger.error(f"❌ Error sending data: {e}")
            return False
    
    def collect_and_send(self):
        """Main collection and send logic"""
        logger.info(f"📱 Collecting data from device: {DEVICE_ID}")
        
        # Get SMS messages
        sms_list = self.get_sms_messages(MAX_ITEMS)
        if sms_list:
            new_sms = []
            for sms in sms_list:
                sms_id = str(sms.get("_id", sms.get("id", "")))
                if sms_id and sms_id not in self.last_sms_ids:
                    new_sms.append(self.format_sms(sms))
                    self.last_sms_ids.add(sms_id)
            
            if new_sms:
                self.send_to_bot("sms", new_sms)
        
        # Get call logs
        call_list = self.get_call_logs(MAX_ITEMS)
        if call_list:
            new_calls = []
            for call in call_list:
                call_id = str(call.get("_id", call.get("id", "")))
                if call_id and call_id not in self.last_call_ids:
                    new_calls.append(self.format_call(call))
                    self.last_call_ids.add(call_id)
            
            if new_calls:
                self.send_to_bot("call", new_calls)
    
    def run(self):
        """Main loop"""
        logger.info("=" * 50)
        logger.info("👑 KING FISHER - ANDROID DATA SENDER")
        logger.info("=" * 50)
        logger.info(f"📱 Device ID: {DEVICE_ID}")
        logger.info(f"🔗 Bot URL: {BOT_API_URL}")
        logger.info(f"⏱️  Interval: {INTERVAL}s")
        logger.info(f"📦 Max Items: {MAX_ITEMS}")
        logger.info(f"🔐 Termux Mode: {self.is_termux}")
        logger.info("=" * 50)
        logger.info("🔄 Starting data collection...")
        logger.info("Press Ctrl+C to stop\n")
        
        try:
            while True:
                try:
                    self.collect_and_send()
                except Exception as e:
                    logger.error(f"Error in collection loop: {e}")
                
                time.sleep(INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("\n👋 Shutting down gracefully...")
            logger.info("✅ Goodbye!")

# ============ MAIN ============
if __name__ == "__main__":
    sender = AndroidDataSender()
    sender.run()