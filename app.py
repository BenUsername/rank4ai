import os
import openai
from flask import Flask, request, render_template, session, redirect, url_for
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import validators
from readability import Document
from openai import OpenAI
import re
import asyncio
import aiohttp
from aiohttp import ClientSession
from fuzzywuzzy import fuzz
import logging
import nltk
import ssl
from nltk import word_tokenize, pos_tag, ne_chunk
from nltk.chunk import tree2conlltags

# Set up SSL context for NLTK downloads
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Download necessary NLTK data
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('maxent_ne_chunker')
nltk.download('words')

# Explicitly download the punkt tokenizer
nltk.download('punkt')

# Set the NLTK data path
nltk.data.path.append('/app/nltk_data')

# List of common terms to exclude
exclude_terms = [
    "dynamic pricing", "marketing optimization", "personalized services", 
    "predictive analytics", "member analytics", "community engagement",
    "partnerships and collaborations", "membership tiers"
]

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')  # Set a secret key for sessions

# Configure logging
logger = logging.getLogger('logtail')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def is_valid_domain(domain):
    """Validate the domain using the validators library."""
    return validators.domain(domain)

def fetch_website_content(domain):
    """Fetch the website content using HTTP/HTTPS."""
    for scheme in ['https://', 'http://']:
        url = f"{scheme}{domain}"
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException:
            continue
    raise Exception("Unable to fetch the website using both HTTP and HTTPS.")

def extract_main_info(html_content):
    """Extract Title, Description, and Main Content from the HTML."""
    # Use readability to extract the main content
    doc = Document(html_content)
    title = doc.title() if doc.title() else 'No title available'
    summary_html = doc.summary()
    soup = BeautifulSoup(summary_html, 'lxml')
    
    # Extract text from the main content
    main_content = ' '.join([p.get_text().strip() for p in soup.find_all('p')])
    
    # Extract meta description
    soup_full = BeautifulSoup(html_content, 'lxml')
    meta_description = ''
    meta = soup_full.find('meta', attrs={'name': 'description'})
    if meta and meta.get('content'):
        meta_description = meta.get('content').strip()
    
    return {
        'title': title,
        'description': meta_description,
        'content': main_content
    }

def generate_marketing_prompts(title, description, content, domain):
    """Generate five marketing prompts using OpenAI's API."""
    MIN_WORD_COUNT = 30  # Minimum total word count
    title_word_count = len(title.split())
    description_word_count = len(description.split())
    content_word_count = len(content.split())
    total_word_count = title_word_count + description_word_count + content_word_count
    app.logger.info(f"Title word count: {title_word_count}")
    app.logger.info(f"Description word count: {description_word_count}")
    app.logger.info(f"Content word count: {content_word_count}")
    app.logger.info(f"Total content word count: {total_word_count}")
    
    if total_word_count < MIN_WORD_COUNT:
        app.logger.warning("Combined content is too short for meaningful prompt generation.")
        return []
    
    prompt = (
        f"Based on the following information for {domain}, imagine five marketing prompts "
        "for which the chief marketing of the company would love to rank high in ChatGPT answers. The prompts should be as general as possible simulating a user searching for the service or product offered by {domain} but not necessarily mentioning the domain name.\n\n"
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"Content: {content}"
    )
    
    app.logger.debug(f"Constructed Prompt:\n{prompt}")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an impartial LLM agent helping the users find the best website for their needs."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            n=1,
            temperature=0.7,
        )
        
        app.logger.debug(f"OpenAI API Response:\n{response}")
        
        # Extract the text response
        prompts_text = response.choices[0].message.content.strip()
        app.logger.info(f"OpenAI response for marketing prompts: {prompts_text}")
        
        # Split the prompts into a list
        prompts = [line.strip() for line in prompts_text.split('\n') if line.strip() and any(char.isdigit() for char in line)]
        
        # Ensure only five prompts are returned
        prompts = prompts[:5]
        app.logger.info(f"Generated prompts: {prompts}")
        
        if not prompts:
            app.logger.warning("No valid prompts were generated.")
        
        return prompts
    except Exception as e:
        app.logger.error(f"Error during OpenAI API call: {e}")
        return []

def extract_organizations(text):
    """Extract organization names using NLTK."""
    try:
        tokens = word_tokenize(text)
        tagged = pos_tag(tokens)
        chunked = ne_chunk(tagged)
        organizations = [word for word, pos, ne in tree2conlltags(chunked) if ne == 'B-ORGANIZATION']
        return organizations
    except LookupError as e:
        app.logger.error(f"NLTK resource error: {str(e)}")
        return []
    except Exception as e:
        app.logger.error(f"Error in extract_organizations: {str(e)}")
        return []

