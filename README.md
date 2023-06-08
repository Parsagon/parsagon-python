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
- Actions example: `python3 -m parsagon "1. Go to https://assessment.cot.tn.gov/TPAD/ 2. Select 'Bedford' from the county dropdown 3. Type '001' in the Search Term box. 4. Click on the Search button."`
- Scraping example: `python3 -m parsagon "1. Go to https://www.hannaford.com/product/cedar-s-whole-wheat-wraps/736543?refineByCategoryId=50061 2. Scrape the product title, weight, and price (as a float)."`
- Add the `-v` flag to see more debugging information.

## Testing
`python3 -m pytest .`