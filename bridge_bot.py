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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters, 
    ContextTypes
)
from telegram.request import HTTPXRequest
import mss
import mss.tools

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
UPLOADS = Path("tasks/uploads")
INBOX.mkdir(parents=True, exist_ok=True)
UPLOADS.mkdir(parents=True, exist_ok=True)

# Simple token → file-path index for callback data (keeps callback_data <= 64 bytes)
UPLOAD_INDEX = UPLOADS / "index.json"

def _load_upload_index() -> dict:
    try:
        return json.loads(UPLOAD_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_upload_index(data: dict):
    try:
        UPLOAD_INDEX.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass

def _put_upload_token(path: Path) -> str:
    data = _load_upload_index()
    token = uuid.uuid4().hex[:12]
    data[token] = str(path)
    # Keep index from growing unbounded
    if len(data) > 2000:
        # drop oldest roughly by recreating with last 1500
        items = list(data.items())[-1500:]
        data = {k: v for k, v in items}
    _save_upload_index(data)
    return token

def _get_upload_path(token: str) -> Path | None:
    data = _load_upload_index()
    p = data.get(token)
    return Path(p) if p else None

def _build_file_reference_message(path: Path) -> str:
    """Create the requested directive line that points to tasks/uploads."""
    rel_hint = f"tasks/uploads/{path.name}"
    return f"check {rel_hint} and proceed"

# AutoHotkey configuration
AHK_EXE = r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"  # Adjust if needed
SEND_AHK = str(BASE / "send_to.ahk")

HELP_TEXT = """
📋 *Available Commands:*

/task <directive> - Create a new task for Claude
/note <text> - Add a note to the last task
/to <target> <message> - Send to ChatGPT/Claude/Cursor (new cursor: opens new agent)
/query <claude|cursor> <message> - Direct send (no quick-input)
/sendfile <target> - Send the last uploaded file's content to a target
/stop <target> - Stop/interrupt in Cursor/Claude
/move <path> - Focus Cursor and open folder to the given path
/move cursor <path> - Same as above; explicit target prefix
/custom <keys> - Send global key input without focusing
/custom <cursor|claude> <keys> - Focus target and send custom input
/new cursor <filename> - Focus Cursor, open project, create file, confirm
/focus <cursor|claude|chrome> - Focus a desktop app window
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
    
    # Special STOP mode: invoke AHK without creating a temp file
    if isinstance(text, str) and text.strip().upper() == "STOP":
        try:
            result = subprocess.run(
                [AHK_EXE, SEND_AHK, target, "STOP"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                error_msg = result.stderr[:400] if result.stderr else "Unknown error"
                return f"❌ AHK error (code {result.returncode}):\n{error_msg}"
            return f"✅ Sent to {target.capitalize()}"
        except subprocess.TimeoutExpired:
            return "❌ Timeout - AutoHotkey took too long"
        except Exception as e:
            logger.error(f"Error sending to {target}: {e}")
            return f"❌ Error: {str(e)[:200]}"

    # Create temp file with message for normal SEND/FILE flows
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
    valid_targets = ["chatgpt", "claude", "cursor", "claude_direct", "cursor_direct"]
    
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

async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send STOP to a desktop application (cursor/claude)"""
    if not ctx.args or len(ctx.args) < 1:
        await update.message.reply_text("Usage: /stop <cursor|claude>")
        return
    target = ctx.args[0].lower()
    if target not in ["cursor", "cursor_direct", "claude", "claude_direct"]:
        await update.message.reply_text("Target must be cursor or claude")
        return
    # Use the STOP mode in AHK by passing special token
    result = send_to_desktop(target, "STOP")
    await update.message.reply_text(result)

async def cmd_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Directly send to Claude/Cursor without quick-input flow"""
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Usage: /query <claude|cursor> <message>")
        return
    target = ctx.args[0].lower()
    if target not in ["claude", "cursor"]:
        await update.message.reply_text("Target must be 'claude' or 'cursor'")
        return
    text = " ".join(ctx.args[1:])
    await update.message.chat.send_action(action="typing")
    mapped = "claude_direct" if target == "claude" else "cursor_direct"
    result = send_to_desktop(mapped, text)
    await update.message.reply_text(result, parse_mode='Markdown')

async def cmd_move(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Open a folder in Cursor by sending Ctrl+M and path input.
    Usage:
      /move <relative-or-absolute-path>
      /move cursor <relative-or-absolute-path>
    """
    if not ctx.args:
        await update.message.reply_text("Usage: /move <path> OR /move cursor <path>")
        return
    args = [a.strip() for a in ctx.args if a.strip()]
    if not args:
        await update.message.reply_text("Usage: /move <path> OR /move cursor <path>")
        return
    # Optional target prefix (currently only 'cursor' supported)
    if args[0].lower() == "cursor":
        rel = " ".join(args[1:]).strip()
    else:
        rel = " ".join(args).strip()
    await update.message.chat.send_action(action="typing")
    result = send_to_desktop("cursor_move", rel)
    await update.message.reply_text(result)

async def cmd_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send custom key chords, globally or to a focused target.
    Usage:
      /custom <keys>
      /custom <cursor|claude> <keys>
    Examples:
      /custom winkey+up
      /custom ctrl+shift+esc
      /custom cursor ctrl+j
      /custom claude text:"hello" , ctrl+enter
    """
    if not ctx.args:
        await update.message.reply_text("Usage: /custom <keys> OR /custom <cursor|claude> <keys>")
        return
    await update.message.chat.send_action(action="typing")
    # Global mode if first arg isn't a known target
    if len(ctx.args) == 1 or ctx.args[0].lower() not in ["cursor", "claude"]:
        keys = " ".join(ctx.args)
        result = send_to_desktop("custom", keys)
        await update.message.reply_text(result)
        return
    # Targeted mode
    target = ctx.args[0].lower()
    keys = " ".join(ctx.args[1:])
    mapped = "cursor_custom" if target == "cursor" else "claude_custom"
    result = send_to_desktop(mapped, keys)
    await update.message.reply_text(result)

async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Create a new file in Cursor via automation.
    Usage: /new cursor <filename>
    """
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Usage: /new cursor <filename>")
        return
    target = ctx.args[0].lower()
    if target != "cursor":
        await update.message.reply_text("Only supported target is 'cursor'")
        return
    filename = " ".join(ctx.args[1:]).strip()
    if not filename:
        await update.message.reply_text("Provide a filename, e.g. /new cursor README.md")
        return
    await update.message.chat.send_action(action="typing")
    result = send_to_desktop("cursor_new", filename)
    await update.message.reply_text(result)

async def cmd_focus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Focus a desktop application window.
    Usage: /focus <cursor|claude|chrome>
    """
    if not ctx.args or len(ctx.args) < 1:
        await update.message.reply_text("Usage: /focus <cursor|claude|chrome>")
        return
    target = ctx.args[0].lower()
    valid = ["cursor", "claude", "chrome"]
    if target not in valid:
        await update.message.reply_text("Target must be one of: cursor, claude, chrome")
        return
    await update.message.chat.send_action(action="typing")
    result = send_to_desktop("focus", target)
    await update.message.reply_text(result)

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

async def cmd_snap(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Capture a desktop screenshot and send it back"""
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            temp_path = BASE / f"screenshot_{uuid.uuid4().hex[:8]}.png"
            mss.tools.to_png(img.rgb, img.size, output=str(temp_path))
        await update.message.reply_photo(photo=open(temp_path, 'rb'))
    except Exception as e:
        await update.message.reply_text(f"❌ Screenshot failed: {e}")
    finally:
        try:
            if 'temp_path' in locals() and Path(temp_path).exists():
                Path(temp_path).unlink()
        except:
            pass

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Upload the latest report .md using the new convention.
    Usage:
      /report cursor <projectname>  -> ../claudeprojects/{projectname}/directives/reports/cursorreports/
      /report claude <projectname>  -> ../claudeprojects/{projectname}/directives/reports/claudereports/
    """
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Usage: /report <cursor|claude> <projectname>")
        return
    target = ctx.args[0].strip().lower()
    project = " ".join(ctx.args[1:]).strip()
    if target not in ["cursor", "claude"]:
        await update.message.reply_text("First argument must be 'cursor' or 'claude'.")
        return
    try:
        subfolder = "cursorreports" if target == "cursor" else "claudereports"
        base_dir = (BASE.parent / project / "directives" / "reports").resolve()
        reports_dir = (base_dir / subfolder)
        if not reports_dir.exists():
            await update.message.reply_text(
                f"❌ Reports directory not found for `{target}` `{project}`\nPath: `{reports_dir}`",
                parse_mode='Markdown'
            )
            return
        files = sorted(reports_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
        if not files:
            await update.message.reply_text("📭 No .md reports found in that reports directory")
            return
        latest = files[-1]
        await update.message.reply_document(
            document=open(latest, 'rb'),
            caption=f"📄 Latest {target} report from `{project}`: `{latest.name}`",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send report: {e}")

ALLOWED_FILE_EXTS = {".md", ".txt", ".patch", ".diff", ".png", ".jpg", ".jpeg", ".pdf"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

def _read_uploaded_as_text(path: Path) -> str:
    """Return a safe textual representation for various file types."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            text = "\n\n".join((p.extract_text() or "").strip() for p in reader.pages)
            return text
        except Exception:
            return ""
    if ext in {".png", ".jpg", ".jpeg"}:
        return f"Image uploaded: {path.name}. Please analyze the content contextually."
    # Default to utf-8 text with replacement for any errors
    return path.read_text(encoding="utf-8", errors="replace")

async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle small directive files (.md/.txt/.patch/.diff)"""
    doc = update.message.document
    if not doc:
        return
    name = doc.file_name or "file"
    ext = Path(name).suffix.lower()
    size = doc.file_size or 0
    if ext not in ALLOWED_FILE_EXTS or size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"Only {', '.join(sorted(ALLOWED_FILE_EXTS))} up to 15MB are accepted.")
        return

    # Download to uploads directory
    tg_file = await doc.get_file()
    dest = UPLOADS / f"{int(time.time())}_{name}"
    await tg_file.download_to_drive(custom_path=str(dest))
    ctx.chat_data["last_upload"] = str(dest)
    token = _put_upload_token(dest)

    # Inline keyboard to choose target without needing a caption
    buttons = [
        [InlineKeyboardButton("ChatGPT", callback_data=f"sendfile:chatgpt:{token}")],
        [InlineKeyboardButton("Claude (Opus flow)", callback_data=f"sendfile:claude:{token}")],
        [InlineKeyboardButton("Claude (direct)", callback_data=f"sendfile:claude_direct:{token}")],
        [InlineKeyboardButton("Cursor (new agent)", callback_data=f"sendfile:cursor:{token}")],
        [InlineKeyboardButton("Cursor (direct)", callback_data=f"sendfile:cursor_direct:{token}")]
    ]
    await update.message.reply_text(
        f"📎 Uploaded `{name}` ({size} bytes). Choose where to send:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def cmd_sendfile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send the last uploaded file's content to a desktop target"""
    if not ctx.args:
        await update.message.reply_text("Usage: /sendfile <chatgpt|claude|cursor>")
        return
    target = ctx.args[0].lower()
    if target not in ["chatgpt", "claude", "cursor", "claude_direct", "cursor_direct"]:
        await update.message.reply_text("Invalid target.")
        return

    # Prefer per-chat last upload; fallback to newest in uploads
    path = ctx.chat_data.get("last_upload")
    if not path:
        files = sorted(UPLOADS.glob("*"))
        if files:
            path = str(files[-1])
    if not path or not Path(path).exists():
        await update.message.reply_text("No uploaded file found.")
        return

    try:
        # Instead of sending file content, send a reference to the file path/name
        message = _build_file_reference_message(Path(path))
        result = send_to_desktop(target, message)
        await update.message.reply_text(result)
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send file: {e}")

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    if not query.data.startswith("sendfile:"):
        return
    try:
        _, target, token = query.data.split(":", 2)
    except ValueError:
        return
    path = _get_upload_path(token)
    if not path.exists():
        await query.edit_message_text("File no longer available.")
        return
    try:
        message = _build_file_reference_message(path)
        result = send_to_desktop(target, message)
        await query.edit_message_text(f"{result}")
    except Exception as e:
        await query.edit_message_text(f"❌ Failed to send file: {e}")

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
    app.add_handler(CommandHandler("query", cmd_query))
    app.add_handler(CommandHandler("move", cmd_move))
    app.add_handler(CommandHandler("custom", cmd_custom))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("focus", cmd_focus))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("snap", cmd_snap))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
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
