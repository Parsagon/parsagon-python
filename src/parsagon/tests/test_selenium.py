from src.parsagon.browser import SeleniumWrapper


def test_selenium():
    wrapper = SeleniumWrapper()
    wrapper.goto("https://gabemontague.com/example/")
    wrapper.wait()
