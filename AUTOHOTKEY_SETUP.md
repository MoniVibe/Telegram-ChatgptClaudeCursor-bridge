# AutoHotkey Desktop Integration Setup

## Prerequisites

1. **Install AutoHotkey v2** (Required)
   - Download from: https://www.autohotkey.com/download/ahk-v2.exe
   - Install to default location: `C:\Program Files\AutoHotkey\v2\`
   - If installed elsewhere, update `AHK_EXE` in `bridge_bot.py`

2. **Configure Cursor IDE** (For Cursor integration)
   - Open Cursor → File → Preferences → Keyboard Shortcuts
   - Search for "Focus Chat" or "Toggle AI Chat"
   - Set keybinding to: `Ctrl+Alt+;`
   - This allows the script to focus the chat input

## Usage

Send messages from your phone to desktop apps:

### ChatGPT
```
/to chatgpt Explain the concept of dependency injection with examples
```

### Claude
```
/to claude Write unit tests for the OrderQueue class with edge cases
```

### Cursor
```
/to cursor Run cmake build and show me any errors
```

## How It Works

1. Your phone sends `/to <target> <message>` to Telegram bot
2. Bot creates temp file with message content
3. AutoHotkey script:
   - Reads the message file
   - Copies to clipboard
   - Focuses or launches target app
   - Pastes and sends the message
4. Bot confirms delivery

## Customization

### Window Titles
If your browser/app titles differ, edit `send_to.ahk`:

```autohotkey
; Change these to match your window titles
case "chatgpt":
    FocusOrLaunch("ChatGPT", "", "chrome.exe https://chat.openai.com/")
    
case "claude":
    FocusOrLaunch("Claude - Chrome", "", "chrome.exe https://claude.ai/new")
```

### Browser Choice
Default uses Edge. To use Chrome:

```autohotkey
; Replace msedge.exe with chrome.exe
"chrome.exe https://chat.openai.com/"
```

### Cursor Path
If Cursor installed elsewhere:

```autohotkey
cursorExe := "D:\Tools\Cursor\Cursor.exe"  ; Your custom path
```

## Troubleshooting

### "AutoHotkey not found"
- Install AutoHotkey v2 from link above
- Or update path in `bridge_bot.py`:
  ```python
  AHK_EXE = r"D:\MyTools\AutoHotkey\AutoHotkey64.exe"
  ```

### "Window not found"
- Make sure the app is running
- Check window title matches (use Window Spy tool)
- Try alt-tabbing to the app first

### Cursor not receiving text
- Verify keyboard shortcut is set in Cursor
- Try different shortcut like `Ctrl+Shift+P`
- Update the shortcut in `send_to.ahk`

### Text not pasting
- Check clipboard isn't blocked by security software
- Try increasing Sleep delays in script:
  ```autohotkey
  Sleep 200  ; Increase from 120
  ```

## Security Notes

- Messages are sent via clipboard (visible to clipboard managers)
- Temp files are created and deleted immediately
- No sensitive data should be sent this way
- AutoHotkey scripts run with user privileges

## Advanced Features

### Add New Targets

Edit `send_to.ahk` to add more apps:

```autohotkey
case "slack":
    FocusOrLaunch("Slack", "", "slack.exe")
    PasteAndSend("Slack")
    
case "discord":
    FocusOrLaunch("Discord", "", "%LOCALAPPDATA%\Discord\app-1.0.9030\Discord.exe")
    Send "^v{Enter}"
```

Then use: `/to slack Check the deployment status`

### Multi-Monitor Support

The script clicks at 90% height of window, which works on any monitor.
Adjust if needed:

```autohotkey
clickY := y + (h * 0.85)  ; Click higher up
```

## Testing

Test each integration:

```bash
# From command line (after bot is running)
python -c "from bridge_bot import send_to_desktop; print(send_to_desktop('chatgpt', 'Test message'))"
```

Or from Telegram:
```
/to chatgpt Hello from my phone!
/to claude Generate a README template
/to cursor Show current git status
```
