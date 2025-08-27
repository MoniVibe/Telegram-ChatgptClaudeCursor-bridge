# 🎯 LLM Orchestrator - Mobile Task Bridge

A lightweight system that lets you send tasks from your phone to Claude while walking, which then generates code patches for your local repository.

## 🏗️ Architecture

```
Phone (Telegram) → Bridge Bot → Task Queue → Claude Runner → Git Patches → Local Build
                                                ↓
                                           Notification
```

## 🚀 Quick Start

### 1. Initial Setup

```bash
cd <your_path>\orchestrator

# Run interactive setup
python setup.py

# Install AutoHotkey v2 (for desktop integration)
# Download from: https://www.autohotkey.com/
```

### 2. Configure Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow instructions
3. Copy the bot token to `.env` file
4. Run `python bridge_bot.py` and send `/start` to your bot
5. Copy your chat ID to `.env` file

### 3. Configure Claude API

1. Get API key from [Anthropic Console](https://console.anthropic.com/)
2. Add to `.env` as `ANTHROPIC_API_KEY`

### 4. Start the System

**Windows:**
```cmd
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

## 📱 Mobile Commands

Send these to your Telegram bot:

- `/task <directive>` - Create a new task
- `/note <text>` - Add note to last task
- `/to <target> <message>` - Send to ChatGPT/Claude/Cursor
- `/status` - Check system status
- `/list` - Show pending tasks
- `/help` - Show all commands

### Example Tasks

```
/task Implement player movement with WASD keys, add jump on spacebar

/task Add unit tests for the inventory system

/task Refactor render loop to use double buffering
```

### Direct Desktop Messaging (NEW!)

```
# Send to ChatGPT for high-level planning
/to chatgpt Design a state machine for enemy AI behavior

# Send to Claude for code generation
/to claude Implement OrderQueue with priority sorting and unit tests

# Send to Cursor for local execution
/to cursor Run the test suite and show coverage report
```

## 🔧 Configuration

### Core Settings

Edit `.env` file:

```env
# Claude/OpenAI API
ANTHROPIC_API_KEY=YOUR_API
OPENAI_API_KEY=YOUR_API

# Telegram
TELEGRAM_BOT_TOKEN=YOUR_API
TELEGRAM_CHAT_ID=YOUR_CHAT_ID

# Repository
REPO_PATH=YOUR_REPO_PATH
DEFAULT_BRANCH=main

# Build Commands (customize for your project)
BUILD_CMD=cmake --build build --config Release
TEST_CMD=ctest --test-dir build

# Runner Settings
POLL_INTERVAL_SEC=5
```

## 📁 Directory Structure

```
orchestrator/
├── tasks/
│   ├── inbox/      # New tasks from phone
│   ├── processing/ # Currently being processed
│   └── done/       # Completed tasks
├── logs/           # System logs
├── bridge_bot.py   # Telegram interface
├── claude_runner.py # Task processor
├── notifier.py     # Notification system
└── .env           # Configuration
```

## 🔄 Workflow

### Task Processing Pipeline

1. **Send task from phone**: `/task Add particle effects to explosions`

2. **Bridge Bot** creates task card in `inbox/`:
```json
{
  "id": "task-abc123",
  "text": "Add particle effects to explosions",
  "status": "queued"
}
```

3. **Claude Runner** picks up task:
   - Creates feature branch
   - Asks Claude for unified diff
   - Applies patch
   - Commits changes
   - Runs build/tests
   - Notifies phone with results

4. **You** review in Cursor IDE and merge if good

### Direct Desktop Messaging

1. **Send from phone**: `/to claude Write a singleton pattern for GameManager`
2. **Bot uses AutoHotkey** to:
   - Focus or launch target app
   - Paste message into chat
   - Send automatically
3. **Continue conversation** on desktop when you return

## 🛡️ Safety Features

- Only accepts unified diff patches (no direct file access)
- Creates feature branches (never touches main)
- Automatic rollback on patch failure
- Build/test validation before notification
- Temperature 0 for consistent outputs

## 🔍 Monitoring

Check logs:
```bash
# View runner logs
tail -f logs/claude_runner.log

# View bot logs  
tail -f logs/bridge_bot.log

# Check task status
ls tasks/inbox/
ls tasks/processing/
ls tasks/done/
```

## 🎯 Best Practices

### Good Task Directives

✅ **Specific and bounded:**
```
/task Add health bar UI component above player, show current/max HP, use green-yellow-red gradient
```

✅ **Include constraints:**
```
/task Implement dash ability: double-tap direction, 5 unit distance, 0.5s cooldown, add visual trail
```

✅ **Mention test requirements:**
```
/task Create inventory system with 20 slots, stack limit 99, add unit tests for add/remove/stack operations
```

### Poor Task Directives

❌ **Too vague:**
```
/task Make game better
```

❌ **Too large:**
```
/task Rewrite entire engine
```

❌ **Missing context:**
```
/task Fix the bug
```

## 🔌 Integration with Cursor

1. Open your repo in Cursor
2. Keep terminal open with build watch:
```powershell
while ($true) {
    cmake --build build
    Start-Sleep -Seconds 5
}
```

3. When runner commits, Cursor auto-refreshes
4. Review changes in Git panel
5. Test locally and merge if satisfied

## 🚁 Advanced Usage

### Custom System Prompts

Edit `SYSTEM_PROMPT` in `claude_runner.py` for your tech stack:

```python
SYSTEM_PROMPT = """You are a Unity C# developer.
Generate patches for Unity 2022.3 LTS.
Use new Input System, not legacy.
Follow SOLID principles.
..."""
```

### Voice Input (Future)

The system is prepared for voice input. To add:

1. Install `openai-whisper`
2. Modify `bridge_bot.py` to transcribe voice messages
3. Convert transcription to `/task` commands

### Multiple Repositories

Create different `.env` files:
```bash
python claude_runner.py --env .env.gameproject
python claude_runner.py --env .env.webproject
```

## 🎯 AutoHotkey Integration

### Setup for Desktop Messaging

1. Install AutoHotkey v2 from https://www.autohotkey.com/
2. For Cursor: Set keyboard shortcut for "Focus Chat" to `Ctrl+Alt+;`
3. Test with: `/to cursor Show git status`

See [AUTOHOTKEY_SETUP.md](AUTOHOTKEY_SETUP.md) for detailed configuration.

## 🐛 Troubleshooting

**Bot not responding:**
- Check bot token in `.env`
- Verify bot is not blocked
- Check `logs/bridge_bot.log`

**Patches failing:**
- Ensure repo is clean: `git status`
- Check Claude API key is valid
- Review `logs/claude_runner.log`

**Build errors:**
- Verify `BUILD_CMD` in `.env`
- Check repo builds manually first
- Ensure all dependencies installed

## 📈 Metrics

The system logs all operations. To generate reports:

```python
# Quick stats
python -c "
import json
from pathlib import Path

done = list(Path('tasks/done').glob('*_result.json'))
results = [json.loads(f.read_text()) for f in done]

success = sum(1 for r in results if r['status'] == 'success')
print(f'Success rate: {success}/{len(results)} ({success/len(results)*100:.1f}%)')
"
```

## 🎉 Tips for Walking & Coding

1. **Use voice dictation** on phone for longer tasks
2. **Batch similar tasks** to maintain context
3. **Add notes** immediately after task for clarifications
4. **Review on desktop** before starting next walk
5. **Keep tasks small** - one feature per walk

## 📝 License

MIT - Use freely for your projects!

## 🤝 Contributing

Feel free to enhance:
- Add web dashboard
- Integrate more LLMs
- Add code review step
- Create VS Code extension
- Add metrics dashboard

---

**Happy Walking & Coding! 🚶‍♂️💻**
