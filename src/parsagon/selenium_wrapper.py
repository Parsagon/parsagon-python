import logging
import time

import lxml.html
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class SeleniumWrapper:
    """
    Convenience wrapper around Selenium WebDriver for managing data-psgn-id and providing other HTML/Selenium utilities.  Doesn't use AI.
    """

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

    def switch_to_last_window(self):
        driver = self.driver
        driver.switch_to.window(driver.window_handles[-1])

    def mark_html(self):
        """
        Adds node IDs to elements on the current page that don't already have IDs.
        """
        new_max_elem_id = self.driver.execute_script(
            f"let elemIdx = {self.max_elem_id}; for (const node of document.querySelectorAll(':not([data-psgn-id]):not(style)')) {{ node.setAttribute('data-psgn-id', elemIdx); elemIdx++; }} return elemIdx;"
        )
        self.max_elem_id = new_max_elem_id

    def _get_cleaned_lxml_root(self):
        driver = self.driver
        html = driver.page_source

        parser = lxml.html.HTMLParser(remove_comments=True, remove_pis=True)
        root = lxml.html.fromstring(html, parser=parser)
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

    def wait(self, seconds):
        time.sleep(seconds)

    def perform_interaction(self, interaction_type, elem_id, *args, **kwargs):
        interaction_fn = {
            "click_elem": self._click_elem,
            "fill_input": self._fill_input,
            "select_option": self._select_option,
        }[interaction_type]
        self.switch_to_last_window()
        interaction_fn(elem_id, *args, **kwargs)

    def _get_elem(self, elem_id: int):
        """
        Gets a selenium element by Parsagon ID (psgn-id).
        """
        return self.driver.find_element(By.XPATH, f'//*[@data-psgn-id="{elem_id}"]')

    # IMPORTANT: Do not change the names of arguments to the functions below without also changing the prompt to GPT in the backend - GPT must know the argument names.
    def goto(self, url: str):

        # Go to website
        self.switch_to_last_window()
        self.driver.get(url)

        # Wait for website to load
        self.wait(5)

    def _click_elem(self, elem_id):
        """
        Clicks a button.
        """
        elem = self._get_elem(elem_id)
        elem.click()

    def _select_option(self, elem_id, option):
        """
        Selects an option by name from a dropdown.
        """
        elem = self._get_elem(elem_id)
        select_obj = Select(elem)
        select_obj.select_by_visible_text(option)

    def _fill_input(self, elem_id, text, enter=False):
        """
        Fills an input text field, then presses an optional end key.
        """
        elem = self._get_elem(elem_id)
        elem.clear()
        elem.send_keys(text)
        if enter:
            elem.send_keys(Keys.RETURN)

    # (End of functions with controlled argument names)
