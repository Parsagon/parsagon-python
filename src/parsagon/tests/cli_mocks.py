from parsagon.main import main


def call_cli(mocker, args):
    """
    Uses the mocker to pretend that the args passed are coming from argparse, then calls the main function.
    """

    mocker.patch(
        "parsagon.main.get_args",
        lambda: (
            args,
            None,
        ),
    )
    return main()
