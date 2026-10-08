from controller import Controller
from input_handler import InputHandler
from intent_router import IntentRouter
from qa_retriever import QARetriever
from identity_manager import IdentityManager
from small_talk_manager import SmallTalkManager

from handle_flight import FlightDatabase
from booking_retrieval import BookingExampleRetriever

INTENTS_CSV = "data/intents.csv"            #paths to datasets used in the system
BOOKING_EXAMPLES_CSV = "data/flight.csv"
TIMETABLE_CSV = "data/times.csv"
QA_CSV = "data/COMP3074-CW1-Dataset.csv"

class App:
    def __init__(self):
        self.input = InputHandler()                                         #core input and routing components
        self.router = IntentRouter(INTENTS_CSV, min_confidence=0.30)
        self.identity = IdentityManager()                                   #identity management and small talk
        self.small_talk = SmallTalkManager(identity_ref=self.identity)
        self.qa = QARetriever(QA_CSV)                                           #QA component
        self.flight_db = FlightDatabase(TIMETABLE_CSV)                          #flight data and support
        self.booking_examples = BookingExampleRetriever(BOOKING_EXAMPLES_CSV)

        self.controller = Controller(                                       #main dialogue controller
            input_handler=self.input,
            router=self.router,
            identity=self.identity,
            small_talk=self.small_talk,
            qa=self.qa,
            flight_db=self.flight_db,
            booking_examples=self.booking_examples,
        )
    #call the controller to get started
    def run(self):
        self.controller.run()   #start the controller chat loop
