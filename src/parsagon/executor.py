import copy
import json
import logging
from pathlib import Path
import time
from urllib.parse import urljoin

import lxml.html
from pyvirtualdisplay import Display
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from webdriver_manager.chrome import ChromeDriverManager

from parsagon.api import (
    get_interaction_element_id,
    get_schema_fields,
    get_cleaned_data,
    scrape_page,
    get_str_about_data,
    get_bool_about_data,
)
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


# A dict of schema types to element types
ELEMENT_TYPES = {
    "str": "TEXT",
    "num": "TEXT",
    "link": "URL",
    "image": "IMAGE",
    "html": "HTML",
    "element": "ACTION",
    "textarea": "TEXT",
    "markdown": "TEXT",
    "elem_id": "ACTION",
}


class Executor:
    """
    Executes code produced by GPT with the proper context.  Records custom_function usage along the way.
    """

    def __init__(self, headless=False, infer=False):
        self.headless = headless
        if self.headless:
            self.display = Display(visible=False, size=(1280, 1050)).start()
        chrome_options = uc.ChromeOptions()
        chrome_options.add_argument("--start-maximized")
        driver_exec_path = ChromeDriverManager().install()
        self.driver = uc.Chrome(driver_executable_path=driver_exec_path, options=chrome_options)
        self.max_elem_id = 0
        self.execution_context = {
            "custom_assert": self.custom_assert,
            "goto": self.goto,
            "close_window": self.close_window,
            "click_elem": self.click_elem,
            "click_elem_by_id": self.click_elem_by_id,
            "fill_input": self.fill_input,
            "fill_input_by_id": self.fill_input_by_id,
            "select_option": self.select_option,
            "select_option_by_id": self.select_option_by_id,
            "scroll": self.scroll,
            "press_key": self.press_key,
            "wait": self.wait,
            "scrape_data": self.scrape_data,
            "get_str_about_data": get_str_about_data,
            "get_bool_about_data": get_bool_about_data,
        }
        logger.debug("Available functions: %s", ", ".join(self.execution_context.keys()))
        self.custom_functions = {}
        self.infer = infer

        highlights_path = Path(__file__).parent / "highlights.js"
        with highlights_path.open() as f:
            self.highlights_script = f.read()

    def add_custom_function(self, call_id, custom_function):
        if call_id in self.custom_functions:
            self.custom_functions[call_id].examples.extend(custom_function.examples)
        else:
            self.custom_functions[call_id] = custom_function

    def inject_highlights_script(self):
        self.driver.execute_script(self.highlights_script)

    def highlights_setup(self, field_type, max_examples="null"):
        self.driver.execute_script(f"window.currentFieldType = '{field_type}'; window.maxExamples = {max_examples};")

    def highlights_cleanup(self):
        self.driver.execute_script(f"window.currentFieldType = null; window.maxExamples = null; window.clearCSS();")

    def get_selected_node_ids(self):
        return self.driver.execute_script(
            "return Array.from(document.getElementsByClassName('parsagon-io-example-stored')).map((elem) => elem.getAttribute('data-psgn-id'))"
        )

    def get_selected_node_and_descendant_ids(self):
        return self.driver.execute_script(
            "return Array.from(document.getElementsByClassName('parsagon-io-example-stored')).map((elem) => [elem, ...elem.querySelectorAll('*')]).flat().map((elem) => elem.getAttribute('data-psgn-id'))"
        )

    def mark_html(self):
        """
        Adds node IDs to elements on the current page that don't already have IDs.
        """
        logger.debug("  Marking HTML...")
        self.max_elem_id = self.driver.execute_script(
            "let elemIdx = 0; for (const node of document.all) { elemIdx = Math.max(elemIdx, parseInt(node.getAttribute('data-psgn-id') ?? 0)); } return elemIdx"
        )
        self.max_elem_id = self.driver.execute_script(
            f"let elemIdx = {self.max_elem_id}; "
            + "for (const node of document.all) { if (node.hasAttribute('data-psgn-id')) { continue; } node.setAttribute('data-psgn-id', elemIdx); elemIdx++; } return elemIdx;"
        )
        self.driver.execute_script(
            "for (const image of document.images) { image.setAttribute('data-psgn-width', image.parentElement.offsetWidth ?? -1); image.setAttribute('data-psgn-height', image.parentElement.offsetHeight ?? -1); }"
        )

    def _get_cleaned_lxml_root(self):
        parser = lxml.html.HTMLParser(remove_comments=True, remove_pis=True)
        root = lxml.html.fromstring(self.driver.page_source.replace("&nbsp;", " "), parser=parser)

        # make links absolute
        root.make_links_absolute(self.driver.current_url)
        for elem in root.xpath("//img[@srcset]"):
            srcset_list = []
            for s in elem.get("srcset").split(","):
                parts = s.strip().split()
                if not parts:
                    continue
                parts[0] = urljoin(self.driver.current_url, parts[0])
                srcset_list.append(" ".join(parts))
            elem.set("srcset", ", ".join(srcset_list))

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

    def get_elem(self, description, elem_type):
        if self.infer:
            return self.get_elem_by_description(description, elem_type)
        self.highlights_setup("ACTION", max_examples=1)
        user_input = input(
            f'Click the element referred to by "{description}". Hit ENTER to confirm your selection, or type "N/A" if the element does not exist: '
        )
        self.mark_html()
        selected_node_ids = self.get_selected_node_ids()
        while user_input != "N/A" and not selected_node_ids:
            user_input = input('Please click an element or type "N/A": ')
            selected_node_ids = self.get_selected_node_ids()
        self.highlights_cleanup()
        if user_input == "N/A":
            return None, None
        else:
            elem_id = selected_node_ids[0]
            elem = self._id_to_elem(elem_id)
        return elem, elem_id

    def get_elem_by_description(self, description, elem_type):
        logger.info(f'Looking for {elem_type.lower()}: "{description}"')
        visible_html = self.get_visible_html()
        elem_id = get_interaction_element_id(visible_html, elem_type, description)
        if elem_id is None:
            raise ParsagonException(
                f'Could not find an element matching "{description}". Perhaps try rephrasing your prompt.'
            )
        elem = self._id_to_elem(elem_id)
        log_suffix = f' with text "{elem.text}"' if elem.text else ""
        logger.info(f"Found element" + log_suffix)
        return elem, elem_id

    def _id_to_elem(self, elem_id):
        """
        Gets a selenium element by Parsagon ID (psgn-id).
        """
        assert elem_id is not None
        result = self.driver.find_element(By.XPATH, f'//*[@data-psgn-id="{elem_id}"]')
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
        time.sleep(2)
        self.mark_html()
        self.inject_highlights_script()

        return self.driver.current_window_handle

    def close_window(self, window_id):
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[-1])

    def _click_elem(self, elem, window_id):
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)

        try:
            self.driver.execute_script("arguments[0].click();", elem)
            logger.info("Clicked element")
            time.sleep(2)
        except Exception as e:
            return False
        self.mark_html()
        self.inject_highlights_script()
        return True

    def click_elem(self, description, window_id, call_id):
        """
        Clicks a button using its description.
        """
        elem, elem_id = self.get_elem(description, "BUTTON")
        html = self.get_scrape_html()
        success = self._click_elem(elem, window_id) if elem else False
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
        return success

    def click_elem_by_id(self, elem_id, window_id):
        elem = self._id_to_elem(elem_id)
        return self._click_elem(elem, window_id)

    def _select_option(self, elem, option, window_id):
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)

        for i in range(3):
            try:
                select_obj = Select(elem)
                select_obj.select_by_visible_text(option)
                logger.info(f'Selected option "{option}"')
                time.sleep(2)
                break
            except:
                time.sleep(2)
        else:
            return False
        self.mark_html()
        self.inject_highlights_script()
        return True

    def select_option(self, description, option, window_id, call_id):
        """
        Selects an option by name from a dropdown using its description.
        """
        elem, elem_id = self.get_elem(description, "SELECT")
        html = self.get_scrape_html()
        success = self._select_option(elem, option, window_id) if elem else False
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
        return success

    def select_option_by_id(self, elem_id, option, window_id):
        elem = self._id_to_elem(elem_id)
        return self._select_option(elem, option, window_id)

    def _fill_input(self, elem, text, enter, window_id):
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)

        for i in range(3):
            try:
                elem.clear()
                elem.send_keys(text)
                logger.info(f'Typed "{text}" into element')
                if enter:
                    elem.send_keys(Keys.RETURN)
                    logger.debug("Pressed enter")
                time.sleep(2)
                break
            except:
                time.sleep(2)
        else:
            return False
        self.mark_html()
        self.inject_highlights_script()
        return True

    def fill_input(self, description, text, enter, window_id, call_id):
        """
        Fills an input text field, then presses an optional end key using its description.
        """
        elem, elem_id = self.get_elem(description, "INPUT")
        html = self.get_scrape_html()
        success = self._fill_input(elem, text, enter, window_id) if elem else False
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
        return success

    def fill_input_by_id(self, elem_id, text, enter, window_id):
        elem = self._id_to_elem(elem_id)
        return self._fill_input(elem, text, enter, window_id)

    def scroll(self, x, y, window_id):
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)
        logger.info(f"Scrolling {x * 100}% to the left and {y * 100}% down")
        self.driver.execute_script(
            f"window.scrollTo({{top: document.documentElement.scrollHeight * {y}, left: document.documentElement.scrollWidth * {x}, behavior: 'smooth'}});"
        )
        time.sleep(1)

    def press_key(self, key, window_id):
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)
        logger.info(f"Pressing {key}")
        ActionChains(self.driver).send_keys(getattr(Keys, key)).perform()
        time.sleep(1)

    def wait(self, seconds):
        logger.info(f"Waiting {seconds} seconds...")
        time.sleep(seconds)
        self.mark_html()
        self.inject_highlights_script()

    def scrape_data(self, schema, window_id, call_id):
        """
        Scrapes data from the current page.
        """
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)

        if self.infer:
            user_input = "INFER"
        else:
            user_input = input(
                f'Now determining what elements to scrape to collect data in the format {schema}. Hit ENTER to continue by clicking on the elements to scrape, or type a valid command: '
            )
            while user_input not in ("", "INFER"):
                user_input = input('Hit ENTER or type "INFER": ')

        self.mark_html()
        html = self.get_scrape_html()
        if user_input == "":
            nodes = {}
            field_types = get_schema_fields(schema)
            for field, field_type in field_types.items():
                if not isinstance(field_type, str):
                    continue
                self.highlights_setup(ELEMENT_TYPES[field_type])
                field_repr = field.replace("dataset0|", "").replace("|", " / ")
                input(
                    f"Click elements containing data for the field `{field_repr}`. Hit TAB to autocomplete or DELETE/BACKSPACE to clear selections. Hit ENTER when done: "
                )
                nodes[field] = [[node_id] for node_id in self.get_selected_node_ids()]
                self.highlights_cleanup()
            logger.info("Scraping data...")
            result = get_cleaned_data(html, schema, nodes)
            scraped_data = result["data"]
        else:
            self.highlights_setup("ACTION")
            input(f"Click on the element(s) from which data should be inferred. Hit ENTER when done: ")
            relevant_elem_ids = self.get_selected_node_and_descendant_ids()
            self.highlights_cleanup()
            logger.info("Scraping data...")
            result = scrape_page(html, schema, relevant_elem_ids)
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
                    "html": html,
                    "url": self.driver.current_url,
                    "nodes": nodes,
                    "scraped_data": copy.deepcopy(scraped_data),
                }
            ],
        )
        self.add_custom_function(call_id, custom_function)
        return scraped_data

    def execute(self, code):
        try:
            exec(code, self.execution_context)
        finally:
            self.driver.quit()
            if self.headless:
                self.display.stop()
