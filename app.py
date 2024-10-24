import os
from flask import Flask, request, render_template, session, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import validators
from openai import OpenAI
import re
import logging
from datetime import date, datetime, timedelta
import time
from urllib.parse import quote_plus  
import difflib
from urllib.parse import urljoin
import json
import threading
import uuid
import requests.exceptions
import gc
import psutil
import difflib
from requests.exceptions import RequestException
import urllib3
import asyncio
from crawl4ai import AsyncWebCrawler
from playwright.sync_api import sync_playwright
import subprocess

# Load environment variables from .env file  
load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Constants
MAX_API_CALLS_PER_SESSION = 100
BASE_USER_COUNT = 1000
DAILY_INCREASE = 5
CONTACT_EMAIL = os.getenv('mailto', 'support@promptboostai.com')
MAX_SEARCHES_PER_SESSION = 3
requests_timeout = 30

# Disable SSL warnings (use with caution)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def is_valid_domain(domain):
    return validators.domain(domain)

def fetch_page(url, headers, timeout):
    try:
        response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        app.logger.info(f"Error fetching {url}: {str(e)}")
    return None

def fetch_main_page_content(domain):
    base_url = f"https://{domain}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    MAX_HTML_SIZE = 1 * 1024 * 1024  # 1MB

    try:
        # Try HTTPS first with regular requests
        response = requests.get(base_url, headers=headers, timeout=requests_timeout, verify=False)
        response.raise_for_status()
        content = response.text[:MAX_HTML_SIZE]
        return process_content(content)
    except RequestException as e:
        app.logger.warning(f"HTTPS request failed for {domain}: {str(e)}")
        try:
            # If HTTPS fails, try HTTP
            base_url = f"http://{domain}"
            response = requests.get(base_url, headers=headers, timeout=requests_timeout)
            response.raise_for_status()
            content = response.text[:MAX_HTML_SIZE]
            return process_content(content)
        except RequestException as e:
            app.logger.warning(f"HTTP request also failed for {domain}: {str(e)}")
            
            # Fallback to crawl4ai
            app.logger.info(f"Attempting to fetch {domain} using crawl4ai")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(fetch_with_crawl4ai(base_url))
            finally:
                loop.close()

def process_content(content):
    MAX_HTML_SIZE = 1 * 1024 * 1024  # 1MB
    soup = BeautifulSoup(content[:MAX_HTML_SIZE], 'html.parser')
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    text_content = (main_content.get_text(strip=True) if main_content else soup.get_text(strip=True))[:5000]
    
    return content[:MAX_HTML_SIZE], text_content

def fetch_additional_content(domain):
    base_url = f"https://{domain}"
    pages_to_fetch = ["/blog"]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    existing_content = {}
    MAX_HTML_SIZE = 512 * 1024  # 512KB

    for page in pages_to_fetch:
        url = urljoin(base_url, page)
        try:
            app.logger.info(f"Fetching content from {url}")
            response = requests.get(url, headers=headers, timeout=requests_timeout, verify=False)
            response.raise_for_status()
            content = response.text[:MAX_HTML_SIZE]
            soup = BeautifulSoup(content, 'html.parser')
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            text_content = (main_content.get_text(strip=True) if main_content else soup.get_text(strip=True))[:2000]
            existing_content[url] = text_content
            app.logger.info(f"Successfully fetched content from {url}")
        except Exception as e:
            app.logger.warning(f"Error fetching {url}: {str(e)}")

    if not existing_content:
        app.logger.warning(f"No additional content found for {domain}")

    return existing_content

