# parsagon

Parsagon allows you to create browser automations with natural language. You can create automations that fill out forms, scrape web pages, and much more, all without writing code. Here's a brief overview of how to get started:

## Requirements

To use Parsagon, you must have an up-to-date version of Google Chrome and Python >= 3.8

## Installation

To get started, install the Parsagon python package:

`pip install parsagon`

and set your API key as an environment variable:

`export PARSAGON_API_KEY=<YOUR API KEY>`

Please contact us to get your API key if you don't have it already.

## Usage

```
import parsagon

# Create a program
parsagon.create('Go to https://www.google.com/. Type "the meaning of life" into the search bar and hit enter. Scroll down and click the "More results" button 3 times. Scrape data in the format [{"title": "str", "link": "link"}].')

# Run a program
parsagon.run("My program")

# List your programs
parsagon.detail()
```

See [the docs](https://parsagon.io/docs/pipelines/overview) for more information.
