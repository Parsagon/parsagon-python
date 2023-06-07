import logging
from functools import partial

from src.parsagon.api import get_interaction_element_id, scrape_page
from src.parsagon.selenium_wrapper import SeleniumWrapper
from selenium.common.exceptions import ElementNotInteractableException

logger = logging.getLogger(__name__)

"""
    goto(url: str): Go to a URL
    click_elem(description: str): Click an element by giving a short description of it
    fill_input(description: str, text: str, enter: bool): Type text into an input element by giving a short description of the element, the text to type, and whether to hit enter after typing the text
    select_option(description: str, option: str): Select an option from a dropdown by giving a short description of the dropdown and giving the text of the option
    scrape_data(schema: dict or list): Scrape data from the current page. The data will have the format, field names, and data types of the given data schema
    """


class Executor:
    """
    Executes code produced by GPT with the proper context.
    """

    def __init__(self, selenium_wrapper):
        self.selenium_wrapper: SeleniumWrapper = selenium_wrapper
        self.execution_context = {
            "goto": selenium_wrapper.goto,
            "click_elem": partial(self.element_interaction, "click_elem"),
            "fill_input": partial(self.element_interaction, "fill_input"),
            "select_option": partial(self.element_interaction, "select_option"),
            "scrape_data": self.scrape_data,
        }

        # Wrap all functions with the custom call wrapper
        for k in self.execution_context:
            self.execution_context[k] = self.wrap_custom_call(self.execution_context[k])

    def wrap_custom_call(self, fn):
        """
        Modifies the function to remove the call_id argument.
        """

        def extract_call_id(*args, **kwargs):
            call_id = kwargs.pop("call_id")
            logger.info(f"Executing call {call_id}...")
            logger.debug(fn)
            return fn(*args, **kwargs)

        return extract_call_id

    def element_interaction(self, interaction_type, description, *args, **kwargs):
        """
        Interacts with an element described in natural language in description, using the interaction type, arguments, and keyword arguments.
        """

        # Mark the HTML so we have Parsagon IDs
        self.selenium_wrapper.mark_html()
        visible_html = self.selenium_wrapper.get_visible_html()

        # Get the Parsagon ID of the element using AI
        elem_type = {
            "click_elem": "BUTTON",
            "fill_input": "INPUT",
            "select_option": "SELECT",
        }[interaction_type]
        elem_id = get_interaction_element_id(visible_html, elem_type, description)
        assert elem_id is not None and isinstance(elem_id, int)

        # Perform the interaction
        self.selenium_wrapper.perform_interaction(interaction_type, elem_id, *args, **kwargs)

    def scrape_data(self, schema):
        """
        Scrapes data from the current page.
        """
        html = self.selenium_wrapper.get_scrape_html()
        result = scrape_page(html, schema)
        print(result)
        return result

    def execute(self, code):
        exec(code, self.execution_context)
