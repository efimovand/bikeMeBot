from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_policy = State()
    after_bike = State()


class BikeStates(StatesGroup):
    choosing_brand = State()
    choosing_model = State()
    choosing_color = State()


class HelmetStates(StatesGroup):
    choosing_brand = State()
    choosing_model = State()
    choosing_color = State()


class PhotoStates(StatesGroup):
    waiting_front = State()
    waiting_side = State()
    waiting_body = State()


class JacketStates(StatesGroup):
    choosing_brand = State()
    choosing_model = State()
    choosing_color = State()


class SuitStates(StatesGroup):
    choosing_brand = State()
    choosing_model = State()
    choosing_color = State()


class GloveStates(StatesGroup):
    choosing_brand = State()
    choosing_model = State()
    choosing_color = State()


class BootStates(StatesGroup):
    choosing_brand = State()
    choosing_model = State()
    choosing_color = State()


class LocationStates(StatesGroup):
    choosing_location = State()