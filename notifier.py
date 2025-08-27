"""
Notifier - Telegram notification module
Handles all outbound messaging to your phone
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root explicitly to avoid CWD issues
BASE_DIR = Path(__file__).resolve().parent
# Force .env to override any existing OS env vars to avoid stale values
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

# Configuration
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LOG_FILE = "logs/notifications.jsonl"

logger = logging.getLogger(__name__)

def notify(text: str, parse_mode: str = "Markdown") -> bool:
    """
    Send notification to Telegram
    
    Args:
        text: Message text to send
        parse_mode: Telegram parse mode (Markdown or HTML)
    
    Returns:
        bool: Success status
    """
    if not (CHAT_ID and BOT_TOKEN):
        logger.warning("Telegram credentials not configured")
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": parse_mode
            },
            timeout=10
        )
        
        if response.status_code == 200:
            log_event("notification_sent", {"message": text[:100]})
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False

def notify_with_file(text: str, file_path: str, caption: Optional[str] = None) -> bool:
    """
    Send notification with a file attachment
    
    Args:
        text: Message text
        file_path: Path to file to attach
        caption: Optional caption for the file
    
    Returns:
        bool: Success status
    """
    if not (CHAT_ID and BOT_TOKEN):
        logger.warning("Telegram credentials not configured")
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                url,
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption or text,
                    "parse_mode": "Markdown"
                },
                files={"document": f},
                timeout=30
            )
        
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"Failed to send file: {e}")
        return False

def notify_progress(task_id: str, stage: str, details: Optional[str] = None):
    """
    Send progress update notification
    
    Args:
        task_id: Task identifier
        stage: Current stage (e.g., "building", "testing", "complete")
        details: Optional additional details
    """
    icons = {
        "queued": "⏳",
        "processing": "⚙️",
        "building": "🔨",
        "testing": "🧪",
        "complete": "✅",
        "failed": "❌",
        "warning": "⚠️"
    }
    
    icon = icons.get(stage, "📋")
    msg = f"{icon} Task `{task_id}` - {stage}"
    
    if details:
        msg += f"\n{details}"
    
    notify(msg)

def log_event(event_type: str, data: Dict[str, Any]):
    """
    Log an event to the notifications log
    
    Args:
        event_type: Type of event
        data: Event data
    """
    event = {
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        "data": data
    }
    
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event) + '\n')
    except Exception as e:
        logger.error(f"Failed to log event: {e}")

def send_summary(tasks_processed: int, successes: int, failures: int):
    """
    Send daily summary notification
    
    Args:
        tasks_processed: Total tasks processed
        successes: Number of successful tasks
        failures: Number of failed tasks
    """
    msg = (
        f"📊 *Daily Summary*\n\n"
        f"📥 Tasks processed: {tasks_processed}\n"
        f"✅ Successful: {successes}\n"
        f"❌ Failed: {failures}\n"
        f"📈 Success rate: {(successes/tasks_processed*100):.1f}%" if tasks_processed > 0 else "No tasks"
    )
    
    notify(msg)

def test_connection() -> bool:
    """
    Test Telegram connection
    
    Returns:
        bool: Connection status
    """
    if not (CHAT_ID and BOT_TOKEN):
        print("❌ Missing TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN in .env")
        return False
    
    success = notify("🔗 Connection test successful!")
    
    if success:
        print("✅ Telegram connection working")
    else:
        print("❌ Failed to connect to Telegram")
    
    return success

if __name__ == "__main__":
    # Test the notifier when run directly
    import sys
    
    if len(sys.argv) > 1:
        # Send custom message
        message = " ".join(sys.argv[1:])
        if notify(message):
            print(f"✅ Sent: {message}")
        else:
            print("❌ Failed to send message")
    else:
        # Run connection test
        test_connection()
