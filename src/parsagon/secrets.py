import ast
import re


def extract_secrets(task):
    secrets = {}
    matches = list(re.finditer(r'\{\s*(?P<var>[A-Za-z_]+)\s*:\s*(?P<value>"([^"]|\\")*")\}', task))
    for match in matches:
        var_name = match.group("var")
        if not var_name.startswith("SECRET"):
            continue
        new_match = re.sub(r'\{([A-Za-z_]+):\s*"([^"]|\\")*"\}', '{\\1: "******"}', match.group(0))
        task = task.replace(match.group(0), new_match)
        secrets[match.group(1)] = ast.literal_eval(match.group(2))
    return task, secrets
