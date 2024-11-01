import os
from flask import Flask, request, render_template, session, jsonify, send_from_directory, redirect, url_for
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
from requests.exceptions import RequestException
import urllib3
import httpx
from pymongo import MongoClient
import stripe
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env file  
load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

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
MAX_INITIAL_SEARCHES = 3  # Searches before signup
MAX_FREE_SEARCHES_AFTER_SIGNUP = 3  # Additional searches after signup before subscription required

# Disable SSL warnings (use with caution)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# MongoDB setup
mongo_uri = os.getenv('MONGODB_URI')
if not mongo_uri:
    app.logger.error("No MongoDB URI found in environment variables")
    raise ValueError("MongoDB URI is required")

try:
    mongo_client = MongoClient(mongo_uri)
    # Explicitly specify the database name
    db = mongo_client['promptboostai']  # or any other database name you prefer
    requests_collection = db.requests
    users_collection = db.users  # Add this line
    app.logger.info("Successfully connected to MongoDB")
except Exception as e:
    app.logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise

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
        response = requests.get(base_url, headers=headers, timeout=requests_timeout, verify=False)
        response.raise_for_status()
        content = response.text[:MAX_HTML_SIZE]
        return process_content(content)  # Now returns 3 values
    except RequestException as e:
        app.logger.warning(f"HTTPS request failed for {domain}: {str(e)}")
        try:
            base_url = f"http://{domain}"
            response = requests.get(base_url, headers=headers, timeout=requests_timeout)
            response.raise_for_status()
            content = response.text[:MAX_HTML_SIZE]
            return process_content(content)  # Now returns 3 values
        except RequestException as e:
            app.logger.warning(f"HTTP request also failed for {domain}: {str(e)}")
            # Fallback using httpx
            return fetch_with_httpx(base_url)  # Already returns 3 values

