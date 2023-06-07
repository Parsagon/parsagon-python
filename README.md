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
- Example: `python3 -m parsagon "1. Go to https://assessment.cot.tn.gov/TPAD/ 2. Select 'Bedford' from the county dropdown 3. Type '001' in the Search Term box. 4. Click on the Search button."`

## Testing
`python3 -m pytest .`