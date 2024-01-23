from collections import defaultdict
import copy
import json
import logging
from pathlib import Path
import psutil
import time
from urllib.parse import urljoin

import lxml.html
from pyvirtualdisplay import Display
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from webdriver_manager.chrome import ChromeDriverManager

from parsagon import settings
from parsagon.api import (
    get_interaction_element_id,
    get_schema_fields,
    get_cleaned_data,
    scrape_page,
    get_str_about_data,
    get_bool_about_data,
    get_json_about_data,
)
from parsagon.custom_function import CustomFunction
from parsagon.exceptions import ParsagonException
from parsagon.print import browser_print, input, Progress, ask, confirm
from parsagon.settings import get_resource_path

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
    "text_markdown": "TEXT",
    "markdown": "TEXT",
    "elem_id": "ACTION",
}


class Executor:
    """
    Executes code produced by GPT with the proper context.  Records custom_function usage along the way.
    """

    def __init__(self, task, headless=False, infer=False, use_uc=False, function_bank={}):
        self.task = task
        self.headless = headless
        self.function_bank = function_bank
        if self.headless:
            self.display = Display(visible=False, size=(1280, 1050)).start()
        driver_executable_path = ChromeDriverManager().install()
        if use_uc:
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument("--start-maximized")
            self.driver = uc.Chrome(driver_executable_path=driver_executable_path, options=chrome_options)
        else:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--start-maximized")
            self.driver = webdriver.Chrome(service=ChromeService(driver_executable_path), options=chrome_options)
        self.max_elem_ids = defaultdict(int)
        self.execution_context = {
            "custom_assert": self.custom_assert,
            "goto": self.goto,
            "close_window": self.close_window,
            "click_elem": self.click_elem,
            "click_elem_by_id": self.click_elem_by_id,
            "click_next_page": self.click_next_page,
            "fill_input": self.fill_input,
            "fill_input_by_id": self.fill_input_by_id,
            "select_option": self.select_option,
            "select_option_by_id": self.select_option_by_id,
            "scroll": self.scroll,
            "press_key": self.press_key,
            "join_text": self.join_text,
            "wait": self.wait,
            "get_inner_text": self.get_inner_text,
            "scrape_data": self.scrape_data,
            "get_str_about_data": get_str_about_data,
            "get_bool_about_data": get_bool_about_data,
            "get_json_about_data": get_json_about_data,
        }
        self.custom_functions = {}
        self.infer = infer

        highlights_path = get_resource_path() / "highlights.js"
        with highlights_path.open() as f:
            self.highlights_script = f.read()

    def add_custom_function(self, call_id, custom_function):
        if call_id in self.custom_functions:
            self.custom_functions[call_id].examples.extend(custom_function.examples)
        else:
            self.custom_functions[call_id] = custom_function

    def exec_custom_function(self, name, call_id, args_dict):
        code = self.function_bank[call_id]
        args_dict["call_id"] = call_id
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in args_dict.items())
        code = f"{code}\noutput = {name}{call_id}({args_str})"
        context = {"driver": self.driver, "PARSAGON_API_KEY": settings.get_api_key()}
        exec(code, context, context)
        return context["output"]

    def inject_highlights_script(self):
        self.driver.execute_script(self.highlights_script)

    def highlights_setup(self, field_type, max_examples="null"):
        self.driver.execute_script(f"window.currentFieldType = '{field_type}'; window.maxExamples = {max_examples};")

    def highlights_cleanup(self):
        self.driver.execute_script(f"window.currentFieldType = null; window.maxExamples = null; window.clearCSS();")

    def get_selected_node_ids(self, css_selector=None, xpath_selector=None):
        if css_selector:
            return [
                elem.get_attribute("data-psgn-id") for elem in self.driver.find_elements(By.CSS_SELECTOR, css_selector)
            ]
        elif xpath_selector:
            return [elem.get_attribute("data-psgn-id") for elem in self.driver.find_elements(By.XPATH, xpath_selector)]
        else:
            return [
                elem.get_attribute("data-psgn-id")
                for elem in self.driver.find_elements(By.CLASS_NAME, "parsagon-io-example-stored")
            ]

    def get_selected_node_and_descendant_ids(self):
        return self.driver.execute_script(
            "return Array.from(document.getElementsByClassName('parsagon-io-example-stored')).map((elem) => [elem, ...elem.querySelectorAll('*')]).flat().map((elem) => elem.getAttribute('data-psgn-id'))"
        )

    def mark_html(self):
        """
        Adds node IDs to elements on the current page that don't already have IDs.
        """
        max_elem_id = self.max_elem_ids[self.driver.current_window_handle]
        max_elem_id = self.driver.execute_script(
            f"let elemIdx = {max_elem_id}; "
            + "for (const node of document.all) { if (node.hasAttribute('data-psgn-id')) { continue; } node.setAttribute('data-psgn-id', elemIdx); elemIdx++; } return elemIdx;"
        )
        self.max_elem_ids[self.driver.current_window_handle] = max_elem_id
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
            elem.getparent().remove(elem)

        # Remove invisible elements
        id_to_elem = {}
        for elem in root.iter():
            elem_id = elem.get("data-psgn-id")
            if elem_id:
                id_to_elem[elem_id] = elem
        visible_elem_ids = set(
            driver.execute_script(
                "return Array.from(document.getElementsByTagName('*')).filter((elem) => { const style = getComputedStyle(elem); const rect = elem.getBoundingClientRect(); return style.opacity > 0.1 && style.display !== 'none' && style.visibility === 'visible' && elem.offsetWidth && elem.offsetHeight && elem.getClientRects().length && rect.right + window.scrollX >= 0 && rect.bottom + window.scrollY >= 0 }).map((elem) => elem.getAttribute('data-psgn-id'))"
            )
        )
        max_elem_id = self.max_elem_ids[self.driver.current_window_handle]
        with Progress() as progress:
            for elem_id in progress.track(range(max_elem_id), description="[green]Analyzing page"):
                elem_id = str(elem_id)
                is_visible = elem_id in visible_elem_ids
                if not is_visible:
                    try:
                        lxml_elem = root.xpath(f'//*[@data-psgn-id="{elem_id}"]')[0]
                        contains_visible = False
                        for descendant in lxml_elem.iterdescendants():
                            if descendant.get("data-psgn-id") in visible_elem_ids:
                                contains_visible = True
                                break
                        if contains_visible:
                            continue
                        parent = lxml_elem.getparent()
                        if parent is not None:
                            parent.remove(lxml_elem)
                    except IndexError:
                        continue
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
        while (
            user_input != "N/A"
            and not selected_node_ids
            and not user_input.startswith("XPATH:")
            and not user_input.startswith("CSS:")
        ):
            user_input = input('Please click an element or type "N/A": ')
            selected_node_ids = self.get_selected_node_ids()
        self.highlights_cleanup()
        if user_input == "N/A":
            return None, None, None, None

        css_selector = None
        xpath_selector = None
        if user_input.startswith("CSS:"):
            css_selector = user_input[4:].strip()
            selected_node_ids = self.get_selected_node_ids(css_selector=css_selector)
        elif user_input.startswith("XPATH:"):
            xpath_selector = user_input[6:].strip()
            selected_node_ids = self.get_selected_node_ids(xpath_selector=xpath_selector)

        elem_id = selected_node_ids[0] if selected_node_ids else None
        elem = self._id_to_elem(elem_id) if selected_node_ids else None
        return elem, elem_id, css_selector, xpath_selector

    def get_elem_by_description(self, description, elem_type):
        browser_print(f'Looking for {elem_type.lower()}: "{description}"')
        self.mark_html()
        visible_html = self.get_visible_html()
        elem_id = get_interaction_element_id(visible_html, description, self.task)
        if elem_id is None:
            raise ParsagonException(
                f'Could not find an element matching "{description}". Perhaps try rephrasing your prompt.'
            )
        elem = self._id_to_elem(elem_id)
        log_suffix = f' with text "{elem.text}"' if elem.text else ""
        browser_print(f"Found element" + log_suffix)
        return elem, elem_id, None, None

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
        browser_print(f"Going to {url}")
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
            browser_print("Clicked element")
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
        if call_id in self.function_bank:
            edit = confirm(f'Now clicking the element referred to by "{description}". Do you want to edit this step?')
            if not edit:
                return self.exec_custom_function(
                    "click_elem", call_id, {"description": description, "window_id": window_id}
                )
        elem, elem_id, css_selector, xpath_selector = self.get_elem(description, "BUTTON")
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
                    "css_selector": css_selector,
                    "xpath_selector": xpath_selector,
                }
            ],
        )
        self.add_custom_function(call_id, custom_function)
        return success

    def click_elem_by_id(self, elem_id, window_id):
        elem = self._id_to_elem(elem_id)
        return self._click_elem(elem, window_id)

    def click_next_page(self, description, window_id, call_id, wait=1):
        elem, elem_id, css_selector, xpath_selector = self.get_elem(description, "BUTTON")
        html = self.get_scrape_html()
        prev_html = self.driver.page_source
        success = self._click_elem(elem, window_id) if elem else False
        time.sleep(wait)
        custom_function = CustomFunction(
            "click_next_page",
            arguments={},
            examples=[
                {
                    "html": html,
                    "url": self.driver.current_url,
                    "elem_id": elem_id,
                    "xpath_selector": xpath_selector,
                }
            ],
        )
        self.add_custom_function(call_id, custom_function)
        return success and prev_html != self.driver.page_source

    def _select_option(self, elem, option, window_id):
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)

        for i in range(3):
            try:
                select_obj = Select(elem)
                select_obj.select_by_visible_text(option)
                browser_print(f'Selected option "{option}"')
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
        elem, elem_id, css_selector, xpath_selector = self.get_elem(description, "SELECT")
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
                    "css_selector": css_selector,
                    "xpath_selector": xpath_selector,
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
                browser_print(f'Typed "{text}" into element')
                if enter:
                    elem.send_keys(Keys.RETURN)
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
        elem, elem_id, css_selector, xpath_selector = self.get_elem(description, "INPUT")
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
                    "css_selector": css_selector,
                    "xpath_selector": xpath_selector,
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
        browser_print(f"Scrolling {x * 100}% to the left and {y * 100}% down")
        self.driver.execute_script(
            f"window.scrollTo({{top: document.documentElement.scrollHeight * {y}, left: document.documentElement.scrollWidth * {x}, behavior: 'smooth'}});"
        )
        time.sleep(1)
        self.mark_html()

    def press_key(self, key, window_id):
        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)
        browser_print(f"Pressing {key}")
        ActionChains(self.driver).send_keys(getattr(Keys, key)).perform()
        time.sleep(1)

    def join_text(strings):
        return "\\n\\n".join(strings)

    def wait(self, seconds):
        browser_print(f"Waiting {seconds} seconds...")
        time.sleep(seconds)
        self.mark_html()
        self.inject_highlights_script()

    def get_inner_text(self, window_id):
        return self.driver.execute_script("return document.body.innerText;")

    def scrape_data(self, schema, window_id, call_id):
        """
        Scrapes data from the current page.
        """
        if call_id in self.function_bank:
            edit = confirm(f"Now scraping data in the format {schema}. Do you want to edit this step?")
            if not edit:
                return self.exec_custom_function("scrape_data", call_id, {"schema": schema, "window_id": window_id})

        if self.driver.current_window_handle != window_id:
            self.driver.switch_to.window(window_id)

        browser_print(f"Now collecting data in the format {schema}")

        self.mark_html()
        html = self.get_scrape_html()
        nodes = {}
        css_selectors = {}
        xpath_selectors = {}
        if not self.infer:
            field_types = get_schema_fields(schema)
            for field, field_type in field_types.items():
                self.highlights_setup(ELEMENT_TYPES[field_type])
                field_repr = field.replace("dataset0|", "").replace("|", " / ")
                field_input = ask(
                    f"Click elements containing data for the field `{field_repr}`. Hit TAB to autocomplete or DELETE/BACKSPACE to clear selections. Hit ENTER when done"
                )
                if field_input.startswith("CSS:"):
                    css_selector = field_input[4:].strip()
                    nodes[field] = [[node_id] for node_id in self.get_selected_node_ids(css_selector=css_selector)]
                    css_selectors[field] = css_selector
                elif field_input.startswith("XPATH:"):
                    xpath_selector = field_input[6:].strip()
                    nodes[field] = [[node_id] for node_id in self.get_selected_node_ids(xpath_selector=xpath_selector)]
                    xpath_selectors[field] = xpath_selector
                else:
                    nodes[field] = [[node_id] for node_id in self.get_selected_node_ids()]
                self.highlights_cleanup()
            browser_print("Scraping data...")
            result = get_cleaned_data(html, schema, nodes)
            scraped_data = result["data"]
        else:
            browser_print("Scraping data...")
            result = scrape_page(self.get_visible_html(), schema, self.task, html)
            scraped_data = result["data"]
            nodes = result["nodes"]
            if not scraped_data or not nodes:
                raise ParsagonException(
                    f"Parsagon could not find any data on the page that would fit the format {schema}. You can try rephrasing your prompt, or you can run Parsagon in manual mode to click on elements you want to scrape."
                )
        browser_print(f"Scraped data:\n{scraped_data}")

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
                    "css_selectors": css_selectors,
                    "xpath_selectors": xpath_selectors,
                    "scraped_data": copy.deepcopy(scraped_data),
                }
            ],
        )
        self.add_custom_function(call_id, custom_function)
        return scraped_data

    def execute(self, code):
        loc = {}
        try:
            exec(code, self.execution_context, loc)
            browser_print(f"Program finished and returned a value of:\n{loc['output']}\n")
        finally:
            self.quit()

    def quit(self):
        self.driver.quit()
        for proc in psutil.process_iter():
            try:
                if proc.name() == "chromedriver":
                    proc.kill()
            except psutil.NoSuchProcess:
                continue
        if self.headless:
            self.display.stop()
