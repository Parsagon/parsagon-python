from typing import Dict, List, Any


class CustomFunction:
    """
    A custom function to be converted to one or more transformers on the backend
    """

    def __init__(self, name: str, arguments: Dict[str, Any], examples: List[Dict]):
        """
        :param name: The name of the custom function as it is known to GPT.
        :param arguments: Arguments used for the actual performing of the function.
        :param examples: Holds other values useful for the creation of transformers.
        """
        self.name = name
        self.arguments = arguments
        self.examples = examples

    def to_json(self):
        return {
            "name": self.name,
            "arguments": self.arguments,
            "examples_data": self.examples,
        }
