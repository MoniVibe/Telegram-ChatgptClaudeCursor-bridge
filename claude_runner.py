"""
Claude Runner - Polls tasks, generates diffs, applies patches, runs tests
Core orchestration engine for the LLM workflow
"""

import os
import time
import json
import subprocess
import shutil
import uuid
import traceback
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from dotenv import load_dotenv
from anthropic import Anthropic
from notifier import notify, log_event

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/claude_runner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
REPO = Path(os.getenv("REPO_PATH", "."))
INBOX = Path("tasks/inbox")
PROCESSING = Path("tasks/processing")
DONE = Path("tasks/done")
LOGS = Path("logs")

# Create directories
for p in (INBOX, PROCESSING, DONE, LOGS):
    p.mkdir(parents=True, exist_ok=True)

# Initialize Anthropic client
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_KEY:
    logger.error("ANTHROPIC_API_KEY not set in .env")
    raise ValueError("ANTHROPIC_API_KEY required")

ANTH = Anthropic(api_key=ANTHROPIC_KEY)

# Git and build configuration
DEFAULT_BRANCH = os.getenv("DEFAULT_BRANCH", "main")
BUILD_CMD = os.getenv("BUILD_CMD")
TEST_CMD = os.getenv("TEST_CMD")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", "5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Claude system prompt - focused on generating clean diffs
SYSTEM_PROMPT = """You are a senior software engineer generating unified diff patches.

CRITICAL RULES:
1. Return ONLY a unified diff patch (git apply compatible)
2. NO explanations, NO code fences, NO markdown
3. Start with 'diff --git' or '--- ' immediately
4. Include proper file headers for new files
5. Keep changes minimal and focused
6. Ensure patches are syntactically correct

For new files, use format:
diff --git a/path/to/file b/path/to/file
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/path/to/file
@@ -0,0 +1,N @@
+content here

For modifications:
diff --git a/path/to/file b/path/to/file
index abc123..def456 100644
--- a/path/to/file
+++ b/path/to/file
@@ -L,N +L,M @@
 context
-removed lines
+added lines
 context
"""

class GitRepo:
    """Git repository operations"""
    
    def __init__(self, repo_path: Path):
        self.repo = repo_path
        
    def run(self, cmd: str) -> subprocess.CompletedProcess:
        """Run a command in the repo directory"""
        return subprocess.run(
            cmd,
            cwd=self.repo,
            shell=True,
            capture_output=True,
            text=True
        )
    
    def get_current_branch(self) -> str:
        """Get current branch name"""
        result = self.run("git rev-parse --abbrev-ref HEAD")
        return result.stdout.strip() if result.returncode == 0 else DEFAULT_BRANCH
    
    def ensure_clean(self) -> bool:
        """Ensure working tree is clean"""
        self.run("git reset --hard")
        self.run("git clean -fd")
        return True
    
    def checkout_branch(self, branch: str) -> bool:
        """Checkout a branch"""
        result = self.run(f"git checkout {branch}")
        return result.returncode == 0
    
    def create_branch(self, prefix: str = "auto") -> str:
        """Create a new branch from default"""
        branch_name = f"{prefix}/{uuid.uuid4().hex[:8]}"
        
        self.ensure_clean()
        self.checkout_branch(DEFAULT_BRANCH)
        self.run("git pull")
        self.run(f"git checkout -b {branch_name}")
        
        logger.info(f"Created branch: {branch_name}")
        return branch_name
    
    def apply_patch(self, patch_text: str) -> Tuple[bool, str]:
        """Apply a patch to the repository"""
        patch_file = self.repo / "_auto_generated.patch"
        
        try:
            # Write patch to file
            patch_file.write_text(patch_text, encoding="utf-8")
            
            # Try to apply the patch
            result = self.run(f'git apply --index "{patch_file}"')
            
            if result.returncode != 0:
                # Try with different whitespace handling
                result = self.run(f'git apply --index --whitespace=fix "{patch_file}"')
                
            if result.returncode == 0:
                self.run("git add -A")
                return True, "Patch applied successfully"
            else:
                return False, f"Patch failed: {result.stderr}"
                
        finally:
            # Clean up patch file
            if patch_file.exists():
                patch_file.unlink()
    
    def commit(self, message: str) -> bool:
        """Commit changes"""
        result = self.run(f'git commit -m "{message}"')
        return result.returncode == 0
    
    def get_diff_summary(self) -> str:
        """Get summary of changes"""
        result = self.run("git diff --stat HEAD~1")
        return result.stdout if result.returncode == 0 else ""

class ClaudeInterface:
    """Interface to Claude API"""
    
    def __init__(self, client: Anthropic):
        self.client = client
        
    def generate_patch(self, task_text: str, context: Dict[str, Any]) -> str:
        """Generate a diff patch for the given task"""
        
        # Build prompt with context
        prompt = self._build_prompt(task_text, context)
        
        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            
            if message.content:
                return message.content[0].text
            return ""
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return ""
    
    def _build_prompt(self, task_text: str, context: Dict[str, Any]) -> str:
        """Build the prompt with task and context"""
        prompt_parts = [
            f"Repository: {context.get('repo_path', 'unknown')}",
            f"Current branch: {context.get('branch', DEFAULT_BRANCH)}",
            f"",
            f"Task directive:",
            f"{task_text}",
            f"",
            f"Generate a unified diff patch that implements this task.",
            f"Output ONLY the patch, starting with 'diff --git' or '---'."
        ]
        
        return "\n".join(prompt_parts)

