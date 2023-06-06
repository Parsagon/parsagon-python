from typing import Dict, Any


class Action:
    # TODO: Take this out if we want

    def __init__(self, action_type: str, arguments: Dict[str, Any], html: str, targets: Dict[str, Any]):
        self.type = action_type
        self.arguments = arguments
        self.html = html
        self.targets = targets

    def as_dict(self):
        return {
            "type": self.type,
            "arguments": self.arguments,
            "html": self.html,
            "targets": self.targets,
        }
