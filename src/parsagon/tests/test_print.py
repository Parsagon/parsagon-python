from parsagon.print import ask


def test_non_gui_ask_allows_choices(mocker):
    mocker.patch("parsagon.print.Prompt.ask")
    ask("a question", choices=["answer1", "answer2"], show_choices=False)
