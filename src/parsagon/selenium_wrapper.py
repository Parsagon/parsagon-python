import logging
import time
from tkinter.tix import Select

import lxml.html
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class SeleniumWrapper:
    """
    Wrapper around Selenium WebDriver.
    """

    class Interaction:
        """
        Single use: Used when interacting with the loaded page - ensures proper actions are taken before and after the interaction.  If the webpage is modified and new elements appear that are not marked, but then an exception is raised, this will ensure that the webpage is re-marked all the same.
        """

        def __init__(self, wrapper):
            self.wrapper = wrapper

        def __enter__(self):
            """
            Call before interaction. Goes to last window.
            """
            driver = self.wrapper.driver
            driver.switch_to.window(driver.window_handles[-1])

        def __exit__(self, exc_type, exc_value, exc_traceback):
            """
            Called after interaction.  Marks the HTML. Rethrows any exceptions.
            """
            self.wrapper.mark_html()
            self.wrapper = None  # Avoid circular reference?

    def __init__(self, headless: bool = False) -> None:
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        else:
            chrome_options.add_argument("--start-maximized")

        self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
        self.max_elem_id = 0

    def __del__(self) -> None:
        self.driver.close()

    def mark_html(self):
        """
        Adds node IDs to elements on the current page that don't already have IDs.
        """
        new_max_elem_id = self.driver.execute_script(
            f"let elemIdx = {self.max_elem_id}; for (const node of document.querySelectorAll(':not([data-psgn-id]):not(style)')) {{ node.setAttribute('data-psgn-id', elemIdx); elemIdx++; }} return elemIdx;"
        )
        self.max_elem_id = new_max_elem_id

    def get_visible_html(self):
        """
        Returns cleaned html from the driver, hiding all elements that are not visible.
        Script, noscript, style, and head elements are removed.
        All elements must have node IDs added as data attributes.
        """

        driver = self.driver

        html = driver.page_source
        assert "data-psgn-id" in html

        parser = lxml.html.HTMLParser(remove_comments=True, remove_pis=True)
        root = lxml.html.fromstring(html, parser=parser)
        for elem in root.iterfind(".//script"):
            elem.text = ""
        for elem in root.iterfind(".//noscript"):
            elem.text = ""
        for elem in root.iterfind(".//style"):
            elem.text = ""
        for elem in root.iterfind(".//head"):
            elem.text = ""
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

    def goto(self, url: str):

        # Go to website
        self.driver.switch_to.window(self.driver.window_handles[-1])
        self.driver.get(url)

        # Wait for website to load
        self.wait(5)

    def wait(self, seconds):
        time.sleep(seconds)

    def get_elem(self, elem_id: int):
        """
        Gets a selenium element by Parsagon ID (psgn-id).
        """
        return self.driver.find_element(By.XPATH, f'//*[@data-psgn-id="{elem_id}"]')

    def click_button(self, elem):
        """
        Clicks a button.
        """
        elem = self._convert_elem(elem)
        elem.click()

    def select_option(self, elem, option_name):
        """
        Selects an option by name from a dropdown.
        """
        elem = self._convert_elem(elem)
        select_obj = Select(elem)
        select_obj.select_by_visible_text(option_name)

    def fill_input(self, elem, text, end_key=None):
        """
        Fills an input text field, then presses an optional end key.
        """
        elem = self._convert_elem(elem)
        elem.clear()
        elem.send_keys(text)
        end_key = end_key.upper()
        if end_key == "RETURN":
            elem.send_keys(Keys.RETURN)
        elif end_key == "NONE" or end_key is None:
            pass
        else:
            raise RuntimeError("Invalid end key: " + end_key)

    def _convert_elem(self, elem):
        """
        Helper to convert an "elem" argument to one of the methods above to a Selenium element.
        """
        result = elem
        if isinstance(elem, int):
            result = self.get_elem(elem)
        return result
