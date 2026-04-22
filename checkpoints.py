def ask_human(prompt: str, options: list = None) -> str:
    """
    Human-in-the-loop checkpoint.
    Shows prompt and optional numbered choices.
    Returns human's response.
    """
    print("\n" + "="*50)
    print("🤚 HUMAN CHECKPOINT")
    print("="*50)
    print(f"\n{prompt}")

    if options:
        for i, opt in enumerate(options, 1):
            print(f"\n  [{i}] {opt}")
        while True:
            choice = input("\nYour choice (number): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(options):
                return options[int(choice) - 1]
            print("Enter a valid number.")
    else:
        return input("\nYour response: ").strip()