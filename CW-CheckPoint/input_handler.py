class InputHandler:
    def get_input(self, prompt="You: "):             #gets user input
        return input(prompt).strip()

    def is_exit_command(self, text: str) -> bool:    #exits the progam
        return text.lower() in {"exit", "quit"}