class TaskProcessor:
    """Process task cards through the pipeline"""
    
    def __init__(self):
        self.git = GitRepo(REPO)
        self.claude = ClaudeInterface(ANTH)
        
    def process_card(self, card_path: Path) -> Dict[str, Any]:
        """Process a single task card"""
        
        # Load task card
        card = json.loads(card_path.read_text(encoding="utf-8"))
        task_id = card["id"]
        task_text = card["text"]
        
        logger.info(f"Processing {task_id}: {task_text[:50]}...")
        
        # Skip notes
        if card["kind"] == "note":
            return {
                "status": "skipped",
                "reason": "Note card - no action needed"
            }
        
        try:
            # Create feature branch
            branch = self.git.create_branch()
            
            # Generate patch with Claude
            context = {
                "repo_path": str(REPO),
                "branch": branch,
            }
            
            patch = self.claude.generate_patch(task_text, context)
            
            if not patch.strip():
                raise ValueError("Claude returned empty patch")
            
            # Validate patch format
            if not self._is_valid_patch(patch):
                raise ValueError("Invalid patch format returned")
            
            # Apply patch
            success, message = self.git.apply_patch(patch)
            if not success:
                raise RuntimeError(f"Patch application failed: {message}")
            
            # Commit changes
            commit_msg = f"auto: {task_id} - {task_text[:60]}"
            if not self.git.commit(commit_msg):
                raise RuntimeError("Commit failed")
            
            # Run build and tests
            build_result = self._run_build()
            test_result = self._run_tests()
            
            # Prepare result
            result = {
                "status": "success",
                "task_id": task_id,
                "branch": branch,
                "build": build_result,
                "tests": test_result,
                "diff_summary": self.git.get_diff_summary()
            }
            
            # Notify success
            self._notify_result(result, card)
            
            return result
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            
            # Reset to clean state
            self.git.ensure_clean()
            self.git.checkout_branch(DEFAULT_BRANCH)
            
            result = {
                "status": "failed",
                "task_id": task_id,
                "error": str(e)
            }
            
            # Notify failure
            notify(f"❌ Task {task_id} failed:\n{str(e)[:200]}")
            
            return result
    
    def _is_valid_patch(self, patch: str) -> bool:
        """Check if patch has valid format"""
        valid_starts = ("diff --git", "Index:", "---", "+++")
        return any(patch.strip().startswith(s) for s in valid_starts)
    
    def _run_build(self) -> Dict[str, Any]:
        """Run build command"""
        if not BUILD_CMD:
            return {"skipped": True}
        
        result = self.git.run(BUILD_CMD)
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout[:1000] if result.stdout else "",
            "errors": result.stderr[:1000] if result.stderr else ""
        }
    
    def _run_tests(self) -> Dict[str, Any]:
        """Run test command"""
        if not TEST_CMD:
            return {"skipped": True}
        
        result = self.git.run(TEST_CMD)
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout[:1000] if result.stdout else "",
            "errors": result.stderr[:1000] if result.stderr else ""
        }
    
    def _notify_result(self, result: Dict[str, Any], card: Dict[str, Any]):
        """Send notification based on result"""
        task_id = result["task_id"]
        branch = result.get("branch", "unknown")
        
        # Check overall success
        build_ok = result["build"].get("skipped") or result["build"].get("success")
        tests_ok = result["tests"].get("skipped") or result["tests"].get("success")
        
        if build_ok and tests_ok:
            msg = f"✅ {task_id} completed on `{branch}`\n"
            msg += f"📝 {card['text'][:100]}"
            
            if result.get("diff_summary"):
                msg += f"\n\n📊 Changes:\n```\n{result['diff_summary'][:300]}\n```"
            
            notify(msg)
        else:
            msg = f"⚠️ {task_id} on `{branch}` - issues detected\n"
            
            if not build_ok:
                msg += f"\n🔨 Build failed:\n```\n{result['build'].get('errors', '')[:300]}\n```"
            
            if not tests_ok:
                msg += f"\n🧪 Tests failed:\n```\n{result['tests'].get('errors', '')[:300]}\n```"
            
            notify(msg)

def main_loop():
    """Main processing loop"""
    processor = TaskProcessor()
    
    logger.info(f"Starting task runner - polling every {POLL_INTERVAL}s")
    notify("🚀 Claude Runner started")
    
    while True:
        try:
            # Check for new tasks
            task_files = sorted(INBOX.glob("*.json"))
            
            for task_file in task_files:
                logger.info(f"Found task: {task_file.name}")
                
                # Move to processing
                processing_file = PROCESSING / task_file.name
                shutil.move(str(task_file), str(processing_file))
                
                try:
                    # Process the task
                    result = processor.process_card(processing_file)
                    
                    # Save result
                    result_file = DONE / f"{task_file.stem}_result.json"
                    result_file.write_text(
                        json.dumps(result, indent=2),
                        encoding="utf-8"
                    )
                    
                finally:
                    # Move to done
                    done_file = DONE / task_file.name
                    shutil.move(str(processing_file), str(done_file))
            
            # Wait before next poll
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            notify("🛑 Claude Runner stopped")
            break
            
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main_loop()
