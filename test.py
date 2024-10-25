import httpx
from bs4 import BeautifulSoup

def get_website_info(url):
    try:
        # Define headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' 
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/58.0.3029.110 Safari/537.3'
        }
        
        # Make an HTTP GET request to the website with headers
        response = httpx.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responsesa

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract the title
        title = soup.title.string if soup.title else 'No title found'

        # Extract the description
        description_tag = soup.find('meta', attrs={'name': 'description'})
        description = description_tag['content'] if description_tag else 'No description found'

        return title, description

    except httpx.RequestError as e:
        return f"An error occurred while requesting {url}: {e}"
    except httpx.HTTPStatusError as e:
        return f"HTTP error occurred: {e}"

# Example usage
url = "https://www.lodgify.com"
title, description = get_website_info(url)
print(f"Title: {title}")
print(f"Description: {description}")
