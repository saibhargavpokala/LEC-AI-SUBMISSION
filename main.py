"""
LEC AI — Assignment Support Agent
Entry point: CLI menu with 3 modes.
"""

from agent import run_conversation, run_agent
from eval import run_eval, run_ablation_eval


def main():
    print()
    print("=" * 50)
    print("🎓 ASSIGNMENT SUPPORT AGENT")
    print("=" * 50)
    print("  [1] Help with assignment")
    print("  [2] Run evaluation")
    print("  [3] Run prompt ablation")
    print("=" * 50)

    mode = input("\nChoose (1, 2, or 3): ").strip()

    if mode == "2":
        run_eval()
        return

    if mode == "3":
        run_ablation_eval()
        return

    # Mode 1 — paste assignment
    print("\nPaste your assignment below.")
    print("Press Enter twice when done:\n")

    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    brief = "\n".join(lines)

    run_conversation(brief=brief)


if __name__ == "__main__":
    main()