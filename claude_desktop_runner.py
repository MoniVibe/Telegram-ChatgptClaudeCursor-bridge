"""
Claude Desktop Runner - No API

Processes /task by automating the Claude Desktop app with AutoHotkey.
Sends meta-prompt, polls window for a unified diff, applies patch, and notifies via Telegram.
"""

import os
import time
import json
import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple
import subprocess

from dotenv import load_dotenv
try:
    from notifier import notify, notify_chunked
except Exception:
    from notifier import notify
    def notify_chunked(text: str, parse_mode: str = "Markdown") -> bool:
        if not text:
            return False
        max_len = 3500
        sent_any = False
        remaining = text
        while remaining:
            chunk = remaining[:max_len]
            remaining = remaining[max_len:]
            sent_any = notify(chunk, parse_mode=parse_mode) or sent_any
        return sent_any

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/claude_desktop_runner.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
INBOX = Path('tasks/inbox')
PROCESSING = Path('tasks/processing')
DONE = Path('tasks/done')
for p in (INBOX, PROCESSING, DONE, Path('logs')):
    p.mkdir(parents=True, exist_ok=True)

REPO = Path(os.getenv('REPO_PATH', '.')).resolve()
DEFAULT_BRANCH = os.getenv('DEFAULT_BRANCH', 'main')
BUILD_CMD = os.getenv('BUILD_CMD')
TEST_CMD = os.getenv('TEST_CMD')

AHK_EXE = r"C:\\Program Files\\AutoHotkey\\v2\\AutoHotkey64.exe"
SEND_AHK = str(BASE / 'send_to.ahk')

POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_SEC', '5'))
PULL_INTERVAL = 4
PULL_TIMEOUT = 300

META_PROMPT = (
    "Return ONLY a git-apply unified diff. No commentary. Start with 'diff --git' or '---'.\n"
    "Implement this directive precisely:\n"
)

def git(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO, shell=True, capture_output=True, text=True)

def git_create_branch(prefix: str = 'desk') -> str:
    name = f"{prefix}/" + str(int(time.time()))
    git('git reset --hard')
    git('git clean -fd')
    git(f'git checkout {DEFAULT_BRANCH}')
    git('git pull')
    git(f'git checkout -b {name}')
    return name

def git_apply_patch(patch: str) -> Tuple[bool, str]:
    path = REPO / '_claude.patch'
    path.write_text(patch, encoding='utf-8')
    try:
        r = git(f'git apply --index "{path}"')
        if r.returncode != 0:
            r = git(f'git apply --index --whitespace=fix "{path}"')
        if r.returncode == 0:
            git('git add -A')
            return True, 'ok'
        return False, r.stderr
    finally:
        if path.exists():
            path.unlink()

def ahk_send_claude(text: str) -> bool:
    tmp = BASE / '_tmp_send.txt'
    tmp.write_text(text, encoding='utf-8')
    r = subprocess.run([AHK_EXE, SEND_AHK, 'claude', str(tmp)], capture_output=True, text=True)
    ok = r.returncode == 0
    try:
        tmp.unlink()
    except Exception:
        pass
    if not ok:
        log.error(f'AHK send failed: {r.stderr[:200] if r.stderr else ""}')
    return ok

def ahk_pull_claude() -> str:
    r = subprocess.run([AHK_EXE, SEND_AHK, 'claude', 'PULL'], capture_output=True, text=True)
    if r.returncode != 0:
        log.error(f'AHK pull failed: {r.stderr[:200] if r.stderr else ""}')
        return ''
    return (r.stdout or '').strip()

def extract_patch(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.strip()
    if t.startswith('diff --git') or t.startswith('--- '):
        return t
    i = max(t.rfind('\ndiff --git '), t.rfind('\n--- '))
    if i == -1:
        return None
    return t[i+1:]

def process_task(task_path: Path):
    card = json.loads(task_path.read_text(encoding='utf-8'))
    task_id = card['id']
    directive = card['text']
    log.info(f'Processing {task_id}: {directive[:80]}...')
    notify(f'⚙️ Processing {task_id}: {directive[:80]}...')

    # 1) Send prompt to Claude Desktop
    prompt = META_PROMPT + directive
    if not ahk_send_claude(prompt):
        raise RuntimeError('Failed to send to Claude Desktop')

    # 2) Poll for patch
    start = time.time()
    patch = None
    while time.time() - start < PULL_TIMEOUT:
        time.sleep(PULL_INTERVAL)
        content = ahk_pull_claude()
        patch = extract_patch(content)
        if patch:
            break
    if not patch:
        raise TimeoutError('Timed out waiting for Claude patch')

    notify_chunked(f"```\n{patch[:3500]}\n```")

    # 3) Apply patch
    branch = git_create_branch()
    ok, msg = git_apply_patch(patch)
    if not ok:
        raise RuntimeError(f'Patch apply failed: {msg[:200]}')
    git(f'git commit -m "desk: {task_id} - {directive[:60]}"')

    # 4) Optional build/tests
    if BUILD_CMD:
        r = git(BUILD_CMD)
        notify_chunked("🔨 Build\n" + f"Return: {r.returncode}\n\n" + ("```\n" + (r.stdout or '')[:1000] + "\n```"))
    if TEST_CMD:
        r = git(TEST_CMD)
        notify_chunked("🧪 Tests\n" + f"Return: {r.returncode}\n\n" + ("```\n" + (r.stdout or '')[:1000] + "\n```"))

    notify(f"✅ {task_id} completed on `{branch}`")

def main_loop():
    log.info('Claude Desktop Runner started')
    notify('🚀 Claude Desktop Runner started (no API)')
    while True:
        try:
            files = sorted(INBOX.glob('*.json'))
            for f in files:
                p = PROCESSING / f.name
                shutil.move(str(f), str(p))
                try:
                    process_task(p)
                except Exception as e:
                    log.error(f'Task {f.name} failed: {e}')
                    notify(f'❌ Task {f.stem} failed: {str(e)[:200]}')
                finally:
                    shutil.move(str(p), str(DONE / f.name))
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            notify('🛑 Desktop Runner stopped')
            break
        except Exception as e:
            log.error(f'Loop error: {e}')
            time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main_loop()


