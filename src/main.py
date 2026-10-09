
"""RIKO entry point: choose Text Chat or Voice Chat."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SRC_DIR = str(PROJECT_ROOT / "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from modes.text_chat import main as run_text_chat


def main():
    print("\n========== RIKO ==========")
    print("1. Text Chat")
    print("2. Voice Chat")
    print("0. Exit")

    choice = input("\nChoose mode: ").strip()

    if choice == "1":
        run_text_chat()
    elif choice == "2":
        # Import voice dependencies only when Voice Chat is selected.
        from modes.voice_chat import main as run_voice_chat
        run_voice_chat()
    elif choice == "0":
        print("RIKO closed.")
    else:
        print("Invalid choice. Run RIKO again and choose 0, 1, or 2.")


if __name__ == "__main__":
    main()
