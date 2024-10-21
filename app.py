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
import time
from urllib.parse import quote_plus  
import difflib
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from urllib.parse import urljoin
import json
import threading
import uuid
from werkzeug.serving import WSGIRequestHandler
import requests.exceptions
import tiktoken
import gc
import psutil

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')  # Set a secret key for sessions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Revert OpenAI client initialization to synchronous
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Add this constant at the top of your file, after the imports
MAX_API_CALLS_PER_SESSION = 100  # Adjust this number as needed

# Add this near the top of your file, after the imports
BASE_USER_COUNT = 1000  # Starting count
DAILY_INCREASE = 5  # Number of users to add each day

# Add this near the top of your file, after loading other environment variables
CONTACT_EMAIL = os.getenv('mailto', 'support@promptboostai.com')

# Logo.dev API token
LOGO_DEV_TOKEN = os.getenv('LOGO_DEV_TOKEN')

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

# Increase the timeout for requests
requests_timeout = 30  # 30 seconds

def fetch_website_content(domain):
    base_url = f"https://{domain}"
    pages_to_fetch = [
        "",  # Homepage
        "/blog",
        "/about",
        "/products",
        "/services",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    existing_content = {}
    html_content = None
    
    for page in pages_to_fetch:
        url = urljoin(base_url, page)
        try:
            response = requests.get(url, headers=headers, timeout=requests_timeout, verify=False)
            if response.status_code == 200:
                content = response.text
                soup = BeautifulSoup(content, 'html.parser')
                main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
                if main_content:
                    existing_content[url] = main_content.get_text(strip=True)
                else:
                    existing_content[url] = soup.get_text(strip=True)
                if page == "":
                    html_content = content
        except Exception as e:
            app.logger.info(f"Error fetching {url}: {str(e)}")
    
    return html_content, existing_content

def generate_marketing_prompts(title, description, content, domain):
    MIN_WORD_COUNT = 30
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
        
        prompts_text = response.choices[0].message.content.strip()
        logger.info(f"OpenAI response for marketing prompts: {prompts_text}")
        
        prompts = [line.strip() for line in prompts_text.split('\n') if line.strip()]
        
        prompts = prompts[:5]
        logger.info(f"Generated prompts: {prompts}")
        
        if not prompts:
            logger.warning("No valid prompts were generated.")
        
        return prompts
    except Exception as e:
        logger.error(f"Error during OpenAI API call: {e}")
        return []

def extract_main_info(html_content):
    """Extract Title, Description, and Main Content from the HTML."""
    # Use readability to extract the main content
    doc = Document(html_content)
    title = doc.title() if doc.title() else 'No title available'
    summary_html = doc.summary()
    soup = BeautifulSoup(summary_html, 'lxml')
    
    # Extract text from the main content
    main_content = ' '.join([p.get_text(strip=True) for p in soup.find_all('p')])
    
    # Extract meta description
    soup_full = BeautifulSoup(html_content, 'lxml')
    meta_description = ''
    meta = soup_full.find('meta', attrs={'name': 'description'})
    if meta and meta.get('content'):
        meta_description = meta.get('content').strip()
    
    del soup, soup_full  # Explicitly delete to free memory
    gc.collect()  # Force garbage collection
    
    return {
        'title': title,
        'description': meta_description,
        'content': main_content[:5000]  # Limit content length
    }

def analyze_content_gaps(domain, ai_response, existing_content):
    suggestions = []
    # Compare AI response with existing content
    matches = difflib.get_close_matches(ai_response, existing_content.keys(), n=1, cutoff=0.6)
    if matches:
        closest_match = matches[0]
        suggestion = f"Update '{closest_match}' to include information about: {ai_response}"
    else:
        suggestion = f"Consider creating new content about: {ai_response}"
    suggestions.append(suggestion)
    return suggestions

def generate_prompt_answer(prompt, domain, info, existing_content):
    # Check if the API call limit has been reached
    if session.get('api_calls', 0) >= MAX_API_CALLS_PER_SESSION:
        app.logger.warning(f"API call limit reached for session")
        return {
            'prompt': prompt,
            'answer': "API call limit reached. Join the waiting list for unlimited access.",
            'competitors': 'N/A',
            'visible': 'N/A',
            'content_suggestions': []
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
        
        # Update this regex pattern to capture a wider range of domain extensions
        potential_competitors = re.findall(r'\(([a-z0-9-]+(?:\.[a-z0-9-]+)+)\)', answer)
        
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
        
        visibility_str = 'No'
        if rank > 0:
            if rank == 1:
                visibility_str = "You're 1st!"
            elif rank == 2:
                visibility_str = "You're 2nd!"
            elif rank == 3:
                visibility_str = "You're 3rd!"
            else:
                visibility_str = f"You're {rank}th"
        
        # Log the rank
        if rank > 0:
            app.logger.info(f"Domain {domain} found in competitors list at rank {rank}")
        
        # Analyze content gaps
        content_suggestions = analyze_content_gaps(domain, [answer], existing_content)

        return {
            'prompt': prompt,
            'answer': answer,
            'competitors': competitors_str,
            'visible': visibility_str,
            'content_suggestions': content_suggestions
        }
    except Exception as e:
        error_message = f"Error generating answer for prompt '{prompt}': {str(e)}"
        app.logger.error(error_message)
        return {
            'prompt': prompt,
            'answer': f'Error: {error_message}',
            'competitors': 'N/A',
            'visible': 'N/A',
            'content_suggestions': []
        }

def generate_prompt_answers(prompts, domain, info, existing_content):
    return [generate_prompt_answer(prompt, domain, info, existing_content) for prompt in prompts]

def get_user_count():
    start_date = date(2024, 1, 1)  # Choose a start date
    days_passed = (date.today() - start_date).days
    return BASE_USER_COUNT + (days_passed * DAILY_INCREASE)

def get_logo_dev_logo(domain):
    """Constructs the Logo.dev API URL for a given domain."""
    public_key = "pk_Iiu041TAThCqnelMWeRtDQ"
    encoded_domain = quote_plus(domain)
    logo_url = f"https://img.logo.dev/{encoded_domain}?token={public_key}&size=200&format=png"
    return logo_url

# Add a new function to get the Brandfetch CDN URL
def get_brandfetch_cdn_logo(domain):
    """Constructs the Brandfetch CDN URL for a given domain."""
    return f"https://cdn.brandfetch.io/{domain}"

def log_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    app.logger.info(f"Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB")

@app.before_request
def before_request():
    log_memory_usage()

@app.after_request
def after_request(response):
    log_memory_usage()
    gc.collect()  # Force garbage collection
    return response

# Near the top of the file, update or add this constant
MAX_SEARCHES_PER_SESSION = 3  # Keep it at 3 searches

# Set a longer timeout for the /get_advice route
WSGIRequestHandler.timeout = 120  # 120 seconds

@app.route('/', methods=['GET'])
def index():
    searches_left = session.get('searches_left', MAX_SEARCHES_PER_SESSION)
    user_count = get_user_count()
    domain = request.args.get('domain')
    show_results = request.args.get('showResults')
    return render_template('index.html', searches_left=searches_left, user_count=user_count, domain=domain, show_results=show_results)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

async def calculate_score(table):
    total_points = 0
    max_points = len(table) * 5  # 5 points max per prompt
    for row in table:
        visible = row['visible'].lower()
        if visible == 'no':
            total_points += 1  # Minimum 1 point even if not visible
        elif visible.startswith('you'):
            # Handle cases like "You're 1st!", "You're 2nd!", etc.
            try:
                rank_text = visible.split()[1]  # Get the second word (e.g., "1st", "2nd")
                rank = int(''.join(filter(str.isdigit, rank_text)))  # Extract digits
                total_points += max(6 - rank, 1)  # 5 points for 1st, 4 for 2nd, etc., minimum 1
            except (IndexError, ValueError):
                total_points += 1  # Default to 1 point if parsing fails
        else:
            total_points += 5  # Assume top rank if format is unexpected
    
    # Scale score from 62 to 100
    score = 62 + (total_points / max_points) * 38
    return round(score)

@app.route('/analyze', methods=['POST'])
@limiter.limit("5 per minute")
async def analyze():
    try:
        start_time = time.time()
        domain = request.form['domain']
        searches_left = session.get('searches_left', MAX_SEARCHES_PER_SESSION)

        if searches_left <= 0:
            return jsonify({'error': 'No searches left. Please try again later.', 'searches_left': 0}), 403

        if not is_valid_domain(domain):
            return jsonify({'error': 'Invalid domain name.', 'searches_left': searches_left}), 400

        logging.info(f"Fetching content for {domain}")
        html_content, existing_content = fetch_website_content(domain)
        if not existing_content:
            return jsonify({'error': f"We couldn't fetch any content for {domain}. The website may be unavailable or blocking our requests. Please try another domain.", 'searches_left': searches_left}), 404

        logging.info(f"Extracting main info for {domain}")
        info = extract_main_info(html_content)
        
        logging.info(f"Generating marketing prompts for {domain}")
        prompts = generate_marketing_prompts(info['title'], info['description'], info['content'], domain)
        
        if not prompts:
            return jsonify({'error': "We couldn't generate valid prompts for this website. Please try another domain.", 'searches_left': searches_left}), 500

        logging.info(f"Generating prompt answers for {domain}")
        table = generate_prompt_answers(prompts, domain, info, existing_content)
        score = await calculate_score(table)

        session['searches_left'] = searches_left - 1
        searches_left = session['searches_left']

        end_time = time.time()
        logging.info(f"Total processing time for {domain}: {end_time - start_time} seconds")

        logo_url = get_logo_dev_logo(domain)

        return jsonify({
            'domain': domain,
            'info': info,
            'prompts': prompts,
            'table': table,
            'searches_left': searches_left,
            'logo_url': logo_url,
            'score': score
        })

    except requests.exceptions.Timeout:
        logger.error(f"Timeout error processing {domain}")
        return jsonify({'error': f"The request timed out while processing {domain}. Please try again later."}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error processing {domain}: {str(e)}")
        return jsonify({'error': f"An error occurred while fetching data from {domain}. Please try again later."}), 502
    except Exception as e:
        logger.error(f"Error processing {domain}: {str(e)}", exc_info=True)
        return jsonify({'error': f"An unexpected error occurred while processing your request: {str(e)}. Please try again later."}), 500

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html', contact_email=CONTACT_EMAIL)

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html', contact_email=CONTACT_EMAIL)

@app.route('/blog/track-brand-visibility-ai-search')
def blog_post():
    return render_template('blog_post.html')

@app.route('/blog/answer-engine-optimization')
def aeo_blog_post():
    return render_template('aeo_blog_post.html')

# Dictionary to store job results
job_results = {}

MAX_PROCESSING_TIME = 60  # Maximum processing time in seconds

def background_task(job_id, domain, prompt, existing_content):
    start_time = time.time()
    try:
        while time.time() - start_time < MAX_PROCESSING_TIME:
            content_suggestions = get_advice(domain, prompt, existing_content)
            if content_suggestions:
                job_results[job_id] = content_suggestions
                return
            time.sleep(5)  # Wait for 5 seconds before trying again
        
        # If we've reached here, it means we've timed out
        job_results[job_id] = {"error": "Processing timed out. Please try again."}
    except Exception as e:
        job_results[job_id] = {"error": str(e)}

@app.route('/get_advice', methods=['POST'])
def get_advice_route():
    data = request.json
    domain = data.get('domain')
    prompt = data.get('prompt')

    if not domain or not prompt:
        return jsonify({'error': 'Domain and prompt are required.'}), 400

    job_id = str(uuid.uuid4())
    existing_content = fetch_website_content(domain)
    
    # Start the background task
    thread = threading.Thread(target=background_task, args=(job_id, domain, prompt, existing_content))
    thread.start()

    return jsonify({"job_id": job_id}), 202

@app.route('/get_advice_result/<job_id>', methods=['GET'])
def get_advice_result(job_id):
    result = job_results.get(job_id)
    if result is None:
        return jsonify({"status": "processing"}), 202
    else:
        # Remove the result from storage after retrieving
        del job_results[job_id]
        return jsonify(result), 200

@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error('Server Error: %s', (error))
    return render_template('500.html'), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    app.logger.warning('Rate limit exceeded: %s', str(e))
    return jsonify(error="Rate limit exceeded. Please try again later."), 429

@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.error('Unhandled Exception: %s', (e))
    return render_template('500.html'), 500

def get_advice(domain, prompt, existing_content):
    try:
        # Estimate token count
        encoding = tiktoken.encoding_for_model("gpt-4o-mini")
        
        # Function to count tokens
        def count_tokens(text):
            return len(encoding.encode(text))
        
        # Truncate existing content if it's too large
        max_content_tokens = 100000  # Adjust as needed
        total_content = json.dumps(existing_content)
        content_tokens = count_tokens(total_content)
        
        if content_tokens > max_content_tokens:
            # Truncate content more safely
            truncated_content = total_content[:max_content_tokens]
            last_brace = truncated_content.rfind('}')
            if last_brace != -1:
                truncated_content = truncated_content[:last_brace+1]
            else:
                truncated_content = "{}"  # Fallback to empty object if no valid JSON
            
            try:
                existing_content = json.loads(truncated_content)
            except json.JSONDecodeError:
                app.logger.error(f"Failed to parse truncated content: {truncated_content}")
                existing_content = {}  # Fallback to empty object
        
        # Prepare the messages
        system_message = "You are an expert in SEO and content strategy."
        user_message = f"""
        Analyze the following prompt and existing content for {domain}. 
        Provide specific suggestions for content updates:
        1. Suggest updates for up to 3 existing pages, including the main landing page and up to 2 blog posts.
        2. Suggest 3 new blog posts to create.

        Prompt: {prompt}

        Existing content:
        {json.dumps(existing_content, indent=2)}

        Format your response as a JSON object with two keys: 'existing_page_suggestions' and 'new_blog_post_suggestions'.
        For existing pages, include 'url' and 'suggestion'.
        For new blog posts, include 'title' and 'outline'. The 'outline' should always be an array of strings, even if there's only one item.
        Limit your response to a maximum of 3 existing page suggestions and 3 new blog post suggestions.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7,
        )
        
        content = response.choices[0].message.content.strip()
        app.logger.info(f"Raw OpenAI API response: {content}")
        
        # Remove the triple backticks and "json" if present
        content = content.replace("```json", "").replace("```", "").strip()
        
        try:
            content_suggestions = json.loads(content)
        except json.JSONDecodeError as e:
            app.logger.error(f"JSON Decode Error: {e}")
            app.logger.error(f"Cleaned response content: {content}")
            
            # Attempt to fix common JSON issues
            content = content.replace("'", '"')  # Replace single quotes with double quotes
            content = re.sub(r'(\w+):', r'"\1":', content)  # Add quotes to keys
            app.logger.info(f"Attempting to parse fixed JSON: {content}")
            
            try:
                content_suggestions = json.loads(content)
            except json.JSONDecodeError:
                app.logger.error("Failed to parse JSON even after attempted fixes")
                return {"error": "Failed to parse the AI response. Please try again."}
        
        # Ensure we have the expected structure
        if not isinstance(content_suggestions, dict):
            app.logger.error(f"Unexpected content structure: {content_suggestions}")
            return {"error": "The AI response was not in the expected format. Please try again."}
        
        # Ensure we have the required keys, if not, provide empty lists
        content_suggestions['existing_page_suggestions'] = content_suggestions.get('existing_page_suggestions', [])
        content_suggestions['new_blog_post_suggestions'] = content_suggestions.get('new_blog_post_suggestions', [])
        
        # Ensure we have at most 3 suggestions for each category
        content_suggestions['existing_page_suggestions'] = content_suggestions['existing_page_suggestions'][:3]
        content_suggestions['new_blog_post_suggestions'] = content_suggestions['new_blog_post_suggestions'][:3]

        return content_suggestions
    except Exception as e:
        app.logger.error(f"Error generating advice: {str(e)}", exc_info=True)
        return {"error": "An error occurred while generating advice. Please try again later."}

# Add this new route
@app.route('/autocomplete/<query>')
@limiter.limit("200 per hour")  # Increase the limit or remove it for testing
def autocomplete(query):
    url = f"https://api.brandfetch.io/v2/search/{quote_plus(query)}"
    headers = {
        "Authorization": f"Bearer {os.getenv('BRANDFETCH_API_KEY')}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        suggestions = []
        for item in data:
            if 'name' in item and 'domain' in item:
                logo_url = None
                if 'icon' in item and item['icon']:
                    logo_url = item['icon']
                
                suggestions.append({
                    'name': item['name'],
                    'domain': item['domain'],
                    'logo_url': logo_url
                })
        
        app.logger.info(f"Autocomplete suggestions: {suggestions}")
        return jsonify(suggestions[:5])  # Limit to 5 suggestions
    except requests.RequestException as e:
        app.logger.error(f"Error fetching autocomplete suggestions: {str(e)}")
        return jsonify([])

@app.route('/blog/ultimate-guide-ranking-high-llm-results')
def llm_ranking_blog_post():
    return render_template('llm_ranking_blog_post.html')

@app.route('/blog/llm-visibility-secret')
def llm_visibility_blog_post():
    return render_template('llm_visibility_blog_post.html')

@app.route('/blog/understanding-large-language-models-seo')
def understanding_llm_seo_blog_post():
    return render_template('understanding_llm_seo_blog_post.html')

@app.route('/blog/case-studies-improved-llm-visibility')
def case_studies_llm_visibility_blog_post():
    return render_template('case_studies_llm_visibility_blog_post.html')

@app.route('/blog/common-mistakes-ai-search-optimization')
def common_mistakes_ai_search_blog_post():
    return render_template('common_mistakes_ai_search_blog_post.html')

@app.route('/blog/future-of-search')
def future_of_search_blog_post():
    return render_template('future_of_search_blog_post.html')

@app.route('/blog/ai-friendly-content')
def ai_friendly_content_blog_post():
    return render_template('ai_friendly_content_blog_post.html')

@app.route('/blog/ai-search-performance-metrics')
def ai_search_performance_metrics_blog_post():
    return render_template('ai_search_performance_metrics_blog_post.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    # In development, set debug to True and allow all hosts
    app.run(host='0.0.0.0', port=port, debug=True)