def generate_marketing_prompts(title, description, content, domain):
    MIN_WORD_COUNT = 20
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
        f"Based on the following information for {domain}, imagine five prompts "
        " simulating what a user might search on LLM in which answers this company would like to feature. Make the prompt go from general to more and more specific, simulating an interaction between the user and the LLM, user searching for the service or product offered by {domain} interacting with the LLM to refine his queries and increasing the chance for the {domain} to be metionned but the user not mentioning the domain name. As part of this specify in the second prompt the country or region the user is most likely to be based in based on the suffix of the {domain} (eg France for .fr, brasil for .com.br) or based on the headquarter or main office location of the company if you know it. Do not include any introductory text such as Here are five marketing prompts that the chief marketing officer of domain would likely want to rank high for in ChatGPT answers:, just give the prompts straight\n\n"
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
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract title
    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else 'No title available'
    
    # Extract meta description
    meta_description = ''
    meta = soup.find('meta', attrs={'name': 'description'})
    if meta and meta.get('content'):
        meta_description = meta.get('content').strip()
    
    # Extract main content
    main_content = ''
    # Try to find the main content in common tags
    main_candidates = soup.find_all(['main', 'article', 'section', 'div'], class_=re.compile(r'(content|main|article)', re.I))
    if main_candidates:
        # Combine text from all candidate tags
        main_content = ' '.join([tag.get_text(strip=True) for tag in main_candidates])
    else:
        # Fallback to body content
        body = soup.find('body')
        if body:
            main_content = body.get_text(strip=True)
    
    # Limit content length
    main_content = main_content[:5000]
    
    # Explicitly delete the soup object
    del soup
    
    # Call garbage collection
    gc.collect()
    
    return {
        'title': title,
        'description': meta_description,
        'content': main_content
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
    start_date = date(2024, 1, 1)
    days_passed = (date.today() - start_date).days
    time.sleep(0.1)  # Simulate some operation
    return BASE_USER_COUNT + (days_passed * DAILY_INCREASE)

def get_logo_dev_logo(domain):
    public_key = "pk_Iiu041TAThCqnelMWeRtDQ"
    encoded_domain = quote_plus(domain)
    logo_url = f"https://img.logo.dev/{encoded_domain}?token={public_key}&size=200&format=png"
    time.sleep(0.1)  # Simulate some operation
    return logo_url

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
    gc.collect()
    return response

@app.route('/', methods=['GET'])
def index():
    searches_left = session.get('searches_left', MAX_SEARCHES_PER_SESSION)
    user_count = get_user_count()
    domain = request.args.get('domain')
    show_results = request.args.get('showResults')
    return render_template('index.html', searches_left=searches_left, user_count=user_count, domain=domain, show_results=show_results)

def calculate_score(table, content):
    total_points = 0
    max_points = len(table) * 5  # 5 points max per prompt
    for row in table:
        visible = row['visible'].lower()
        if visible == 'no':
            total_points += 1  # Minimum 1 point even if not visible
        elif visible.startswith('you'):
            try:
                rank_text = visible.split()[1]  # Get the second word (e.g., "1st", "2nd")
                rank = int(''.join(filter(str.isdigit, rank_text)))  # Extract digits
                total_points += max(6 - rank, 1)  # 5 points for 1st, 4 for 2nd, etc., minimum 1
            except (IndexError, ValueError):
                total_points += 1  # Default to 1 point if parsing fails
        else:
            total_points += 5  # Assume top rank if format is unexpected
    
    # Scale score from 62 to 100
    initial_score = 62 + (total_points / max_points) * 38
    initial_score = round(initial_score)

    if initial_score <= 70:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an AI assistant that evaluates website ranking in LLM search results."},
                    {"role": "user", "content": f"From 1 to 100, 1 being the worst and 100 being perfect, how well does this site rank on LLM search given its content: {content}. Aim that the score really go from 1 to 100 for typical sites with a normal distribution, not a concentration around a specific score. Please provide only a number."}
                ],
                max_tokens=10,
                temperature=0.7,
            )
            
            ai_score = int(response.choices[0].message.content.strip())
            
            # Use a weighted average of the initial score and AI score
            final_score = round(0 * initial_score + 1 * ai_score)
        except Exception as e:
            app.logger.error(f"Error getting AI score: {str(e)}")
            final_score = initial_score
    else:
        final_score = initial_score

    return final_score

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        start_time = time.time()
        domain = request.form['domain']
        searches_left = session.get('searches_left', MAX_SEARCHES_PER_SESSION)

        app.logger.info(f"Analyzing domain: {domain}")

        if searches_left <= 0:
            return jsonify({'error': 'No searches left. Please try again later.', 'searches_left': 0}), 403

        if not is_valid_domain(domain):
            return jsonify({'error': 'Invalid domain name.', 'searches_left': searches_left}), 400

        app.logger.info(f"Fetching main page content for {domain}")
        html_content, main_text_content = fetch_main_page_content(domain)
        if html_content is None or main_text_content is None:
            return jsonify({'error': f"We couldn't fetch the content for {domain}. The website may be unavailable or blocking our requests. Please try another domain.", 'searches_left': searches_left}), 404

        app.logger.info(f"Extracting main info for {domain}")
        info = extract_main_info(html_content)

        app.logger.info(f"Generating marketing prompts for {domain}")
        prompts = generate_marketing_prompts(info['title'], info['description'], info['content'], domain)

        if not prompts:
            return jsonify({'error': "Couldn't generate valid prompts for this website. Please try another domain.", 'searches_left': searches_left}), 500

        app.logger.info(f"Generating prompt answers for {domain}")
        table = generate_prompt_answers(prompts, domain, info, existing_content={})
        score = calculate_score(table, info['content'])  # Pass info['content'] as the second argument

        session['searches_left'] = searches_left - 1
        searches_left = session['searches_left']

        end_time = time.time()
        app.logger.info(f"Total processing time for {domain}: {end_time - start_time} seconds")

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

    except Exception as e:
        app.logger.error(f"Error processing {domain}: {str(e)}", exc_info=True)
        return jsonify({'error': f"An unexpected error occurred: {str(e)}. Please try again later."}), 500

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

