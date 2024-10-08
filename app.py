import os
from flask import Flask, request, render_template, session, jsonify, redirect, send_from_directory
from markupsafe import Markup
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import validators
from readability import Document
from openai import OpenAI
import re
import logging
from datetime import date

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')  # Set a secret key for sessions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Add this constant at the top of your file, after the imports
MAX_API_CALLS_PER_SESSION = 15  # Adjust this number as needed

# Add this near the top of your file, after the imports
BASE_USER_COUNT = 1000  # Starting count
DAILY_INCREASE = 5  # Number of users to add each day

# Add this near the top of your file, after loading other environment variables
CONTACT_EMAIL = os.getenv('mailto', 'support@promptboostai.com')

# Add this near the top of your file, after other imports
from flask import send_from_directory

# Add this route to your app
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

def is_valid_domain(domain):
    """Validate the domain using the validators library."""
    return validators.domain(domain)

def fetch_website_content(domain):
    urls = [
        f"https://{domain}",
        f"http://{domain}",
        f"https://www.{domain}",
        f"http://www.{domain}",
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.text
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Error fetching {url}: {str(e)}")
    
    return None

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
    logger.info(f"Title word count: {title_word_count}")
    logger.info(f"Description word count: {description_word_count}")
    logger.info(f"Content word count: {content_word_count}")
    logger.info(f"Total content word count: {total_word_count}")
    
    if total_word_count < MIN_WORD_COUNT:
        logger.warning("Combined content is too short for meaningful prompt generation.")
        return []
    
    prompt = (
        f"Based on the following information for {domain}, imagine five marketing prompts "
        "for which the chief marketing of the company would love to rank high in ChatGPT answers. The prompts should be as general as possible simulating a user searching for the service or product offered by {domain} but not necessarily mentioning the domain name. Do not include any introductory text such as Here are five marketing prompts that the chief marketing officer of domain would likely want to rank high for in ChatGPT answers:, just give the prompts straight\n\n"
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"Content: {content}"
    )
    
    logger.debug(f"Constructed Prompt:\n{prompt}")
    
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
        
        logger.debug(f"OpenAI API Response:\n{response}")
        
        # Extract the text response
        prompts_text = response.choices[0].message.content.strip()
        logger.info(f"OpenAI response for marketing prompts: {prompts_text}")
        
        # Split the prompts into a list
        prompts = [line.strip() for line in prompts_text.split('\n') if line.strip()]
        
        # Ensure only five prompts are returned
        prompts = prompts[:5]
        logger.info(f"Generated prompts: {prompts}")
        
        if not prompts:
            logger.warning("No valid prompts were generated.")
        
        return prompts
    except Exception as e:
        logger.error(f"Error during OpenAI API call: {e}")
        return []

def generate_prompt_answer(prompt, domain, info):
    # Check if the API call limit has been reached
    if session.get('api_calls', 0) >= MAX_API_CALLS_PER_SESSION:
        app.logger.warning(f"API call limit reached for session")
        return {
            'prompt': prompt,
            'answer': "API call limit reached. Please try again later.",
            'competitors': 'N/A',
            'visible': 'N/A'
        }

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an impartial LLM agent helping users find the best website for their needs. When mentioning competitor companies or products, provide their names followed by their domain name in parentheses, like this: Company Name (company-name.com). Only use this format for actual companies or products, not for general terms or strategies."},
                {"role": "user", "content": f"Provide a succint answer to the following question, mentioning relevant competitor companies or products if applicable: {prompt}"}
            ],
            max_tokens=300,
            temperature=0.3,
        )
        
        # Increment the API call count
        session['api_calls'] = session.get('api_calls', 0) + 1
        
        answer = response.choices[0].message.content.strip()
        
        app.logger.info(f"OpenAI response for prompt '{prompt}': {answer}")
        
        # Extract competitors using regex
        potential_competitors = re.findall(r'\(([a-z0-9-]+\.(?:com|net|org|fr))\)', answer)
        
        # Validate domains and create competitors list
        competitors = [comp for comp in potential_competitors if is_valid_domain(comp)]
        competitors_str = ', '.join(competitors) if competitors else 'None mentioned'
        
        # Check for visibility and rank
        visible = 'No'
        rank = 0
        for i, comp in enumerate(competitors, 1):
            if domain.lower() in comp.lower():
                visible = 'Yes'
                rank = i
                break
        
        visibility_str = f"Yes (Rank: {rank})" if visible == 'Yes' else 'No'
        
        # Log the rank
        if rank > 0:
            app.logger.info(f"Domain {domain} found in competitors list at rank {rank}")
        
        return {
            'prompt': prompt,
            'answer': answer,
            'competitors': competitors_str,
            'visible': visibility_str
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

def generate_prompt_answers(prompts, domain, info):
    return [generate_prompt_answer(prompt, domain, info) for prompt in prompts]

def get_user_count():
    start_date = date(2024, 1, 1)  # Choose a start date
    days_passed = (date.today() - start_date).days
    return BASE_USER_COUNT + (days_passed * DAILY_INCREASE)

@app.before_request
def before_request():
    if not request.is_secure:
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

@app.route('/', methods=['GET'])
def index():
    searches_left = 3 - session.get('searches_performed', 0)
    user_count = get_user_count()
    return render_template('index.html', searches_left=searches_left, user_count=user_count)

@app.route('/analyze', methods=['POST'])
def analyze():
    if session.get('searches_performed', 0) >= 3:
        return jsonify({'error': "You've reached the maximum number of free searches. Please join the waiting list for more."}), 403

    domain = request.form.get('domain', '').strip()
    if not is_valid_domain(domain):
        return jsonify({'error': 'Invalid domain name.'}), 400

    try:
        html_content = fetch_website_content(domain)
        if html_content is None:
            return jsonify({'error': f"We couldn't fetch the content for {domain}. The website may be unavailable or blocking our requests. Please try another domain."}), 404

        info = extract_main_info(html_content)
        prompts = generate_marketing_prompts(info['title'], info['description'], info['content'], domain)
        
        if not prompts:
            return jsonify({'error': "We couldn't generate valid prompts for this website. Please try another domain."}), 500

        table = generate_prompt_answers(prompts, domain, info)
        
        session['searches_performed'] = session.get('searches_performed', 0) + 1
        searches_left = 3 - session['searches_performed']

        return jsonify({
            'domain': domain,
            'info': info,
            'prompts': prompts,
            'table': table,
            'searches_left': searches_left
        })

    except Exception as e:
        app.logger.error(f"Error processing {domain}: {str(e)}")
        return jsonify({'error': f"An error occurred while processing your request for {domain}. The website may be unavailable or blocking our requests. Please try another domain."}), 500

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

@app.route('/get_advice', methods=['POST'])
def get_advice():
    app.logger.info('get_advice route called')
    data = request.json
    domain = data.get('domain')
    prompt = data.get('prompt')
    
    app.logger.info(f'Received request for advice - Domain: {domain}, Prompt: {prompt}')
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI assistant providing advice on improving website visibility in AI search results."},
                {"role": "user", "content": f"Provide 5 specific tips to improve the visibility of {domain} for the search query: '{prompt}'. Format the response as a numbered list."}
            ],
            max_tokens=250,
            temperature=0.7,
        )
        
        advice = response.choices[0].message.content.strip()
        
        # Ensure the advice is formatted as a numbered list
        if not advice.startswith('1.'):
            advice = '\n'.join([f"{i+1}. {tip.strip()}" for i, tip in enumerate(advice.split('\n'))])
        
        app.logger.info(f'Advice generated successfully for {domain}')
        return jsonify({'advice': advice})
    except Exception as e:
        app.logger.error(f"Error generating advice: {str(e)}")
        return jsonify({'error': 'An error occurred while generating advice. Please try again.'}), 500

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html', contact_email=CONTACT_EMAIL)

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html', contact_email=CONTACT_EMAIL)