def fetch_with_httpx(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        app.logger.info(f"Attempting httpx request for {url}")
        response = httpx.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        app.logger.info(f"Successfully got response from {url}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the title
        title = soup.title.string if soup.title else 'No title found'
        app.logger.info(f"Extracted title: {title}")
        
        # Extract the description
        description_tag = soup.find('meta', attrs={'name': 'description'})
        description = description_tag['content'] if description_tag else 'No description found'
        app.logger.info(f"Extracted description: {description}")
        
        # Extract main content
        main_content = soup.get_text(strip=True)
        
        # Create HTML-like content
        html_content = f'<html><head><title>{title}</title><meta name="description" content="{description}"></head><body>{main_content}</body></html>'
        
        return html_content, main_content, main_content
    except httpx.RequestError as e:
        app.logger.error(f"RequestError for {url}: {str(e)}")
        return "No content", "No content", "Failed to fetch content."
    except httpx.HTTPStatusError as e:
        app.logger.error(f"HTTPStatusError for {url}: {str(e)}")
        return "No content", "No content", "Failed to fetch content."
    except Exception as e:
        app.logger.error(f"Unexpected error for {url}: {str(e)}")
        return "No content", "No content", "Failed to fetch content."

def process_content(content):
    soup = BeautifulSoup(content, 'html.parser')
    main_content = soup.get_text(strip=True)
    return content, main_content, main_content  # Return three values consistently

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
            # Fallback using httpx
            title, description, main_content = fetch_with_httpx(url)
            if title and description:
                existing_content[url] = f"Title: {title}, Description: {description}, Content: {main_content}"

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
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract title
        title = soup.title.string if soup.title else 'No title found'
        app.logger.info(f"Found title: {title}")
        
        # Extract description
        description_tag = soup.find('meta', attrs={'name': 'description'})
        description = description_tag['content'] if description_tag else 'No description found'
        app.logger.info(f"Found description: {description}")
        
        # Extract main content
        main_content = soup.get_text(strip=True)
        
        return {
            'title': title,
            'description': description,
            'content': main_content
        }
    except Exception as e:
        app.logger.error(f"Error extracting main info: {e}")
        return {
            'title': 'No title available',
            'description': '',
            'content': ''
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

@app.route('/')
def index():
    searches_left = session.get('searches_left', MAX_SEARCHES_PER_SESSION)
    user_count = get_user_count()
    domain = request.args.get('domain')
    show_results = request.args.get('showResults')
    return render_template('index.html', 
                         searches_left=searches_left, 
                         user_count=user_count, 
                         domain=domain, 
                         show_results=show_results,
                         stripe_public_key=os.getenv('STRIPE_PUBLIC_KEY'),
                         current_user=current_user)  # Pass current_user explicitly

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

def find_latest_domain_analysis(domain):
    """
    Search for the most recent analysis of a domain in MongoDB
    """
    try:
        # Find most recent entry for this domain
        result = requests_collection.find_one(
            {"domain": domain},
            sort=[("timestamp", -1)]  # Most recent first
        )
        app.logger.info(f"Found database entry for {domain}: {result is not None}")
        return result
    except Exception as e:
        app.logger.error(f"Database query failed: {str(e)}")
        return None

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        domain = request.form['domain']
        if not is_valid_domain(domain):
            return jsonify({'error': 'Invalid domain'}), 400

        app.logger.info(f"Analyzing domain: {domain}")
        
        # Get user's search counts
        if current_user.is_authenticated:
            user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
            if user_data:
                if user_data.get('subscription_status') == 'active':
                    # Subscribed users get unlimited searches
                    pass
                else:
                    # Check free searches after signup
                    free_searches_left = user_data.get('free_searches_left', MAX_FREE_SEARCHES_AFTER_SIGNUP)
                    if free_searches_left <= 0:
                        return jsonify({
                            'error': 'subscription_required',
                            'message': 'Please upgrade to continue analyzing websites'
                        }), 403
                    users_collection.update_one(
                        {'_id': ObjectId(current_user.id)},
                        {'$set': {'free_searches_left': free_searches_left - 1}}
                    )
            else:
                # New authenticated user, initialize with free searches
                users_collection.update_one(
                    {'_id': ObjectId(current_user.id)},
                    {'$set': {'free_searches_left': MAX_FREE_SEARCHES_AFTER_SIGNUP - 1}},
                    upsert=True
                )
        else:
            # Check initial free searches for non-authenticated users
            searches_left = session.get('searches_left', MAX_INITIAL_SEARCHES)
            if searches_left <= 0:
                return jsonify({
                    'error': 'signup_required',
                    'message': 'Sign up to continue analyzing websites',
                    'preview_data': {
                        'domain': domain,
                        'score': 85
                    }
                }), 403
            session['searches_left'] = searches_left - 1

        # Get analysis results
        results = get_analysis_results(domain)
        
        # Add user status info to results
        if current_user.is_authenticated:
            user_data = users_collection.find_one({'_id': ObjectId(current_user.id)})
            results.update({
                'is_authenticated': True,
                'has_active_subscription': user_data.get('subscription_status') == 'active',
                'free_searches_left': user_data.get('free_searches_left', 0) if not user_data.get('subscription_status') == 'active' else 'unlimited'
            })
        else:
            results.update({
                'is_authenticated': False,
                'has_active_subscription': False,
                'searches_left': session.get('searches_left', 0)
            })
        
        return jsonify(results)
        
    except Exception as e:
        app.logger.error(f"Error analyzing domain: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
        logging.info(f"Analyzing content for {domain}")
        _, main_content, _ = fetch_main_page_content(domain)
        
        if not main_content:
            logging.error(f"Failed to fetch content for {domain}")
            return {"error": "Failed to fetch content for analysis. Please try again later."}

        total_content = main_content[:1000]

        system_message = "You are an expert in content strategy and LLM optimization."
        user_message = f"""
        Based on the following content from {domain}, provide 3 strategic recommendations to help them appear more frequently in LLM responses for the prompt: "{prompt}"

        Existing content:
        {total_content}

        Format your response as a JSON object with a single key: 'recommendations'.
        Each recommendation should include:
        1. 'type': One of ['content_update', 'new_content', 'technical']
        2. 'title': A brief title for the recommendation
        3. 'description': Detailed explanation of the recommendation
        4. 'implementation': Step-by-step guide to implement the recommendation
        5. 'score_impact': A number between 1 and 15 representing the estimated score increase
            - 1-5: Minor improvement
            - 6-10: Moderate improvement
            - 11-15: Major improvement
        Base the score_impact on:
        - How much the recommendation would improve visibility in LLM responses
        - How much it would help rank higher in those responses
        - The effort vs impact ratio
        
        Ensure one recommendation is of type 'new_content' suggesting a new blog post or content piece.
        Make recommendations highly specific to their business and the given prompt.
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
        recommendations = json.loads(content)

        # Store recommendations in MongoDB
        store_recommendations(domain, prompt, recommendations['recommendations'])

        return recommendations

    except Exception as e:
        app.logger.error(f"Error generating advice: {str(e)}", exc_info=True)
        return {"error": f"An error occurred while generating advice: {str(e)}. Please try again later."}

def store_recommendations(domain, prompt, recommendations):
    try:
        document = {
            "timestamp": datetime.utcnow(),
            "domain": domain,
            "prompt": prompt,
            "recommendations": recommendations
        }
        
        # Update existing document or create new one
        result = requests_collection.update_one(
            {
                "domain": domain,
                "prompt": prompt,
                "timestamp": {
                    "$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                }
            },
            {"$set": {"recommendations": recommendations}},
            upsert=True
        )
        
        app.logger.info(f"Stored/updated recommendations: {result.modified_count} documents modified")
    except Exception as e:
        app.logger.error(f"Failed to store recommendations: {str(e)}")

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

def store_analysis_result(domain, title, description, prompts, table, score):
    try:
        # Prepare the document
        document = {
            "timestamp": datetime.utcnow(),
            "request_info": {
                "user_agent": request.headers.get('User-Agent'),
                "ip_address": request.remote_addr
            },
            "domain": domain,
            "title": title,
            "description": description,
            "marketing_prompts": [
                {
                    "prompt": row['prompt'],
                    "answer": row['answer'],
                    "competitors": row['competitors'].split(', ') if isinstance(row['competitors'], str) else row['competitors'],
                    "visible": row['visible']
                } for row in table
            ],
            "score": score
        }
        
        # Insert into MongoDB
        result = requests_collection.insert_one(document)
        app.logger.info(f"Stored analysis result with ID: {result.inserted_id}")
        return str(result.inserted_id)
    except Exception as e:
        app.logger.error(f"Failed to store analysis result: {str(e)}")
        # Don't raise the exception - we don't want to break the main functionality
        return None

def store_blog_suggestions(domain, blog_suggestions):
    try:
        # Find the existing document for this domain
        result = requests_collection.update_one(
            {"domain": domain, "timestamp": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}},
            {"$set": {"blog_suggestions": blog_suggestions}},
            upsert=False
        )
        app.logger.info(f"Updated {result.modified_count} documents with blog suggestions")
    except Exception as e:
        app.logger.error(f"Failed to store blog suggestions: {str(e)}")

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

def analyze_competitor(competitor_domain, prompt, llm_response):
    try:
        # Fetch competitor content
        _, competitor_content, _ = fetch_main_page_content(competitor_domain)
        
        # Ask LLM to analyze why this competitor was mentioned
        analysis_prompt = f"""
        Based on this competitor's content and how they were mentioned in the response,
        identify the SINGLE MOST IMPORTANT factor why {competitor_domain} was included.
        
        Competitor content: {competitor_content[:1000]}
        Original prompt: {prompt}
        How they were mentioned: {llm_response}
        
        Return ONLY a brief one-line explanation (max 50 chars).
        Format: Key factor: [explanation]
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert in competitive analysis."},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=60,
            temperature=0.3
        )
        
        analysis = response.choices[0].message.content.strip()
        
        # Store in MongoDB
        store_competitor_analysis(competitor_domain, prompt, analysis)
        
        return analysis
    except Exception as e:
        app.logger.error(f"Error analyzing competitor: {str(e)}")
        return "Analysis unavailable"

def store_competitor_analysis(competitor_domain, prompt, analysis):
    try:
        document = {
            "timestamp": datetime.utcnow(),
            "competitor_domain": competitor_domain,
            "prompt": prompt,
            "analysis": analysis
        }
        
        # Update existing analysis or create new one
        result = requests_collection.update_one(
            {
                "competitor_domain": competitor_domain,
                "prompt": prompt,
                "timestamp": {
                    "$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                }
            },
            {"$set": {"analysis": analysis}},
            upsert=True
        )
        
        app.logger.info(f"Stored competitor analysis: {result.modified_count} documents modified")
    except Exception as e:
        app.logger.error(f"Failed to store competitor analysis: {str(e)}")

@app.route('/analyze_competitor', methods=['POST'])
def analyze_competitor_route():
    data = request.json
    competitor = data.get('competitor')
    prompt = data.get('prompt')
    
    if not competitor or not prompt:
        return jsonify({'error': 'Competitor and prompt are required'}), 400
        
    try:
        # More flexible query to find the original response
        original_response = requests_collection.find_one(
            {
                "$or": [
                    # Check in marketing_prompts array
                    {
                        "marketing_prompts": {
                            "$elemMatch": {
                                "prompt": prompt,
                                "$or": [
                                    {"competitors": {"$in": [competitor]}},
                                    {"competitors": competitor},  # Handle case where competitors is a string
                                    {"competitors": {"$regex": competitor}}  # Handle case where competitor is part of a string
                                ]
                            }
                        }
                    },
                    # Check in the root level (for older documents)
                    {
                        "prompt": prompt,
                        "$or": [
                            {"competitors": {"$in": [competitor]}},
                            {"competitors": competitor},
                            {"competitors": {"$regex": competitor}}
                        ]
                    }
                ]
            },
            {
                "marketing_prompts": 1,
                "answer": 1  # Include answer field for older documents
            }
        )
        
        app.logger.info(f"Found document for {competitor} and prompt '{prompt}': {original_response is not None}")
        
        if not original_response:
            app.logger.warning(f"No document found for competitor {competitor} and prompt '{prompt}'")
            # Fallback: analyze without original response context
            analysis = analyze_competitor(competitor, prompt, f"Analysis for prompt: {prompt}")
            return jsonify({'analysis': analysis})
            
        # Extract the response text, handling different document structures
        if 'marketing_prompts' in original_response and original_response['marketing_prompts']:
            for prompt_data in original_response['marketing_prompts']:
                if prompt_data['prompt'] == prompt:
                    llm_response = prompt_data['answer']
                    break
            else:
                llm_response = original_response['marketing_prompts'][0]['answer']
        else:
            llm_response = original_response.get('answer', f"Analysis for prompt: {prompt}")
        
        analysis = analyze_competitor(competitor, prompt, llm_response)
        return jsonify({'analysis': analysis})
        
    except Exception as e:
        app.logger.error(f"Error in analyze_competitor route: {str(e)}", exc_info=True)
        # Fallback: return a basic analysis
        try:
            basic_analysis = analyze_competitor(competitor, prompt, f"Analysis for prompt: {prompt}")
            return jsonify({'analysis': basic_analysis})
        except Exception as e2:
            app.logger.error(f"Error in fallback analysis: {str(e2)}", exc_info=True)
            return jsonify({'error': "Could not analyze competitor at this time"}), 500

@app.route('/subscribe', methods=['POST'])
def subscribe():
    try:
        data = request.json
        plan = data.get('plan')
        
        price_id = os.getenv(f'STRIPE_PRICE_ID_{plan.upper()}')
        
        if not price_id:
            raise ValueError(f"No price ID found for plan: {plan}")
            
        app.logger.info(f"Creating checkout session for plan {plan} with price ID {price_id}")
        
        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.host_url + 'success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'cancel',
            metadata={
                'plan': plan
            }
        )
        
        return jsonify({'sessionId': session.id})
    except Exception as e:
        app.logger.error(f"Error creating subscription: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/success')
def success():
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('index'))

    try:
        # Retrieve the session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Store user and subscription info in MongoDB
        user_data = {
            "customer_id": checkout_session.customer,
            "subscription_id": checkout_session.subscription,
            "email": checkout_session.customer_details.email,
            "subscription_status": "active",
            "plan": checkout_session.metadata.get('plan', 'monthly'),  # Default to monthly if not specified
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Store in MongoDB, using email as unique identifier
        users_collection.update_one(
            {"email": user_data["email"]},
            {"$set": user_data},
            upsert=True
        )
        
        # Store subscription info in session
        session['user_email'] = user_data["email"]
        session['is_subscriber'] = True
        
        return render_template('success.html', email=user_data["email"])
    except Exception as e:
        app.logger.error(f"Error processing successful subscription: {str(e)}")
        return redirect(url_for('index'))

# Add a function to check subscription status
def check_subscription_status():
    user_email = session.get('user_email')
    if not user_email:
        return False
        
    user = users_collection.find_one({"email": user_email})
    if not user:
        return False
        
    if user.get('subscription_status') != 'active':
        return False
        
    return True

# Add webhook handling for subscription updates
@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError as e:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400

    if event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        update_subscription_status(subscription)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        cancel_subscription(subscription)

    return jsonify({'status': 'success'})

def update_subscription_status(subscription):
    customer_id = subscription['customer']
    status = subscription['status']
    
    users_collection.update_one(
        {"customer_id": customer_id},
        {
            "$set": {
                "subscription_status": status,
                "updated_at": datetime.utcnow()
            }
        }
    )

def cancel_subscription(subscription):
    customer_id = subscription['customer']
    
    users_collection.update_one(
        {"customer_id": customer_id},
        {
            "$set": {
                "subscription_status": "canceled",
                "updated_at": datetime.utcnow()
            }
        }
    )

def get_analysis_results(domain):
    try:
        app.logger.info(f"Getting analysis results for {domain}")
        
        # Get main content
        html_content, main_content, full_content = fetch_main_page_content(domain)
        if not html_content:
            raise Exception("Failed to fetch content")

        # Extract main info
        info = extract_main_info(html_content)
        
        # Get existing content
        existing_content = fetch_additional_content(domain)
        
        # Generate marketing prompts
        prompts = generate_marketing_prompts(info['title'], info['description'], full_content, domain)
        if not prompts:
            raise Exception("Couldn't generate valid prompts")
        
        # Generate prompt answers
        table = generate_prompt_answers(prompts, domain, info, existing_content)
        
        # Calculate score
        score = calculate_score(table, full_content)
        
        # Store results
        store_analysis_result(domain, info['title'], info['description'], prompts, table, score)
        
        return {
            'domain': domain,
            'info': info,
            'prompts': prompts,
            'table': table,
            'logo_url': get_logo_dev_logo(domain),
            'score': score,
            'from_cache': False
        }
        
    except Exception as e:
        app.logger.error(f"Error getting analysis results: {str(e)}")
        raise

# Add near the top after Flask initialization
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.email = user_data['email']
        self.subscription_status = user_data.get('subscription_status', 'free')

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
        
    # Check if user already exists
    if users_collection.find_one({"email": email}):
        return jsonify({'error': 'Email already registered'}), 400
        
    # Create new user with free searches
    user_data = {
        "email": email,
        "password": generate_password_hash(password),
        "subscription_status": "free",
        "free_searches_left": MAX_FREE_SEARCHES_AFTER_SIGNUP,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    try:
        result = users_collection.insert_one(user_data)
        user = User(user_data)
        login_user(user)
        return jsonify({'message': 'Signup successful'}), 200
    except Exception as e:
        app.logger.error(f"Error creating user: {str(e)}")
        return jsonify({'error': 'Error creating user'}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
        
    user_data = users_collection.find_one({"email": email})
    if not user_data or not check_password_hash(user_data['password'], password):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Initialize free searches if not set
    if 'free_searches_left' not in user_data:
        users_collection.update_one(
            {"_id": user_data['_id']},
            {"$set": {
                "free_searches_left": MAX_FREE_SEARCHES_AFTER_SIGNUP,
                "subscription_status": user_data.get('subscription_status', 'free')
            }}
        )
        user_data['free_searches_left'] = MAX_FREE_SEARCHES_AFTER_SIGNUP
        
    user = User(user_data)
    login_user(user)
    return jsonify({'message': 'Login successful'}), 200

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)

