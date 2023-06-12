from typing import Dict, List, Any


class CustomFunction:
    """
    A custom function to be converted to one or more transformers on the backend
    """

    def __init__(self, name: str, arguments: Dict[str, Any], examples: List[Dict], call_id: int):
        """
        :param name: The name of the custom function as it is known to GPT.
        :param arguments: Arguments used for the actual performing of the function.
        :param examples: Holds other values useful for the creation of transformers.
        :param call_id: The call ID of the custom function.
        """
        self.name = name
        self.arguments = arguments
        self.examples = examples
        self.call_id = call_id

    def to_json(self):
        return {
            "name": self.name,
            "arguments": self.arguments,
            "examples": self.examples,
            "call_id": self.call_id,
        }