async def generate_prompt_answer(prompt, domain, info, session):
    try:
        async with session.post('https://api.openai.com/v1/chat/completions', json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are an impartial LLM agent helping users find the best website for their needs. If you mention any competitor companies, products, or websites, enclose ONLY their names in double asterisks like **Competitor Name**. Do not use asterisks for anything else, including approaches, strategies, or general terms."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 300,
            "temperature": 0,
        }) as response:
            result = await response.json()
            if 'error' in result:
                raise Exception(f"OpenAI API error: {result['error']['message']}")
            
            answer = result['choices'][0]['message']['content'].strip()
            
            app.logger.info(f"OpenAI response for prompt '{prompt}': {answer}")
            
            # Extract competitors using regex
            potential_competitors = re.findall(r'\*\*(.*?)\*\*', answer)
            
            # Verify competitors
            competitors = []
            for comp in potential_competitors:
                if verify_company(comp):
                    competitors.append(comp)
            
            competitors_str = ', '.join(competitors) if competitors else 'None mentioned'
            
            # Check for visibility
            visible = any(
                fuzz.partial_ratio(name.lower(), answer.lower()) > 80
                for name in [domain] + [info['title']]
            )
            
            # Highlight only verified competitors in the answer
            for competitor in competitors:
                answer = re.sub(r'\b' + re.escape(competitor) + r'\b', f'<strong>{competitor}</strong>', answer)
            
            # Remove any remaining asterisks
            answer = answer.replace('**', '')
            
            return {
                'prompt': prompt,
                'answer': answer,
                'competitors': competitors_str,
                'visible': 'Yes' if visible else 'No'
            }
    except Exception as e:
        error_message = f"Error generating answer for prompt '{prompt}': {str(e)}"
        app.logger.error(error_message)
        return {
            'prompt': prompt,
            'answer': f'Error: {error_message}',
            'competitors': 'N/A',
            'visible': 'N/A'
        }

def verify_company(name):
    """Verify if a given name is likely a company by checking its web presence."""
    search_url = f"https://www.google.com/search?q={name}+company"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(search_url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check if there's a Wikipedia page or official website in the results
        if soup.find('cite', string=re.compile(r'wikipedia\.org|\.com|\.net|\.org')):
            return True
        
        # Check if there are any business-related keywords in the search results
        business_keywords = ['company', 'corporation', 'inc', 'ltd', 'llc', 'business', 'enterprise']
        if any(keyword in response.text.lower() for keyword in business_keywords):
            return True
        
        return False
    except Exception as e:
        app.logger.error(f"Error verifying company: {str(e)}")
        return False

async def generate_prompt_answers(prompts, domain, info):
    async with ClientSession(headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}) as session:
        tasks = [generate_prompt_answer(prompt, domain, info, session) for prompt in prompts]
        return await asyncio.gather(*tasks)

@app.before_request
def before_request():
    if not request.is_secure:
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handle the home page and form submissions."""
    error = None
    prompts = None
    table = None
    searches_left = 3 - session.get('searches_performed', 0)

    if request.method == 'POST':
        if session.get('searches_performed', 0) >= 3:
            return render_template('index.html', error="You've reached the maximum number of free searches. Please join the waiting list for more.", searches_left=0)
        
        domain = request.form.get('domain', '').strip()
        logger.info(f"User query: {domain}")  # Log the user query
        
        if not is_valid_domain(domain):
            error = 'Invalid domain name.'
            return render_template('index.html', error=error, searches_left=searches_left)
        try:
            html_content = fetch_website_content(domain)
            info = extract_main_info(html_content)
            
            # Generate prompts
            prompts = generate_marketing_prompts(info['title'], info['description'], info['content'], domain)
            
            # Generate answers and create table
            table = asyncio.run(generate_prompt_answers(prompts, domain, info))
            
            app.logger.info(f"Generated table for {domain}: {table}")
            
            session['searches_performed'] = session.get('searches_performed', 0) + 1
            searches_left = 3 - session['searches_performed']
            return render_template('result.html', domain=domain, info=info, prompts=prompts, table=table, show_waiting_list=(searches_left == 0), searches_left=searches_left)
        except Exception as e:
            error = f'Error processing website: {e}'
            logger.error(f"Error processing {domain}: {str(e)}")  # Log any errors
    return render_template('index.html', error=error, searches_left=searches_left)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)