def format_visibility(visible, domain, prompt, row_index):
    if 'Yes' in visible:
        rank = int(re.search(r'\d+', visible).group())
        rank_text = {
            1: 'first! 🥇🎉',
            2: 'second! 🥈🎉',
            3: 'third! 🥉🎉'
        }.get(rank, f'{rank}th! 🎉')
        return Markup(f'<span style="color: green;">✓ Yes</span><br>Congrats, you\'re {rank_text}')
    else:
        return Markup(f'<span style="color: red;">✗ No</span>'
                      f'<button class="info-button" onclick="showAdvice(\'{domain}\', \'{prompt.replace("\'", "\\\'")}\', {row_index})">i</button>'
                      f'<div class="spinner" id="spinner-{row_index}" style="display: none;"></div>')

# Don't forget to pass this function to your template context when rendering
@app.route('/results')
def results():
    # Retrieve necessary data from the session or database
    domain = session.get('domain', '')
    info = session.get('info', {})
    prompts = session.get('prompts', [])
    table = session.get('table', [])
    searches_left = 3 - session.get('searches_performed', 0)

    return render_template('result.html', 
                           domain=domain,
                           info=info,
                           prompts=prompts,
                           table=table,
                           searches_left=searches_left,
                           format_visibility=format_visibility)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)