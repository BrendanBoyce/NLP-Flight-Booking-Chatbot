from booking import BookingTransaction
class Controller:

    #Initialise classes ready for user input
    def __init__(self, input_handler, router, qa, identity, small_talk, flight_db, booking_examples, booking=None):
        self.input = input_handler                      #core components
        self.router = router
        self.qa = qa
        self.identity = identity
        self.small_talk = small_talk
        self.flight_db = flight_db                      #booking components
        self.booking_examples = booking_examples
        self.booking = booking

    def run(self):
        print("Welcome to the interactive chatbot!")
        while True:
            text = self.input.get_input()
            if self.input.is_exit_command(text):        #exit
                print("Bot: Goodbye!")
                break

            if self.booking is not None and not self.booking.is_finished(): #skip intent matching during a booking transaction stage
                response = self.booking.handle_input(text)
                print(f"Bot: {response}")

                if self.booking.is_finished():                  # If finished booking, reset

                    self.booking = None

                continue

            hit = self.router.predict(text)             #intent matching

            # if asked for their name, accept a one word answer
            if self.identity.awaiting_name and self.identity.maybe_set_from_free_text(text):
                continue

            # intent routing based on the identity gathered
            if hit.label == "identity_set":
                reply = self.identity.handle_set(text)
                if reply:
                    print(f"Bot: {reply}")

            elif hit.label == "identity_get":
                reply = self.identity.handle_get()
                if reply:
                    print(f"Bot: {reply}")

            elif hit.label == "qa":
                ans = self.qa.answer(text)
                print(f"Bot: {ans.answer}")

            elif hit.label == "small_talk":
                reply = self.small_talk.handle(text)
                if reply:
                    print(f"Bot: {reply}")

            elif hit.label == "capabilities":
                    print(
                        "Bot: I can do a few things with you:\n"
                        "- Book a flight (for example: 'book a flight from London to Madrid')\n"
                        "- Tell you where you can fly from a specified city\n"
                        "- Remember and tell you your name\n"
                        "- Answer general questions, sometimes\n"
                        "- Have a bit of small talk with you\n"
                        "You can say 'help' at any time, or 'exit' to quit."
                    )

            elif hit.label == "booking":    #start new booking transaction

                if self.booking is None or self.booking.is_finished():
                    self.booking = BookingTransaction(
                        flight_db=self.flight_db,
                        example_retriever=self.booking_examples
                    )
                reply = self.booking.handle_input(text)

                print(f"Bot: {reply}")
            else:
                print("Bot: I’m not sure I understood. Try asking the question differently.")
