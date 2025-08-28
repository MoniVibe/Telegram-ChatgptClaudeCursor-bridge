#Requires AutoHotkey v2.0
; Allow partial title matches like "ChatGPT - Microsoft Edge"
SetTitleMatchMode 2
; Use screen coords for stable clicking
CoordMode "Mouse", "Screen"
; Preferred Claude model to select (unused in new flow, kept for future)
desiredClaudeModel := "Opus"
; Send text to ChatGPT, Claude, or Cursor via clipboard
; Usage:
;  - AutoHotkey64.exe send_to.ahk <target> <msgfile>
;  - AutoHotkey64.exe send_to.ahk <target> FILE <filepath>
;  - AutoHotkey64.exe send_to.ahk <target> STOP
; targets: chatgpt | claude | claude_direct | cursor | cursor_direct

if A_Args.Length < 2 {
    MsgBox "Usage: send_to.ahk <target> <msgfile|FILE <path>|STOP>"
    ExitApp 1
}

target  := A_Args[1]
mode    := "SEND"
msgfile := ""
imgpath := ""
if (A_Args.Length >= 2 && A_Args[2] = "STOP") {
    mode := "STOP"
} else if (A_Args.Length >= 3 && A_Args[2] = "FILE") {
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

; Handle STOP globally to avoid any accidental paste/flows
if (mode = "STOP") {
    if (target = "cursor" or target = "cursor_direct") {
        ; Focus Cursor and send stop hotkey
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
        Sleep 120
        ; Ensure chat input is focused before sending stop
        Send "^!;"
        Sleep 140
        Send "^+{Backspace}"
    } else if (target = "claude" or target = "claude_direct") {
        claude1 := EnvGet("LOCALAPPDATA") . "\\Programs\\Claude\\Claude.exe"
        claude2 := EnvGet("ProgramFiles") . "\\Claude\\Claude.exe"
        claudeExe := ""
        if FileExist(claude1)
            claudeExe := claude1
        else if FileExist(claude2)
            claudeExe := claude2
        if (claudeExe != "")
            FocusOrLaunch("ahk_exe Claude.exe", claudeExe, "")
        else
            FocusOrLaunch("Claude", "", "msedge.exe https://claude.ai/new")
        EnsureActive("ahk_exe Claude.exe")
        Send "{Esc}"
    }
    ExitApp
}

; Send to appropriate target
switch target {
case "chatgpt":
    ; Launch ChatGPT in Chrome instead of Edge
    chromePath := EnvGet("LOCALAPPDATA") . "\\Google\\Chrome\\Application\\chrome.exe"
    urlCmd := '"' . chromePath . '" https://chat.openai.com/'
    FocusOrLaunch("ChatGPT", "", urlCmd)
    EnsureActive("ChatGPT")
    if (mode = "STOP") {
        ; No-op for now
    } else {
        ; Press Ctrl+Shift+O before input as requested
        Send "^+o"
        Sleep 220
        PasteAndSend("ChatGPT", false)
    }
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
        FocusOrLaunch("ahk_exe Claude.exe", claudeExe, "")
    else
        FocusOrLaunch("Claude", "", "msedge.exe https://claude.ai/new")
    EnsureActive("ahk_exe Claude.exe")
    if (mode = "STOP") {
        ; ESC to stop/close suggestions
        Send "{Esc}"
        Sleep 150
    } else {
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
    }
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
        FocusOrLaunch("ahk_exe Claude.exe", claudeExe, "")
    else
        FocusOrLaunch("Claude", "", "msedge.exe https://claude.ai/new")
    EnsureActive("ahk_exe Claude.exe")
    ; Nudge focus into the input by sending a Space before paste
    Send "{Space}"
    Sleep 120
    ; Clear any residual text
    Send "^a"
    Sleep 100
    Send "{Del}"
    Sleep 120
    PasteAndSend("ahk_exe Claude.exe", false)
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
    if (mode = "STOP") {
        ; Focus cursor agent then send Ctrl+Shift+Backspace
        Send "^i"
        Sleep 160
        Send "^+{Backspace}"
    } else {
        ; Open a new agent chat (Ctrl+Shift+I)
        Send "^+i"
        ; Give Cursor time to create the chat pane
        Sleep 700
        ; Ensure the chat input is focused, then paste and send
        Send "^!;"
        Sleep 160
        Send "^v{Enter}"
    }
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
    if (mode = "STOP") {
        Send "^!;"
        Sleep 160
        Send "^+{Backspace}"
    } else {
        ; Focus agent chat (Ctrl+Alt+;) to ensure input is active
        Send "^!;"
        Sleep 140
        ; Clear any residual text
        Send "^a"
        Sleep 100
        Send "{Del}"
        Sleep 120
        Send "^v{Enter}"
    }
    ExitApp
    
case "cursor_move":
    ; Focus Cursor and open folder dialog, then navigate to requested path
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
    EnsureActive("Cursor")

    ; Open "Open Folder" in Cursor (expects Ctrl+M bound)
    Send "^m"
    Sleep 320
    ; Focus the address/path field and clear it
    Send "!d"
    Sleep 160
    Send "^a"
    Sleep 120

    ; Build destination path from base + user-provided relative segment (simple join)
    base := "C:\Users\Moni\Documents\claudeprojects"
    ; Ensure base has no trailing backslash
    while (SubStr(base, StrLen(base)) = "\\")
        base := SubStr(base, 1, StrLen(base) - 1)

    rel := text   ; text is loaded from msg file in SEND mode
    ; Trim whitespace
    rel := Trim(rel, "`r`n `t")
    ; Remove literal prefix "cursor " if present (case-insensitive)
    if (StrLen(rel) >= 7 && StrLower(SubStr(rel, 1, 6)) = "cursor" && SubStr(rel, 7, 1) = " ")
        rel := Trim(SubStr(rel, 8), " `t")
    ; Normalize forward slashes to backslashes
    rel := StrReplace(rel, "/", "\\")
    ; Remove ALL leading backslashes from rel
    while (SubStr(rel, 1, 1) = "\\")
        rel := SubStr(rel, 2)

    if (rel = "")
        dest := base
    else
        dest := base . "\\" . rel

    ; Paste destination path and confirm in one go
    A_Clipboard := dest
    Sleep 120
    Send "^v"
    Sleep 160
    Send "{Enter}"
    Sleep 140
    Send "{Enter}"
    ExitApp
    
case "cursor_custom":
    ; Focus Cursor and send arbitrary key chords from input text
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
    EnsureActive("Cursor")
    keysText := Trim(text, "`r`n `t")
    if (keysText != "")
        DoSendKeys(keysText)
    ExitApp

case "claude_custom":
    ; Focus Claude and send arbitrary key chords from input text
    claude1 := EnvGet("LOCALAPPDATA") . "\\Programs\\Claude\\Claude.exe"
    claude2 := EnvGet("ProgramFiles") . "\\Claude\\Claude.exe"
    claudeExe := ""
    if FileExist(claude1)
        claudeExe := claude1
    else if FileExist(claude2)
        claudeExe := claude2
    if (claudeExe != "")
        FocusOrLaunch("ahk_exe Claude.exe", claudeExe, "")
    else
        FocusOrLaunch("Claude", "", "msedge.exe https://claude.ai/new")
    EnsureActive("ahk_exe Claude.exe")
    keysText := Trim(text, "`r`n `t")
    if (keysText != "")
        DoSendKeys(keysText)
    ExitApp

case "custom":
    ; Send keys globally without focusing or launching any application
    keysText := Trim(text, "`r`n `t")
    if (keysText != "")
        DoSendKeys(keysText)
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

; Parse and send user-friendly key chord strings, e.g.:
;   ctrl+j
;   ctrl+shift+p
;   alt+f, o
;   text:"hello world" then ctrl+enter
DoSendKeys(keysText) {
    ; Split sequences by commas for sequential actions
    parts := StrSplit(keysText, ",")
    for idx, part in parts {
        seq := Trim(part)
        if (seq = "") {
            continue
        }

        ; Support literal text: prefix text:"..."
        if (SubStr(StrLower(seq), 1, 5) = "text:") {
            msg := Trim(SubStr(seq, 6), " `t`r`n")
            if (msg != "") {
                Send msg
            }
            continue
        }

        ; Map common modifiers to AHK syntax
        lower := StrLower(seq)
        lower := StrReplace(lower, "ctrl+", "^")
        lower := StrReplace(lower, "control+", "^")
        lower := StrReplace(lower, "shift+", "+")
        lower := StrReplace(lower, "alt+", "!")
        ; Accept synonyms for Windows key
        lower := StrReplace(lower, "win+", "#")
        lower := StrReplace(lower, "windows+", "#")
        lower := StrReplace(lower, "winkey+", "#")

        ; Normalize special names
        ; Examples: enter, tab, esc, space, up, down, left, right, home, end
        ; Handle common case: modifiers + word key (e.g., #down, ^enter)
        if RegExMatch(lower, "i)^([\^\+!#]+)([a-z]+)$", &m) {
            mods := m[1]
            key  := m[2]
            Send mods "{" key "}"
        } else if RegExMatch(lower, "i)^(\^|\+|!|#)*[a-z0-9]$") {
            ; single char with modifiers (e.g., ^j)
            Send lower
        } else {
            ; Convert words to {word} style if not already with {}
            if (InStr(lower, "{") = 0) {
                tokens := StrSplit(lower, "+", "`t `r`n")
                out := ""
                for i, t in tokens {
                    if (t = "^" or t = "+" or t = "!" or t = "#") {
                        out .= t
                    } else if (StrLen(t) = 1) {
                        out .= t
                    } else {
                        out .= "{" . t . "}"
                    }
                }
                lower := out
            }
            Send lower
        }
        Sleep 120
    }
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

