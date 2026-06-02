from aiogram.fsm.state import State, StatesGroup

class RegistrationFSM(StatesGroup):
    choosing_lang = State()
    entering_minecraft_nick = State()

class TaskFSM(StatesGroup):
    waiting_screenshot = State()
    waiting_task_id = State()          # новое: запоминаем, какое задание выполняем

class WithdrawFSM(StatesGroup):
    entering_nick = State()
    confirming = State()               # используется для подтверждения вывода
    changing_nick = State()            # изменение ника перед выводом

class SupportFSM(StatesGroup):
    chatting = State()

class AdminFSM(StatesGroup):
    commenting = State()
    replying_support = State()
    setting_task2_text = State()       # для команды /set_task2
    setting_task2_media = State()