# small_talk_manager.py
class SmallTalkManager:
    def __init__(self, identity_ref=None):
        self.identity = identity_ref  # a reference to IdentityManager

    def handle(self, text: str):
        t = text.lower()

        #greeting branch
        if any(w in t for w in ["hello", "hi", "hey", "hiya"]):
            if self.identity and self.identity.name:                # greet user by name if available
                print(f"Bot: Hello, {self.identity.name}! How are you?")
            else:
                print("Bot: Hi there! I don’t think I know your name yet, what is your name?")
                if self.identity:
                    self.identity.expect_name()             # let system know name is coming

        elif "how are" in t:                                # general small talk
            print("Bot: I’m good thanks for asking!")

        elif any(w in t for w in ["thanks", "thank you"]):
            print("Bot: You’re very welcome!")
        elif any(w in t for w in ["bye", "goodbye", "see you"]):
            print("Bot: Have a good day!")
        else:
            print("Bot: not good")
