"""
Bridge Bot - Telegram interface for receiving task directives
Handles commands, voice notes, and task queuing
"""

import json
import time
import uuid
import argparse
import logging
import subprocess
import tempfile
import shlex
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os
import sys
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes
)
from telegram.request import HTTPXRequest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bridge_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Paths
BASE = Path(__file__).resolve().parent
INBOX = Path("tasks/inbox")
INBOX.mkdir(parents=True, exist_ok=True)

# AutoHotkey configuration
AHK_EXE = r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"  # Adjust if needed
SEND_AHK = str(BASE / "send_to.ahk")

HELP_TEXT = """
📋 *Available Commands:*

/task <directive> - Create a new task for Claude
/note <text> - Add a note to the last task
/to <target> <message> - Send to ChatGPT/Claude/Cursor
/status - Check runner status
/list - List pending tasks
/clear - Clear completed tasks
/help - Show this help message

*Examples:*
`/task Implement RMB click handler for unit selection`
`/note Add unit tests for the selection logic`
`/to chatgpt Explain this architecture`
`/to claude Generate unit tests for OrderQueue`
`/to cursor Run build and show output`
"""

def new_card(kind: str, text: str, user_id: int = None) -> dict:
    """Create a new task card"""
    return {
        "id": f"task-{uuid.uuid4().hex[:8]}",
        "created_ts": int(time.time()),
        "created_at": datetime.now().isoformat(),
        "kind": kind,  # task|note
        "text": text.strip(),
        "attachments": [],
        "status": "queued",
        "user_id": user_id
    }

