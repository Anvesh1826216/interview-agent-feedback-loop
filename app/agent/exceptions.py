class InvalidStateError(Exception):
    pass


class MissingUserInputError(Exception):
    pass


class LLMUnavailableError(Exception):
    pass


class PromptNotFoundError(Exception):
    pass


class ConversationNotFoundError(Exception):
    pass