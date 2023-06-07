# parsagon-autogpt

## Setup
- Create a new venv
- Activate the environment
- `pip3 install -r requirements.txt`

## Running
- Set environment variables:
  - `API_BASE` - should be set to the API endpoint without trailing slash, excluding the `/api` suffix.
  - `API_KEY` - the API key
- `python3 -m parsagon <task>`

## Testing
`python3 -m pytest .`