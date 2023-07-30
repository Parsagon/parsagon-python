import json
import logging
import time
from urllib.parse import urljoin

import lxml.html
from pyvirtualdisplay import Display
from selenium import webdriver
import seleniumwire.undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select

from parsagon.api import get_interaction_element_id, scrape_page
from parsagon.custom_function import CustomFunction
from parsagon.exceptions import ParsagonException

logger = logging.getLogger(__name__)


# A dictionary of custom function names to their descriptions for the user
custom_functions_to_descriptions = {
    "scrape_data": "scrape data from the page",
    "goto": "go to a page",
    "click_elem": "click an element",
    "fill_input": "fill an input",
    "select_option": "select an option",
}


class Executor:
    """
    Executes code produced by GPT with the proper context.  Records custom_function usage along the way.
    """

    def __init__(self, headless=False):
        self.headless = headless
        if self.headless:
            self.display = Display(visible=False, size=(1280, 1050)).start()
        chrome_options = uc.ChromeOptions()
        chrome_options.add_argument("--start-maximized")
        seleniumwire_options = {"disable_capture": True}
        self.driver = uc.Chrome(options=chrome_options, seleniumwire_options=seleniumwire_options)
        self.max_elem_id = 0
        self.execution_context = {
            "custom_assert": self.custom_assert,
            "goto": self.goto,
            "click_elem": self.click_elem,
            "fill_input": self.fill_input,
            "select_option": self.select_option,
            "scroll": self.scroll,
            "wait": self.wait,
            "scrape_data": self.scrape_data,
        }
        logger.debug("Available functions: %s", ", ".join(self.execution_context.keys()))
        self.custom_functions = {}

    def add_custom_function(self, call_id, custom_function):
        if call_id in self.custom_functions:
            self.custom_functions[call_id].examples.extend(custom_function.examples)
        else:
            self.custom_functions[call_id] = custom_function

    def mark_html(self):
        """
        Adds node IDs to elements on the current page that don't already have IDs.
        """
        logger.debug("  Marking HTML...")
        self.max_elem_id = self.driver.execute_script(
            "let elemIdx = 0; for (const node of document.all) { node.setAttribute('data-psgn-id', elemIdx); elemIdx++; } return elemIdx;"
        )
        self.driver.execute_script(
            "for (const image of document.images) { image.setAttribute('data-psgn-width', image.width ?? -1); image.setAttribute('data-psgn-height', image.height ?? -1); }"
        )

    def _get_cleaned_lxml_root(self):
        parser = lxml.html.HTMLParser(remove_comments=True, remove_pis=True)
        root = lxml.html.fromstring(self.driver.page_source.replace('&nbsp;', ' '), parser=parser)

        # make links absolute
        root.make_links_absolute(self.driver.current_url)
        for elem in root.xpath('//img[@srcset]'):
            srcset_list = []
            for s in elem.get('srcset').split(','):
                parts = s.strip().split()
                if not parts:
                    continue
                parts[0] = urljoin(self.driver.current_url, parts[0])
                srcset_list.append(' '.join(parts))
            elem.set('srcset', ', '.join(srcset_list))

        # remove unnecessary and bulky elements
        for elem in root.iterfind(".//script"):
            elem.text = ""
        for elem in root.iterfind(".//noscript"):
            elem.text = ""
        for elem in root.iterfind(".//style"):
            elem.text = ""
        return root

    def get_scrape_html(self):
        """
        Returns cleaned html from the driver with script, noscript, and style elements removed, designed to preserve scrapable data.
        """
        root = self._get_cleaned_lxml_root()
        return lxml.html.tostring(root).decode()

    def get_visible_html(self):
        """
        Returns cleaned html from the driver, hiding all elements that are not visible.
        Script, noscript, style, and head elements are removed.
        All elements must have node IDs added as data attributes.
        """

        driver = self.driver
        assert "data-psgn-id" in driver.page_source
        root = self._get_cleaned_lxml_root()

        # Remove head elements
        for elem in root.iterfind(".//head"):
            elem.text = ""

        # Remove invisible elements
        for elem_id in range(self.max_elem_id):
            try:
                lxml_elem = root.xpath(f'//*[@data-psgn-id="{elem_id}"]')[0]
                selenium_elem = driver.find_elements(By.XPATH, f'//*[@data-psgn-id="{elem_id}"]')[0]
            except IndexError:
                continue
            if not selenium_elem.is_displayed():
                parent = lxml_elem.getparent()
                if parent is not None:
                    parent.remove(lxml_elem)

        return lxml.html.tostring(root).decode()

    def get_elem_by_description(self, elem_type, description):
        logger.info(f'Looking for {elem_type.lower()}: "{description}"')
        visible_html = self.get_visible_html()
        elem_id = get_interaction_element_id(visible_html, elem_type, description)
        if elem_id is None:
            raise ParsagonException(
                f'Could not find an element matching "{description}". Perhaps try rephrasing your prompt.'
            )
        return elem_id

    def _get_elem(self, elem_id):
        """
        Gets a selenium element by Parsagon ID (psgn-id).
        """
        assert elem_id is not None
        result = self.driver.find_element(By.XPATH, f'//*[@data-psgn-id="{elem_id}"]')
        elem_text = result.text
        log_suffix = f' with text "{elem_text}"' if elem_text else ""
        logger.info(f"Found element" + log_suffix)
        return result

    def custom_assert(self, v):
        assert v, "Web page interaction failed."

    def goto(self, url, window_id=None):
        if window_id in self.driver.window_handles:
            self.driver.switch_to.window(window_id)
        else:
            self.driver.switch_to.new_window("tab")

        # Go to website
        logger.info(f"Going to {url}")
        self.driver.get(url)

        # Wait for website to load
        time.sleep(5)
        self.mark_html()

        return self.driver.current_window_handle

    def click_elem(self, description, window_id, call_id):
        """
        Clicks a button.
        """
        html = self.get_scrape_html()
        elem_id = self.get_elem_by_description("BUTTON", description)
        self.driver.switch_to.window(window_id)
        elem = self._get_elem(elem_id)
        for i in range(3):
            try:
                elem.click()
                logger.info("Clicked element")
                time.sleep(5)
                break
            except Exception as e:
                time.sleep(5)
        else:
            return False
        self.mark_html()
        custom_function = CustomFunction(
            "click_elem",
            arguments={},
            examples=[
                {
                    "html": html,
                    "url": self.driver.current_url,
                    "elem_id": elem_id,
                }
            ],
        )
        self.add_custom_function(call_id, custom_function)
        return True

    def select_option(self, description, option, window_id, call_id):
        """
        Selects an option by name from a dropdown.
        """
        html = self.get_scrape_html()
        elem_id = self.get_elem_by_description("SELECT", description)
        elem = self._get_elem(elem_id)
        for i in range(3):
            try:
                select_obj = Select(elem)
                select_obj.select_by_visible_text(option)
                logger.info(f'Selected option "{option}"')
                time.sleep(5)
                break
            except:
                time.sleep(5)
        else:
            return False
        self.mark_html()
        custom_function = CustomFunction(
            "select_option",
            arguments={
                "option": option,
            },
            examples=[
                {
                    "html": html,
                    "url": self.driver.current_url,
                    "elem_id": elem_id,
                }
            ],
        )
        self.add_custom_function(call_id, custom_function)
        return True

    def fill_input(self, description, text, enter, window_id, call_id):
        """
        Fills an input text field, then presses an optional end key.
        """
        html = self.get_scrape_html()
        elem_id = self.get_elem_by_description("INPUT", description)
        elem = self._get_elem(elem_id)
        for i in range(3):
            try:
                elem.clear()
                elem.send_keys(text)
                logger.info(f'Typed "{text}" into element')
                if enter:
                    elem.send_keys(Keys.RETURN)
                    logger.debug("Pressed enter")
                time.sleep(5)
                break
            except:
                time.sleep(5)
        else:
            return False
        self.mark_html()
        custom_function = CustomFunction(
            "fill_input",
            arguments={
                "text": text,
                "enter": enter,
            },
            examples=[
                {
                    "html": html,
                    "url": self.driver.current_url,
                    "elem_id": elem_id,
                }
            ],
        )
        self.add_custom_function(call_id, custom_function)
        return True

    def scroll(self, x, y, window_id):
        self.driver.switch_to.window(window_id)
        logger.info(f"Scrolling {x * 100}% to the left and {y * 100}% down")
        self.driver.execute_script(
            f"window.scrollTo({{top: document.documentElement.scrollHeight * {y}, left: document.documentElement.scrollWidth * {x}, behavior: 'smooth'}});"
        )
        time.sleep(1)

    def wait(self, seconds):
        logger.info(f"Waiting {seconds} seconds...")
        time.sleep(seconds)
        self.mark_html()

    def scrape_data(self, schema, window_id, call_id):
        """
        Scrapes data from the current page.
        """
        self.driver.switch_to.window(window_id)
        logger.info("Scraping data...")
        html = self.get_scrape_html()
        result = scrape_page(html, schema)
        scraped_data = result["data"]
        nodes = result["nodes"]
        if not scraped_data and not nodes:
            raise ParsagonException(
                f"Parsagon could not find any data on the page that would fit the format {schema}. Perhaps try rephrasing your prompt."
            )
        elif not nodes:
            raise ParsagonException(
                f"Parsagon found the following data on the page for the format {schema}:\n\n{scraped_data}\n\nHowever, it could not find a plausible program to scrape this data. If the data above is incorrect, perhaps try rephrasing your prompt."
            )
        logger.info(f"Scraped data:\n{scraped_data}")
        custom_function = CustomFunction(
            "scrape_data",
            arguments={
                "schema": schema,
            },
            examples=[
                {
                    "html": self.get_scrape_html(),
                    "url": self.driver.current_url,
                    "nodes": nodes,
                    "scraped_data": scraped_data,
                }
            ],
        )
        self.add_custom_function(call_id, custom_function)
        return result["data"]

    def execute(self, code):
        try:
            exec(code, self.execution_context)
        finally:
            self.driver.quit()
            if self.headless:
                self.display.stop()
