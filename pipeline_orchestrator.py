"""
Pipeline Orchestrator - Manages the Mobile → ChatGPT → Claude → Cursor workflow
This is the core engine that processes tasks through each stage
"""

import os
import time
import json
import subprocess
import shutil
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from dotenv import load_dotenv
from anthropic import Anthropic
import openai
from notifier import notify, notify_progress
import subprocess

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
INBOX = Path("tasks/inbox")
PLANNING = Path("tasks/planning")  # ChatGPT planning stage
IMPLEMENTATION = Path("tasks/implementation")  # Claude implementation stage
CURSOR_READY = Path("tasks/cursor_ready")  # Ready for Cursor
DONE = Path("tasks/done")

# Create all directories
for p in (INBOX, PLANNING, IMPLEMENTATION, CURSOR_READY, DONE, Path("logs")):
    p.mkdir(parents=True, exist_ok=True)

# AutoHotkey configuration for desktop delivery
BASE = Path(__file__).resolve().parent
AHK_EXE = r"C:\\Program Files\\AutoHotkey\\v2\\AutoHotkey64.exe"
SEND_AHK = str(BASE / "send_to.ahk")

def _send_to_desktop(target: str, text: str) -> bool:
    """Send text to a desktop app via AutoHotkey. Returns True on success."""
    try:
        if not Path(AHK_EXE).exists() or not Path(SEND_AHK).exists():
            logger.warning("AutoHotkey not configured; skipping desktop send")
            return False

        # Write message to a temp file in cursor tasks area for traceability
        tmp_dir = BASE / "tasks" / "inbox"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = tmp_dir / f"cursor_msg_{uuid.uuid4().hex[:8]}.txt"
        tmp_file.write_text(text, encoding="utf-8")

        try:
            result = subprocess.run(
                [AHK_EXE, SEND_AHK, target, str(tmp_file)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                logger.error(f"AHK send failed ({result.returncode}): {result.stderr[:200] if result.stderr else ''}")
                return False
            return True
        finally:
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Failed to send via AHK: {e}")
        return False

# Initialize API clients
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

if OPENAI_KEY:
    openai.api_key = OPENAI_KEY
    
CLAUDE = Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

# Configuration
REPO = Path(os.getenv("REPO_PATH", "."))
CHATGPT_MODEL = os.getenv("CHATGPT_MODEL", "gpt-4-turbo-preview")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", "5"))


class ChatGPTPlanner:
    """
    Stage 1: ChatGPT for high-level planning and architecture
    Converts user directives into detailed technical specifications
    """
    
    SYSTEM_PROMPT = """You are a senior software architect creating detailed technical specifications.
    
Your role is to transform high-level user requests into comprehensive implementation plans.
Output a structured specification that includes:

1. OBJECTIVE: Clear statement of what needs to be accomplished
2. COMPONENTS: List of components/modules to create or modify
3. IMPLEMENTATION STEPS: Ordered list of specific coding tasks
4. TECHNICAL DETAILS: Specific algorithms, patterns, or approaches to use
5. FILE STRUCTURE: Which files to create/modify and their purposes
6. ACCEPTANCE CRITERIA: How to verify the implementation works
7. CONSIDERATIONS: Performance, security, or compatibility notes

Be specific about:
- Function/class names
- Data structures  
- API contracts
- Error handling
- Edge cases

Output in clear, structured format that can be directly implemented by another AI."""

    def __init__(self):
        self.client = openai
    
    def create_plan(self, user_directive: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform user directive into detailed technical plan
        
        Args:
            user_directive: High-level task from user
            context: Repository and project context
            
        Returns:
            Detailed implementation plan
        """
        logger.info(f"ChatGPT planning: {user_directive[:50]}...")
        
        try:
            # Build context-aware prompt
            prompt = self._build_planning_prompt(user_directive, context)
            
            response = self.client.chat.completions.create(
                model=CHATGPT_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            plan_text = response.choices[0].message.content
            
            # Parse and structure the plan
            plan = {
                "original_directive": user_directive,
                "plan_text": plan_text,
                "components": self._extract_components(plan_text),
                "steps": self._extract_steps(plan_text),
                "files": self._extract_files(plan_text),
                "acceptance": self._extract_acceptance(plan_text),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Plan created with {len(plan['steps'])} steps")
            return plan
            
        except Exception as e:
            logger.error(f"ChatGPT planning failed: {e}")
            return None
    
    def _build_planning_prompt(self, directive: str, context: Dict[str, Any]) -> str:
        """Build context-aware planning prompt"""
        return f"""Project Context:
- Repository: {context.get('repo_path', 'unknown')}
- Language: {context.get('language', 'C++')}
- Build System: {context.get('build_system', 'CMake')}
- Current Branch: {context.get('branch', 'main')}

User Directive:
{directive}

Create a detailed technical specification for implementing this directive.
Be specific about implementation details, not abstract concepts."""
    
    def _extract_components(self, plan_text: str) -> List[str]:
        """Extract component list from plan"""
        # Simple extraction - can be enhanced with better parsing
        components = []
        if "COMPONENTS:" in plan_text:
            section = plan_text.split("COMPONENTS:")[1].split("\n\n")[0]
            components = [line.strip("- ").strip() 
                         for line in section.split("\n") 
                         if line.strip().startswith("-")]
        return components
    
    def _extract_steps(self, plan_text: str) -> List[str]:
        """Extract implementation steps"""
        steps = []
        if "IMPLEMENTATION STEPS:" in plan_text:
            section = plan_text.split("IMPLEMENTATION STEPS:")[1].split("\n\n")[0]
            steps = [line.strip("1234567890. ").strip() 
                    for line in section.split("\n") 
                    if line.strip() and line[0].isdigit()]
        return steps
    
    def _extract_files(self, plan_text: str) -> List[Dict[str, str]]:
        """Extract file structure"""
        files = []
        if "FILE STRUCTURE:" in plan_text:
            section = plan_text.split("FILE STRUCTURE:")[1].split("\n\n")[0]
            for line in section.split("\n"):
                if "/" in line or "\\" in line or ".cpp" in line or ".h" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        files.append({
                            "path": parts[0].strip("- ").strip(),
                            "purpose": parts[1].strip()
                        })
        return files
    
    def _extract_acceptance(self, plan_text: str) -> List[str]:
        """Extract acceptance criteria"""
        criteria = []
        if "ACCEPTANCE CRITERIA:" in plan_text:
            section = plan_text.split("ACCEPTANCE CRITERIA:")[1].split("\n\n")[0]
            criteria = [line.strip("- ").strip() 
                       for line in section.split("\n") 
                       if line.strip().startswith("-")]
        return criteria


class ClaudeImplementer:
    """
    Stage 2: Claude for actual code implementation
    Converts ChatGPT's plan into concrete code/patches
    """
    
    SYSTEM_PROMPT = """You are Claude, an expert programmer implementing code based on technical specifications.

You receive detailed plans from ChatGPT and implement them as unified diff patches.

CRITICAL RULES:
1. Output ONLY a unified diff patch (git apply compatible)
2. NO explanations, NO markdown, NO code fences
3. Start with 'diff --git' immediately
4. Implement EXACTLY what the plan specifies
5. Include all necessary files in a single patch
6. Ensure code is production-ready with error handling

Follow the plan's specifications precisely, including:
- File paths
- Function/class names
- Data structures
- API contracts
- Error handling requirements

The code should be clean, efficient, and well-structured."""

    def __init__(self, client: Anthropic):
        self.client = client
    
    def implement_plan(self, plan: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Generate implementation based on ChatGPT's plan
        
        Args:
            plan: Technical plan from ChatGPT
            context: Repository context
            
        Returns:
            Unified diff patch
        """
        logger.info("Claude implementing plan...")
        
        try:
            prompt = self._build_implementation_prompt(plan, context)
            
            message = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=8192,
                temperature=0,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            
            patch = message.content[0].text if message.content else ""
            
            # Validate patch format
            if not self._is_valid_patch(patch):
                logger.error("Invalid patch format from Claude")
                return None
            
            logger.info("Implementation patch generated")
            return patch
            
        except Exception as e:
            logger.error(f"Claude implementation failed: {e}")
            return None
    
    def _build_implementation_prompt(self, plan: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Build implementation prompt from plan"""
        
        prompt_parts = [
            f"Repository: {context.get('repo_path', 'unknown')}",
            f"Branch: {context.get('branch', 'main')}",
            "",
            "TECHNICAL SPECIFICATION FROM CHATGPT:",
            "=" * 50,
            plan['plan_text'],
            "=" * 50,
            "",
            "Implement this specification as a unified diff patch.",
            "Create/modify all necessary files as specified.",
            "Output ONLY the patch, no explanations."
        ]
        
        return "\n".join(prompt_parts)
    
    def _is_valid_patch(self, patch: str) -> bool:
        """Validate patch format"""
        if not patch.strip():
            return False
        
        valid_starts = ("diff --git", "Index:", "---", "+++")
        return any(patch.strip().startswith(s) for s in valid_starts)


class CursorIntegration:
    """
    Stage 3: Prepare and apply code for Cursor AI
    Formats patches and creates Cursor-ready artifacts
    """
    
    def __init__(self, repo_path: Path):
        self.repo = repo_path
        self.cursor_dir = repo_path / ".cursor_tasks"
        self.cursor_dir.mkdir(exist_ok=True)
    
    def prepare_for_cursor(self, patch: str, plan: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        Prepare implementation for Cursor AI
        
        Creates structured files that Cursor can use for:
        - Code review
        - Testing
        - Integration
        - Documentation
        """
        logger.info(f"Preparing {task_id} for Cursor...")
        
        task_dir = self.cursor_dir / task_id
        task_dir.mkdir(exist_ok=True)
        
        # Save patch file
        patch_file = task_dir / "implementation.patch"
        patch_file.write_text(patch, encoding="utf-8")
        
        # Create Cursor instruction file
        cursor_instructions = self._create_cursor_instructions(plan, task_id)
        (task_dir / "cursor_instructions.md").write_text(cursor_instructions)
        
        # Create test checklist
        test_checklist = self._create_test_checklist(plan)
        (task_dir / "test_checklist.md").write_text(test_checklist)
        
        # Create integration guide
        integration_guide = self._create_integration_guide(plan, patch)
        (task_dir / "integration_guide.md").write_text(integration_guide)
        
        # Prepare Cursor context file
        cursor_context = {
            "task_id": task_id,
            "original_directive": plan['original_directive'],
            "components": plan['components'],
            "files_modified": plan['files'],
            "acceptance_criteria": plan['acceptance'],
            "patch_file": str(patch_file),
            "instructions_file": str(task_dir / "cursor_instructions.md"),
            "timestamp": datetime.now().isoformat()
        }
        
        context_file = task_dir / "cursor_context.json"
        context_file.write_text(json.dumps(cursor_context, indent=2))
        
        logger.info(f"Cursor package ready at {task_dir}")
        return cursor_context
    
    def _create_cursor_instructions(self, plan: Dict[str, Any], task_id: str) -> str:
        """Create instructions for Cursor AI"""
        return f"""# Cursor AI Integration Instructions

## Task ID: {task_id}

## Original Request
{plan['original_directive']}

## Implementation Overview
This task has been planned by ChatGPT and implemented by Claude.
Your role is to:

1. **Review** the implementation patch
2. **Apply** the patch to the working branch
3. **Test** against acceptance criteria
4. **Integrate** with existing codebase
5. **Optimize** for performance and maintainability

## Components Modified
{chr(10).join('- ' + c for c in plan['components'])}

## Files Affected
{chr(10).join(f"- {f['path']}: {f['purpose']}" for f in plan['files'])}

## Implementation Steps Completed
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(plan['steps']))}

## Your Tasks in Cursor

### 1. Apply Patch
```bash
git apply implementation.patch
```

### 2. Verify Implementation
- Check syntax and compilation
- Ensure no breaking changes
- Validate against acceptance criteria

### 3. Run Tests
```bash
{os.getenv('TEST_CMD', 'make test')}
```

### 4. Code Review Checklist
- [ ] Code follows project style guide
- [ ] No memory leaks or resource issues
- [ ] Error handling is comprehensive
- [ ] Documentation is updated
- [ ] Tests cover new functionality

### 5. Performance Validation
- [ ] No performance regressions
- [ ] Efficient algorithms used
- [ ] Resource usage is optimized

## Notes for Cursor
- Use your code analysis to identify potential issues
- Suggest improvements where applicable
- Ensure integration doesn't break existing features
"""
    
    def _create_test_checklist(self, plan: Dict[str, Any]) -> str:
        """Create test checklist for Cursor"""
        return f"""# Test Checklist

## Acceptance Criteria
{chr(10).join(f"- [ ] {criterion}" for criterion in plan['acceptance'])}

## Unit Tests
- [ ] All new functions have unit tests
- [ ] Edge cases are covered
- [ ] Error conditions are tested
- [ ] Mock objects used where appropriate

## Integration Tests
- [ ] Feature works with existing systems
- [ ] No regressions in related features
- [ ] Performance benchmarks pass
- [ ] Memory usage is acceptable

## Manual Testing
- [ ] Feature works as expected in UI
- [ ] User experience is smooth
- [ ] No visual glitches or artifacts
- [ ] Responsive under load

## Test Commands
```bash
# Unit tests
{os.getenv('TEST_CMD', 'make test')}

# Integration tests
make integration-test

# Performance tests
make perf-test
```
"""
    
    def _create_integration_guide(self, plan: Dict[str, Any], patch: str) -> str:
        """Create integration guide for Cursor"""
        return f"""# Integration Guide

## Pre-Integration Checklist
- [ ] Current branch is clean
- [ ] All tests passing on main
- [ ] Dependencies are updated

## Integration Steps

### 1. Create Feature Branch
```bash
git checkout -b feature/{plan['original_directive'][:30].replace(' ', '-').lower()}
```

### 2. Apply Implementation
```bash
git apply implementation.patch
```

### 3. Build Project
```bash
{os.getenv('BUILD_CMD', 'make')}
```

### 4. Run Tests
```bash
{os.getenv('TEST_CMD', 'make test')}
```

### 5. Commit Changes
```bash
git add -A
git commit -m "Implement: {plan['original_directive'][:60]}"
```

## Merge Checklist
- [ ] All CI checks pass
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] No merge conflicts

## Post-Merge
- [ ] Deploy to staging
- [ ] Smoke test in staging
- [ ] Update task tracker
- [ ] Notify team

## Rollback Plan
If issues are detected:
```bash
git revert HEAD
git push origin main
```
"""


class PipelineOrchestrator:
    """
    Main orchestrator that manages the complete pipeline:
    Mobile → ChatGPT → Claude → Cursor
    """
    
    def __init__(self):
        self.chatgpt = ChatGPTPlanner() if OPENAI_KEY else None
        self.claude = ClaudeImplementer(CLAUDE) if CLAUDE else None
        self.cursor = CursorIntegration(REPO)
        self.git = GitRepo(REPO)
    
    def process_task(self, task_file: Path) -> Dict[str, Any]:
        """
        Process a task through the complete pipeline
        """
        # Load task
        task = json.loads(task_file.read_text(encoding="utf-8"))
        task_id = task["id"]
        directive = task["text"]
        
        logger.info(f"Processing {task_id}: {directive[:50]}...")
        notify_progress(task_id, "processing", f"Starting pipeline for: {directive[:50]}...")
        
        result = {
            "task_id": task_id,
            "directive": directive,
            "stages": {}
        }
        
        try:
            # Stage 1: ChatGPT Planning
            if self.chatgpt:
                notify_progress(task_id, "processing", "🧠 ChatGPT creating technical plan...")
                
                context = self._get_repo_context()
                plan = self.chatgpt.create_plan(directive, context)
                
                if not plan:
                    raise ValueError("ChatGPT planning failed")
                
                result["stages"]["planning"] = {
                    "status": "success",
                    "plan": plan
                }
                
                # Save plan
                plan_file = PLANNING / f"{task_id}_plan.json"
                plan_file.write_text(json.dumps(plan, indent=2))
                
                notify_progress(task_id, "processing", 
                              f"✅ Plan created with {len(plan['steps'])} steps")
            else:
                logger.warning("ChatGPT not configured, skipping planning")
                plan = self._create_fallback_plan(directive)
            
            # Stage 2: Claude Implementation
            if self.claude:
                notify_progress(task_id, "processing", "💻 Claude implementing code...")
                
                patch = self.claude.implement_plan(plan, self._get_repo_context())
                
                if not patch:
                    raise ValueError("Claude implementation failed")
                
                result["stages"]["implementation"] = {
                    "status": "success",
                    "patch_size": len(patch)
                }
                
                # Save patch
                patch_file = IMPLEMENTATION / f"{task_id}.patch"
                patch_file.write_text(patch, encoding="utf-8")
                
                notify_progress(task_id, "processing", "✅ Implementation complete")
            else:
                raise ValueError("Claude not configured")
            
            # Stage 3: Cursor Preparation
            notify_progress(task_id, "processing", "📦 Preparing for Cursor AI...")
            
            cursor_package = self.cursor.prepare_for_cursor(patch, plan, task_id)
            
            result["stages"]["cursor_prep"] = {
                "status": "success",
                "package": cursor_package
            }
            
            # Move to cursor_ready
            final_file = CURSOR_READY / f"{task_id}_ready.json"
            final_file.write_text(json.dumps(result, indent=2))
            
            # Create notification with full details
            self._send_completion_notification(task_id, plan, cursor_package)

            # Optionally push instructions directly into Cursor chat if enabled
            if os.getenv("ENABLE_CURSOR_AUTOSEND", "").lower() in ("1", "true", "yes"): 
                try:
                    instructions_text = (
                        f"Task {task_id} is ready for application.\n\n"
                        f"Apply the patch and run checks:\n"
                        f"git apply \"{cursor_package['patch_file']}\"\n"
                        f"{os.getenv('BUILD_CMD', '').strip()}\n"
                        f"{os.getenv('TEST_CMD', '').strip()}\n\n"
                        f"Open instructions: {cursor_package['instructions_file']}"
                    ).strip()
                    if instructions_text:
                        sent = _send_to_desktop("cursor", instructions_text)
                        if sent:
                            logger.info("Cursor instructions sent to desktop chat")
                        else:
                            logger.info("Skipped sending to Cursor chat (AHK not configured or failed)")
                except Exception as e:
                    logger.error(f"Failed to push instructions to Cursor: {e}")
            
            result["status"] = "success"
            
        except Exception as e:
            logger.error(f"Pipeline failed for {task_id}: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
            
            notify(f"❌ Task {task_id} failed:\n{str(e)[:200]}")
        
        return result
    
    def _get_repo_context(self) -> Dict[str, Any]:
        """Get repository context"""
        return {
            "repo_path": str(REPO),
            "branch": self.git.get_current_branch(),
            "language": "C++",  # Can be detected
            "build_system": "CMake"  # Can be detected
        }
    
    def _create_fallback_plan(self, directive: str) -> Dict[str, Any]:
        """Create simple plan when ChatGPT not available"""
        return {
            "original_directive": directive,
            "plan_text": f"Implement: {directive}",
            "components": ["main"],
            "steps": ["Implement the requested feature"],
            "files": [],
            "acceptance": ["Feature works as requested"]
        }
    
    def _send_completion_notification(self, task_id: str, plan: Dict[str, Any], 
                                     cursor_package: Dict[str, Any]):
        """Send detailed completion notification"""
        msg = f"""✅ **Task {task_id} Ready for Cursor**

**Original Request:**
{plan['original_directive']}

**Pipeline Stages Completed:**
1. ✅ ChatGPT Planning - {len(plan['steps'])} steps defined
2. ✅ Claude Implementation - Patch generated
3. ✅ Cursor Package - Ready at `.cursor_tasks/{task_id}/`

**Components to Review:**
{chr(10).join('• ' + c for c in plan['components'][:5])}

**Next Steps in Cursor:**
1. Open `{cursor_package['instructions_file']}`
2. Apply patch: `git apply {cursor_package['patch_file']}`
3. Run tests and validate
4. Merge when ready

**Files Ready:**
• `implementation.patch` - Code changes
• `cursor_instructions.md` - Integration guide
• `test_checklist.md` - Testing requirements
"""
        notify(msg)


class GitRepo:
    """Git repository operations"""
    
    def __init__(self, repo_path: Path):
        self.repo = repo_path
    
    def run(self, cmd: str) -> subprocess.CompletedProcess:
        """Run git command"""
        return subprocess.run(cmd, cwd=self.repo, shell=True, 
                            capture_output=True, text=True)
    
    def get_current_branch(self) -> str:
        """Get current branch"""
        result = self.run("git rev-parse --abbrev-ref HEAD")
        return result.stdout.strip() if result.returncode == 0 else "main"


def main_loop():
    """Main processing loop"""
    orchestrator = PipelineOrchestrator()
    
    logger.info("Pipeline Orchestrator started")
    notify("🚀 Pipeline started: Mobile → ChatGPT → Claude → Cursor")
    
    while True:
        try:
            # Check for new tasks
            task_files = sorted(INBOX.glob("*.json"))
            
            for task_file in task_files:
                logger.info(f"Processing task: {task_file.name}")
                
                # Move to planning stage
                planning_file = PLANNING / task_file.name
                shutil.move(str(task_file), str(planning_file))
                
                try:
                    # Process through pipeline
                    result = orchestrator.process_task(planning_file)
                    
                    # Archive completed task
                    done_file = DONE / f"{task_file.stem}_complete.json"
                    done_file.write_text(json.dumps(result, indent=2))
                    
                finally:
                    # Clean up planning file
                    if planning_file.exists():
                        planning_file.unlink()
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("Shutting down pipeline...")
            notify("🛑 Pipeline stopped")
            break
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
