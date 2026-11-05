from discord.ext.commands.errors import CheckFailure

class InputError(Exception):
    pass

class NoPerms(CheckFailure):
    def __init__(self, message):
        self.message = ",".join(message) if type(message) != str else message
        super().__init__(self.message)
