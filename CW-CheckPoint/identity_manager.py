class IdentityManager:
    def __init__(self):
        self._name = None
        self.awaiting_name = False

    def expect_name(self):
        self.awaiting_name = True   #true when the bot has asked for user name

    def handle_set(self, text: str):
        name = self._extract_name(text) or self._extract_free_name(text)
        if name:
            self._name = name.capitalize()
            self.awaiting_name = False          #name has been taken
            print(f"Bot: Nice to meet you, {self._name}!")
        else:
            self.awaiting_name = True
            print('Bot: Sorry, I didn’t catch your name there. Try typing “my name is <Name>” or just type your first name.')

    def handle_get(self):
        if self._name:                              # printing user name
            print(f"Bot: Your name is {self._name}.")
        else:
            print('Bot: I don’t know yet. Type “my name is <Name>” please to tell me!.')

    def maybe_set_from_free_text(self, text: str) -> bool:
        if not self.awaiting_name:          #expecting a name alone
            return False
        name = self._extract_free_name(text)
        if name:
            self._name = name.capitalize()
            self.awaiting_name = False
            print(f"Bot: Nice to meet you, {self._name}!")
            return True
        return False

    def _extract_name(self, text: str) -> str:
        low = text.lower()
        key = "my name is"      #extracting name after this key
        if key in low:
            start = low.index(key) + len(key)
            tail = text[start:].strip()
            if tail:
                return tail.split()[0].strip(",.!?;:")
        return ""

    def _extract_free_name(self, text: str) -> str:
        tokens = [t.strip(",.!?;:") for t in text.split()]      # similar name extraction
        if len(tokens) == 1 and tokens[0].isalpha() and 2 <= len(tokens[0]) <= 30:
            return tokens[0]
        low = text.lower()
        if low.startswith("i am ") and len(tokens) >= 3:
            return tokens[2]
        if low.startswith("im ") and len(tokens) >= 2:
            return tokens[1]
        return ""

    @property
    def name(self):             #make name accessible
        return self._name
