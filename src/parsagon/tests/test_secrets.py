import pytest

from parsagon.secrets import extract_secrets


def test_non_secrets_are_not_extracted():
    """
    Non-secrets should not be extracted from task descriptions.
    """
    task = 'Go to https://example.com. Type {username: "myusername"} in the username field'
    task, secrets = extract_secrets(task)
    assert secrets == {}
    assert task == 'Go to https://example.com. Type {username: "myusername"} in the username field'


def test_secret_is_extracted():
    """
    A secret should be extracted and replaced in a task description.
    """
    task = 'Go to https://example.com. Type {SECRET_PASSWORD: "mypassword"} in the password field'
    task, secrets = extract_secrets(task)
    assert secrets == {"SECRET_PASSWORD": "mypassword"}
    assert task == 'Go to https://example.com. Type {SECRET_PASSWORD: "******"} in the password field'


def test_secret_with_quotes_is_extracted():
    """
    A secret with quotes in its value should be extracted and replaced in a task description.
    """
    task = 'Go to https://example.com. Type {SECRET_PASSWORD: "mypassword\\"?!1"} in the password field'
    task, secrets = extract_secrets(task)
    assert secrets == {"SECRET_PASSWORD": 'mypassword"?!1'}
    assert task == 'Go to https://example.com. Type {SECRET_PASSWORD: "******"} in the password field'


def test_multiple_secrets_are_extracted():
    """
    Multiple secrets should be extracted and replaced in the same task description.
    """
    task = 'Go to https://example.com. Type {SECRET_PASSWORD: "mypassword"} in the password field. Type {SECRET_ADDRESS: "myaddress"} in the address field'
    task, secrets = extract_secrets(task)
    assert secrets == {"SECRET_PASSWORD": "mypassword", "SECRET_ADDRESS": "myaddress"}
    assert task == 'Go to https://example.com. Type {SECRET_PASSWORD: "******"} in the password field. Type {SECRET_ADDRESS: "******"} in the address field'


def test_secrets_mixed_with_non_secrets_are_extracted():
    """
    Multiple secrets should be extracted and replaced in the same task description, and non-secrets should remain the same.
    """
    task = 'Go to https://example.com. Type {USERNAME: "myusername"} in the username field. Type {SECRET_PASSWORD: "mypassword"} in the password field. Type {SECRET_ADDRESS: "myaddress"} in the address field'
    task, secrets = extract_secrets(task)
    assert secrets == {"SECRET_PASSWORD": "mypassword", "SECRET_ADDRESS": "myaddress"}
    assert task == 'Go to https://example.com. Type {USERNAME: "myusername"} in the username field. Type {SECRET_PASSWORD: "******"} in the password field. Type {SECRET_ADDRESS: "******"} in the address field'
