#!/usr/bin/env python3
"""
Simple echo test program that repeats user input.
"""

def echo_program():
    """
    Continuously prompt user for input and echo it back.
    Type 'quit', 'exit', or 'q' to exit the program.
    """
    print("Echo Test Program")
    print("Type 'quit', 'exit', or 'q' to exit")
    print("-" * 40)

    while True:
        try:
            # Get user input
            user_input = input("Enter something: ")

            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            # Echo the input back to user
            print(f"You said: {user_input}")
            print()  # Add blank line for better readability

        except KeyboardInterrupt:
            print("\nProgram interrupted. Goodbye!")
            break
        except EOFError:
            print("\nEnd of input. Goodbye!")
            break

if __name__ == "__main__":
    echo_program()