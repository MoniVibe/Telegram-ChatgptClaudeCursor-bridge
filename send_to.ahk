#Requires AutoHotkey v2.0
; Allow partial title matches like "ChatGPT - Microsoft Edge"
SetTitleMatchMode 2
; Use screen coords for stable clicking
CoordMode "Mouse", "Screen"
; Preferred Claude model to select (unused in new flow, kept for future)
desiredClaudeModel := "Opus"
; Send text to ChatGPT, Claude, or Cursor via clipboard
; Usage: AutoHotkey64.exe send_to.ahk <target> <msgfile>
; Or:    AutoHotkey64.exe send_to.ahk <target> FILE <filepath>
; targets: chatgpt | claude | claude_direct | cursor | cursor_direct

if A_Args.Length < 2 {
    MsgBox "Usage: send_to.ahk <target> <msgfile|FILE <path>>"
    ExitApp 1
}

target  := A_Args[1]
mode    := "SEND"
msgfile := ""
imgpath := ""
if (A_Args.Length >= 3 && A_Args[2] = "FILE") {
    mode := "FILE"
    imgpath := A_Args[3]
} else {
    msgfile := A_Args[2]
}

if (mode = "SEND") {
    ; Read the message file
    try {
        text := FileRead(msgfile, "UTF-8")
    } catch Error as err {
        MsgBox "Failed to read file: " . msgfile . "`nError: " . err.Message
        ExitApp 1
    }
    ; Copy to clipboard
    A_Clipboard := text
    Sleep 80
}

; Send to appropriate target
switch target {
case "chatgpt":
    ; Launch ChatGPT in Chrome instead of Edge
    chromePath := EnvGet("LOCALAPPDATA") . "\\Google\\Chrome\\Application\\chrome.exe"
    urlCmd := '"' . chromePath . '" https://chat.openai.com/'
    FocusOrLaunch("ChatGPT", "", urlCmd)
    EnsureActive("ChatGPT")
    ; Press Ctrl+Shift+O before input as requested
    Send "^+o"
    Sleep 220
    PasteAndSend("ChatGPT", false)  ; skip clicks; rely on keyboard focus
    ExitApp
    
case "claude":
    ; Prefer Claude Desktop app if installed; fallback to web
    claude1 := EnvGet("LOCALAPPDATA") . "\\Programs\\Claude\\Claude.exe"
    claude2 := EnvGet("ProgramFiles") . "\\Claude\\Claude.exe"
    claudeExe := ""
    if FileExist(claude1)
        claudeExe := claude1
    else if FileExist(claude2)
        claudeExe := claude2

    if (claudeExe != "")
        FocusOrLaunch("Claude", claudeExe, "")
    else
        FocusOrLaunch("Claude", "", "msedge.exe https://claude.ai/new")
    EnsureActive("Claude")
    ; 1) Bring up Claude quick input anywhere
    Send "^!{Space}"
    Sleep 220
    ; 2) Dummy input to normalize focus
    Send "hello"
    Sleep 120
    Send "{Enter}"
    Sleep 3500
    ; 3) Directly paste user's prompt (already on clipboard)
    Send "^v"
    Sleep 200
    ; 4) Move to send-with-Opus and trigger send
    Send "{Tab 4}"
    Sleep 160
    Send "{Space}"
    Sleep 140
    Send "{Space}"
    Sleep 200
    ExitApp

case "claude_direct":
    ; Direct send to Claude without quick-input or model switching.
    ; Just focus Claude and paste/enter.
    ; Prefer Desktop app, fallback to web.
    claude1 := EnvGet("LOCALAPPDATA") . "\\Programs\\Claude\\Claude.exe"
    claude2 := EnvGet("ProgramFiles") . "\\Claude\\Claude.exe"
    claudeExe := ""
    if FileExist(claude1)
        claudeExe := claude1
    else if FileExist(claude2)
        claudeExe := claude2

    if (claudeExe != "")
        FocusOrLaunch("Claude", claudeExe, "")
    else
        FocusOrLaunch("Claude", "", "msedge.exe https://claude.ai/new")
    EnsureActive("Claude")
    PasteAndSend("Claude", false)
    ExitApp
    
case "cursor":
    ; Resolve Cursor.exe path robustly (AHK v2: use EnvGet/A_LocalAppData)
    tryPath1 := EnvGet("LOCALAPPDATA") . "\Programs\cursor\Cursor.exe"
    tryPath2 := EnvGet("ProgramFiles") . "\Cursor\Cursor.exe"
    tryPath3 := EnvGet("ProgramFiles(x86)") . "\Cursor\Cursor.exe"
    cursorExe := ""
    if FileExist(tryPath1)
        cursorExe := tryPath1
    else if FileExist(tryPath2)
        cursorExe := tryPath2
    else if FileExist(tryPath3)
        cursorExe := tryPath3
    else
        cursorExe := "Cursor.exe"  ; fallback to PATH lookup

    FocusOrLaunch("Cursor", cursorExe, "")
    ; Open a new agent chat (Ctrl+Shift+I)
    Send "^+i"
    ; Give Cursor time to create the chat pane
    Sleep 700
    ; Ensure the chat input is focused, then paste and send
    Send "^!;"
    Sleep 160
    Send "^v{Enter}"
    ExitApp

