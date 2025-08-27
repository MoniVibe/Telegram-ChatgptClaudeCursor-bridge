#!/usr/bin/env python3
"""
Setup script - Initialize the orchestrator system
Run this first to configure everything
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv, set_key

def check_python():
    """Check Python version"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ Python 3.10+ required")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")

def install_requirements():
    """Install required packages"""
    print("\n📦 Installing requirements...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Requirements installed")
    else:
        print(f"❌ Installation failed: {result.stderr}")
        sys.exit(1)

def setup_telegram():
    """Guide through Telegram setup"""
    print("\n🤖 Telegram Bot Setup")
    print("1. Open Telegram and search for @BotFather")
    print("2. Send /newbot and follow instructions")
    print("3. Copy the bot token")
    
    token = input("\nEnter bot token (or press Enter to skip): ").strip()
    if token:
        set_key(".env", "TELEGRAM_BOT_TOKEN", token)
        print("✅ Bot token saved")
        
        print("\n4. Run: python bridge_bot.py")
        print("5. Send /start to your bot")
        print("6. Copy the chat ID shown")
        
        chat_id = input("\nEnter chat ID (or press Enter to skip): ").strip()
        if chat_id:
            set_key(".env", "TELEGRAM_CHAT_ID", chat_id)
            print("✅ Chat ID saved")

def setup_claude():
    """Guide through Claude API setup"""
    print("\n🧠 Claude API Setup")
    print("1. Go to https://console.anthropic.com/")
    print("2. Create an API key")
    
    api_key = input("\nEnter Claude API key (or press Enter to skip): ").strip()
    if api_key:
        set_key(".env", "ANTHROPIC_API_KEY", api_key)
        print("✅ API key saved")

def setup_repository():
    """Configure repository path"""
    print("\n📁 Repository Setup")
    
    current = os.getenv("REPO_PATH", "")
    if current:
        print(f"Current repo: {current}")
        change = input("Change? (y/N): ").lower() == 'y'
        if not change:
            return
    
    repo_path = input("Enter repository path: ").strip()
    if repo_path:
        repo_path = Path(repo_path).resolve()
        if repo_path.exists():
            set_key(".env", "REPO_PATH", str(repo_path))
            print(f"✅ Repository set to: {repo_path}")
        else:
            print(f"❌ Path not found: {repo_path}")

def test_setup():
    """Test the configuration"""
    print("\n🧪 Testing Configuration...")
    
    load_dotenv()
    
    # Check critical settings
    checks = {
        "ANTHROPIC_API_KEY": "Claude API",
        "TELEGRAM_BOT_TOKEN": "Telegram Bot",
        "TELEGRAM_CHAT_ID": "Telegram Chat",
        "REPO_PATH": "Repository Path"
    }
    
    all_good = True
    for key, name in checks.items():
        value = os.getenv(key)
        if value and value != "..." and value != "YOUR_" in value:
            print(f"✅ {name}: Configured")
        else:
            print(f"❌ {name}: Not configured")
            all_good = False
    
    if all_good:
        print("\n✨ Setup complete! You can now run:")
        print("  Terminal 1: python bridge_bot.py")
        print("  Terminal 2: python claude_runner.py")
    else:
        print("\n⚠️ Some settings missing. Run setup.py again to configure.")

def main():
    """Main setup flow"""
    print("🚀 Orchestrator Setup\n")
    
    # Check environment
    check_python()
    
    # Create .env if not exists
    if not Path(".env").exists():
        Path(".env").touch()
        print("✅ Created .env file")
    
    # Install packages
    install_requirements()
    
    # Configure services
    setup_telegram()
    setup_claude()
    setup_repository()
    
    # Test configuration
    test_setup()

if __name__ == "__main__":
    main()
