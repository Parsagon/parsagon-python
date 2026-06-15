from parsagon.executor import Executor


class MockDriver:
    def __init__(self, current_url, page_source):
        self.current_url = current_url
        self.page_source = page_source


class MockExecutor(Executor):
    def __init__(self, current_url, page_source):
        self.driver = MockDriver(current_url, page_source)
        self.max_elem_id = 0
        self.custom_functions = {}


def test_makes_links_absolute():
    executor = MockExecutor("https://example.com/", '<html><body><a href="/stuff">Stuff</a></body></html>')
    root = executor._get_cleaned_lxml_root()
    assert root[0][0].get("href") == "https://example.com/stuff"


def test_get_downloaded_file_uses_downloaded_files(tmp_path):
    executor = MockExecutor("https://example.com/", "<html></html>")
    download_dir = tmp_path / "downloaded_files"
    download_dir.mkdir()
    executor.download_dir = str(download_dir)
    pdf_file = download_dir / "file.pdf"
    pdf_file.write_text("pdf")

    assert executor.get_downloaded_file(set(), "https://example.com/file.pdf") == str(pdf_file)