case "cursor_direct":
    ; Previous behavior: focus chat and paste
    tryPath1 := EnvGet("LOCALAPPDATA") . "\Programs\cursor\Cursor.exe"
    tryPath2 := EnvGet("ProgramFiles") . "\Cursor\Cursor.exe"
    tryPath3 := EnvGet("ProgramFiles(x86)") . "\Cursor\Cursor.exe"
    cursorExe := ""
    if FileExist(tryPath1)
        cursorExe := tryPath1
    else if FileExist(tryPath2)
        cursorExe := tryPath2
    else if FileExist(tryPath3)
        cursorExe := tryPath3
    else
        cursorExe := "Cursor.exe"

    FocusOrLaunch("Cursor", cursorExe, "")
    ; Focus chat input with custom keybinding (Ctrl+Alt+;)
    Send "^!;"
    Sleep 140
    Send "^v{Enter}"
    ExitApp
    
default:
    MsgBox "Unknown target: " . target
    ExitApp 1
}

ExitApp

; Function to focus existing window or launch application
FocusOrLaunch(title, exePath := "", url := "") {
    ; Try to find and activate existing window
    if WinExist(title) {
        WinActivate title
        WinWaitActive title, , 3
        return
    }
    
    ; Launch executable if path provided
    if exePath && FileExist(exePath) {
        Run exePath
        WinWait title, , 12
        if WinExist(title) {
            WinActivate title
            WinWaitActive title, , 3
        }
        return
    }
    
    ; Open URL if provided
    if url {
        Run url
        WinWait title, , 15
        if WinExist(title) {
            WinActivate title
            WinWaitActive title, , 3
        }
    }
}

EnsureActive(title, retries := 10, delayMs := 120) {
    loop retries {
        WinActivate title
        WinWaitActive title, , 2
        if WinActive(title)
            return true
        Sleep delayMs
    }
    return false
}

; Function to paste and send in chat applications
PasteAndSend(title, doClick := true) {
    ; Briefly block input to avoid focus stealing
    BlockInput "On"
    ; Ensure target window is active and stays on top briefly
    WinActivate title
    WinWaitActive title, , 3
    WinSetAlwaysOnTop 1, title
    Sleep 150
    
    ; Get window position
    try {
        WinGetPos &x, &y, &w, &h, title
    } catch {
        WinGetPos &x, &y, &w, &h
    }
    
    ; Optionally attempt candidate click points to focus the composer
    if doClick {
        ClickComposer(title, x, y, w, h)
        Sleep 160
    }
    
    ; Paste text and send
    SendInput "^v"
    Sleep 160
    Send "{Enter}"
    Sleep 240
    
    ; Release always-on-top and input block
    WinSetAlwaysOnTop 0, title
    BlockInput "Off"
}

SelectClaudeModel(title, modelName) {
    ; Heuristic navigation to model dropdown and selection
    EnsureActive(title)
    Sleep 150
    ; Move focus away/back to stabilize
    Send "{Shift down}{Tab}{Shift up}{Tab}"
    Sleep 120
    ; From composer, try 4 Tabs to reach model selector
    Send "{Tab 4}"
    Sleep 160
    ; Open dropdown
    Send "{Space}"
    Sleep 160
    ; Some builds require a second space
    Send "{Space}"
    Sleep 220
    ; Type filter and confirm
    if (modelName) {
        Send modelName
        Sleep 240
        Send "{Enter}"
        Sleep 180
    }
}

ClickComposer(title, x, y, w, h) {
    ; Candidate sets
    bottom := []
    bottom.Push([x + (w * 0.50), y + (h * 0.90)])
    bottom.Push([x + (w * 0.50), y + (h * 0.87)])
    bottom.Push([x + (w * 0.45), y + (h * 0.89)])
    bottom.Push([x + (w * 0.55), y + (h * 0.89)])
    bottom.Push([x + (w * 0.50), y + (h * 0.92)])

    ; Claude project view: input sits much higher (~22-34% height)
    grid := []
    ys := [0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34]
    xs := [0.40, 0.50, 0.60]
    for yi in ys {
        for xi in xs {
            grid.Push([x + (w * xi), y + (h * yi)])
        }
    }

    order := []
    if InStr(title, "Claude") {
        for p in grid
            order.Push(p)
        for p in bottom
            order.Push(p)
    } else {
        for p in bottom
            order.Push(p)
    }

    for p in order {
        MouseMove p[1], p[2]
        Sleep 60
        Click p[1], p[2]
        Sleep 90
        Click p[1], p[2]  ; double-click
        Sleep 120
        if !WinActive(title) {
            WinActivate title
            WinWaitActive title, , 2
        }
    }
}