def background_task(job_id, domain, prompt):
    start_time = time.time()
    try:
        content_suggestions = get_advice(domain, prompt)
        if content_suggestions:
            job_results[job_id] = content_suggestions
            return
        # Handle timeout or retries as necessary
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

    thread = threading.Thread(target=background_task, args=(job_id, domain, prompt))
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
    app.logger.warning('Rate limit exceeded')
    return jsonify(error="Rate limit exceeded. Please try again later."), 429

@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.error('Unhandled Exception: %s', (e))
    return render_template('500.html'), 500

def get_advice(domain, prompt):
    try:
        logging.info(f"Fetching additional content for {domain}")
        existing_content = fetch_additional_content(domain)
        if not existing_content:
            logging.warning(f"No additional content fetched for {domain}")
            # Instead of returning an error, let's proceed with the main content
            existing_content = {"main": fetch_main_page_content(domain)[1]}  # Use the text content from the main page

        if not existing_content:
            logging.error(f"Failed to fetch any content for {domain}")
            return {"error": "Failed to fetch content for analysis. Please try again later."}

        total_content = json.dumps(existing_content)
        max_content_tokens = 1000
        total_content = ' '.join(total_content.split()[:max_content_tokens])

        system_message = "You are an expert in SEO and content strategy."
        user_message = f"""
        Analyze the following prompt and existing content for {domain}.
        Provide specific suggestions for content updates:
        1. Suggest updates for up to 3 existing pages, including the main landing page and up to 2 blog posts.
        2. Suggest 3 new blog posts to create.

        Prompt: {prompt}

        Existing content:
        {total_content}

        Format your response as a JSON object with two keys: 'existing_page_suggestions' and 'new_blog_post_suggestions'.
        For existing pages, include 'url' and 'suggestion'.
        For new blog posts, include 'title' and 'outline'. The 'outline' should always be an array of strings.
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

        content = content.replace("```json", "").replace("```", "").strip()
        content_suggestions = json.loads(content)

        content_suggestions['existing_page_suggestions'] = content_suggestions.get('existing_page_suggestions', [])[:3]
        content_suggestions['new_blog_post_suggestions'] = content_suggestions.get('new_blog_post_suggestions', [])[:3]

        return content_suggestions

    except Exception as e:
        app.logger.error(f"Error generating advice: {str(e)}", exc_info=True)
        return {"error": f"An error occurred while generating advice: {str(e)}. Please try again later."}

# Add this new route
@app.route('/autocomplete/<query>')
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

@app.before_request
def limit_remote_addr():
    if request.endpoint == 'analyze':  # Only apply rate limiting to the analyze endpoint
        now = datetime.now()  # Use offset-naive datetime
        if 'rate_limit' not in session:
            session['rate_limit'] = {'count': 0, 'reset_time': now.timestamp()}
        else:
            reset_time = datetime.fromtimestamp(session['rate_limit']['reset_time'])
            if now > reset_time:
                session['rate_limit'] = {'count': 0, 'reset_time': now.timestamp()}
            session['rate_limit']['count'] += 1
            if session['rate_limit']['count'] > 5:  # Limit to 5 requests per minute
                return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
        
        # Store reset_time as timestamp
        session['rate_limit']['reset_time'] = (now + timedelta(minutes=1)).timestamp()

@app.route('/short-term-rental')
def short_term_rental():
    return render_template('short_term_rental.html')

@app.route('/analyze_city', methods=['POST'])
def analyze_city():
    city = request.form['city']
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that recommends the best Airbnb listings. Provide exactly 3 recommendations, each with a name and brief description. Format your response as a numbered list, with each item in the format 'Name: Description'. Do not include any introductory or concluding text."},
                {"role": "user", "content": f"/search Recommend the best Airbnb in {city}."}
            ],
            max_tokens=300,
            n=1,
            temperature=0.7,
        )
        
        recommendations = response.choices[0].message.content.strip().split('\n')
        formatted_recommendations = []
        for rec in recommendations:
            # Remove the number and period at the start
            rec = re.sub(r'^\d+\.\s*', '', rec)
            # Split by the first colon
            parts = rec.split(':', 1)
            if len(parts) == 2:
                name = parts[0].strip()
                description = parts[1].strip()
                formatted_recommendations.append({"name": name, "description": description})
        
        return jsonify({
            "recommendations": formatted_recommendations
        })
    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": "An error occurred while processing your request. Please try again later."}), 500

async def fetch_with_crawl4ai(url):
    browser_path = get_playwright_executable_path()
    app.logger.info(f"Attempting to use Chromium at: {browser_path}")
    app.logger.info(f"File exists: {os.path.exists(browser_path)}")
    
    async with AsyncWebCrawler(verbose=True, playwright_kwargs={
        'chromium_sandbox': False,
        'playwright_kwargs': {
            'executable_path': browser_path
        }
    }) as crawler:
        try:
            result = await crawler.arun(url=url)
            
            if result.success:
                if hasattr(result, 'markdown'):
                    content = result.markdown[:5000]  # Limit to 5000 characters
                    return result.html, content
                else:
                    app.logger.warning(f"No markdown content found for {url}")
                    return None, None
            else:
                app.logger.warning(f"Failed to fetch content from {url} using crawl4ai")
                return None, None
        except Exception as e:
            app.logger.error(f"Error in fetch_with_crawl4ai: {str(e)}")
            return None, None

def log_environment():
    app.logger.info("Environment variables:")
    for key, value in os.environ.items():
        app.logger.info(f"{key}: {value}")
    
    app.logger.info("File system at /app/browsers:")
    for root, dirs, files in os.walk("/app/browsers"):
        for file in files:
            app.logger.info(os.path.join(root, file))

def install_playwright_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
        app.logger.info("Playwright browsers installed successfully")
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Failed to install Playwright browsers: {e}")
    except Exception as e:
        app.logger.error(f"Unexpected error during Playwright browser installation: {e}")

def get_playwright_executable_path():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        return p.chromium.executable_path

# Call this function at the start of your app
if __name__ == '__main__':
    install_playwright_browsers()
    log_environment()
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
