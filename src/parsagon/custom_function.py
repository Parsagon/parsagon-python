from typing import Dict, Any


class CustomFunction:
    """
    A custom function to be converted to transformers on the backend
    """

    def __init__(self, transformer_type: str, arguments: Dict[str, Any], examples, call_id: int):
        self.type = transformer_type
        self.arguments = arguments
        self.examples = examples
        self.call_id = call_id

    def as_dict(self):
        return {
            "type": self.type,
            "arguments": self.arguments,
            "examples": self.examples,
            "call_id": self.call_id,
        }
