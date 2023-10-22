# parsagon

Parsagon allows you to create browser automations with natural language. You can create automations that fill out forms, scrape web pages, and much more, all without writing code. Here's a brief overview of how to get started:

## Requirements

To use Parsagon, you must have an up-to-date version of Google Chrome and Python >= 3.8

## Installation

To get started, install the Parsagon python package:

`pip install parsagon`

Then run

`parsagon setup`

and copy-paste your API key when prompted.

You can view your API key by logging in and going to <https://parsagon.io/settings>

## Usage

From command line:

```
# Create a program
parsagon create

# Run a program
parsagon run 'My program'

# List your programs
parsagon detail

# Delete a program
parsagon delete 'My program'
```

From Python:
```
import parsagon

# Create a program
parsagon.create('Go to https://www.google.com/. Type "the meaning of life" into the search bar and hit enter. Scroll down and click the "More results" button 3 times. Scrape data in the format [{"search result title": "str", "link": "link"}].')

# Run a program
parsagon.run("My program")

# Run a program multiple times
parsagon.batch_runs("My batch name", "My program", runs=[{"variable_name": "value1"}, {"variable_name": "value2"}, ...])

# List your programs
parsagon.detail()

# Delete a program
parsagon.delete("My program")
```

See [the docs](https://parsagon.io/docs/pipelines/overview) for more information.
