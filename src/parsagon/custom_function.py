from typing import Dict, Any


class CustomFunction:
    """
    A custom function to be converted to one or more transformers on the backend
    """

    def __init__(self, name: str, arguments: Dict[str, Any], context, call_id: int):
        """
        :param name: The name of the custom function as it is known to GPT.
        :param arguments: Arguments used for the actual performing of the function.
        :param context: Holds other values useful for the creation of transformers.
        :param call_id: The call ID of the custom function.
        """
        self.name = name
        self.arguments = arguments
        self.context = context
        self.call_id = call_id