def get_last_task() -> dict:
    """Get the most recent task from inbox"""
    tasks = sorted(INBOX.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if tasks:
        return json.loads(tasks[-1].read_text(encoding="utf-8"))
    return None

def send_to_desktop(target: str, text: str) -> str:
    """
    Send text to desktop application via AutoHotkey
    
    Args:
        target: Target application (chatgpt, claude, cursor)
        text: Text to send
        
    Returns:
        Status message
    """
    # Check if AutoHotkey is installed
    if not os.path.exists(AHK_EXE):
        return "❌ AutoHotkey v2 not found. Please install from https://www.autohotkey.com/"
    
    if not os.path.exists(SEND_AHK):
        return "❌ send_to.ahk script not found"
    
    # Create temp file with message
    tmp = BASE / "tasks" / "inbox" / f"msg_{uuid.uuid4().hex[:8]}.txt"
    
    try:
        # Write message to temp file
        tmp.write_text(text, encoding="utf-8")
        
        # Run AutoHotkey script
        result = subprocess.run(
            [AHK_EXE, SEND_AHK, target, str(tmp)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            error_msg = result.stderr[:400] if result.stderr else "Unknown error"
            return f"❌ AHK error (code {result.returncode}):\n{error_msg}"
        
        # Success
        return f"✅ Sent to {target.capitalize()}"
        
    except subprocess.TimeoutExpired:
        return "❌ Timeout - AutoHotkey took too long"
    except Exception as e:
        logger.error(f"Error sending to {target}: {e}")
        return f"❌ Error: {str(e)[:200]}"
    finally:
        # Clean up temp file
        if tmp.exists():
            try:
                tmp.unlink()
            except:
                pass

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n"
        f"Your chat ID is: `{chat_id}`\n\n"
        f"Add this to your .env file as TELEGRAM_CHAT_ID\n\n"
        f"{HELP_TEXT}",
        parse_mode='Markdown'
    )

async def cmd_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Create a new task"""
    text = " ".join(ctx.args).strip()
    if not text:
        await update.message.reply_text(
            "Usage: /task <directive>\n"
            "Example: /task Implement player movement system"
        )
        return
    
    card = new_card("task", text, update.effective_user.id)
    task_file = INBOX / f"{card['id']}.json"
    task_file.write_text(json.dumps(card, ensure_ascii=False, indent=2))
    
    logger.info(f"Created task {card['id']}: {text[:50]}...")
    
    await update.message.reply_text(
        f"✅ Task queued: `{card['id']}`\n"
        f"📝 {text[:100]}{'...' if len(text) > 100 else ''}",
        parse_mode='Markdown'
    )

async def cmd_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Add a note to the last task"""
    text = " ".join(ctx.args).strip()
    if not text:
        await update.message.reply_text("Usage: /note <text>")
        return
    
    last_task = get_last_task()
    if not last_task:
        await update.message.reply_text("❌ No task found. Create one with /task first")
        return
    
    # Append note to the last task
    task_file = INBOX / f"{last_task['id']}.json"
    if task_file.exists():
        last_task['text'] += f"\n\nNote: {text}"
        task_file.write_text(json.dumps(last_task, ensure_ascii=False, indent=2))
        
        await update.message.reply_text(
            f"📎 Note added to `{last_task['id']}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Task file not found")

async def cmd_to(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Send message to desktop application (ChatGPT, Claude, or Cursor)
    Usage: /to <chatgpt|claude|cursor> <message>
    """
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Usage: /to <target> <message>\n\n"
            "Targets:\n"
            "• `chatgpt` - Send to ChatGPT\n"
            "• `claude` - Send to Claude\n"
            "• `cursor` - Send to Cursor IDE\n\n"
            "Example: `/to claude Write unit tests for the inventory system`",
            parse_mode='Markdown'
        )
        return
    
    target = ctx.args[0].lower()
    valid_targets = ["chatgpt", "claude", "cursor"]
    
    if target not in valid_targets:
        await update.message.reply_text(
            f"❌ Invalid target: `{target}`\n"
            f"Use one of: {', '.join(valid_targets)}",
            parse_mode='Markdown'
        )
        return
    
    # Get the message text (everything after the target)
    text = " ".join(ctx.args[1:])
    
    # Show typing indicator
    await update.message.chat.send_action(action="typing")
    
    # Send to desktop
    result = send_to_desktop(target, text)
    
    # Log the action
    logger.info(f"Sent to {target}: {text[:50]}...")
    
    # Send result
    await update.message.reply_text(result, parse_mode='Markdown')

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Check system status"""
    inbox_count = len(list(INBOX.glob("*.json")))
    processing_count = len(list(Path("tasks/processing").glob("*.json")))
    done_count = len(list(Path("tasks/done").glob("*.json")))
    
    # Check AutoHotkey
    ahk_status = "✅ Installed" if os.path.exists(AHK_EXE) else "❌ Not found"
    
    status_msg = (
        f"📊 *System Status*\n\n"
        f"📥 Inbox: {inbox_count} tasks\n"
        f"⚙️ Processing: {processing_count} tasks\n"
        f"✅ Completed: {done_count} tasks\n"
        f"\n🔄 Runner polls every {os.getenv('POLL_INTERVAL_SEC', '5')} seconds\n"
        f"🎯 AutoHotkey v2: {ahk_status}"
    )
    
    await update.message.reply_text(status_msg, parse_mode='Markdown')

async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """List pending tasks"""
    tasks = sorted(INBOX.glob("*.json"), key=lambda p: p.stat().st_mtime)
    
    if not tasks:
        await update.message.reply_text("📭 No pending tasks")
        return
    
    msg = "📋 *Pending Tasks:*\n\n"
    for task_path in tasks[-10:]:  # Show last 10
        try:
            task = json.loads(task_path.read_text(encoding="utf-8"))
            msg += f"• `{task['id']}` - {task['text'][:50]}...\n"
        except:
            continue
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Clear completed tasks"""
    done_dir = Path("tasks/done")
    done_files = list(done_dir.glob("*.json"))
    
    if not done_files:
        await update.message.reply_text("No completed tasks to clear")
        return
    
    # Archive instead of deleting
    archive_dir = Path("tasks/archive") / datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    for f in done_files:
        f.rename(archive_dir / f.name)
    
    await update.message.reply_text(
        f"🗑️ Archived {len(done_files)} completed tasks to `{archive_dir.name}`",
        parse_mode='Markdown'
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    await update.message.reply_text(HELP_TEXT, parse_mode='Markdown')

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages"""
    text = update.message.text.strip()
    
    # If it looks like a task directive, create a task
    if len(text) > 10:
        card = new_card("task", text, update.effective_user.id)
        task_file = INBOX / f"{card['id']}.json"
        task_file.write_text(json.dumps(card, ensure_ascii=False, indent=2))
        
        await update.message.reply_text(
            f"✅ Task created: `{card['id']}`\n"
            f"💡 Tip: Use /task for explicit task creation",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "Use /task to create a task or /help for commands"
        )

async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages (placeholder for future Whisper integration)"""
    await update.message.reply_text(
        "🎤 Voice notes not yet implemented.\n"
        "Use /task <text> for now"
    )

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Telegram Bridge Bot")
    parser.add_argument("--print-chat-id", action="store_true",
                       help="Print chat ID for setup")
    args = parser.parse_args()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: Set TELEGRAM_BOT_TOKEN in .env file")
        print("1. Create bot with @BotFather on Telegram")
        print("2. Copy the token to .env file")
        sys.exit(1)
    
    # Build application with increased HTTP timeouts for slow networks
    req = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30)
    app = ApplicationBuilder().token(token).request(req).build()
    
    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("note", cmd_note))
    app.add_handler(CommandHandler("to", cmd_to))  # New command
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    logger.info("Bridge bot starting...")
    print("Bridge Bot is running!")
    print("Send /start to your bot to get your chat ID")
    print("\nNEW: Use /to to send messages to ChatGPT, Claude, or Cursor!")
    
    # Run bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
