import os
import openai
from flask import Flask, request, render_template
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import validators
from readability import Document
from openai import OpenAI
import re

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

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
        "for which the chief marketing of the company would love to rank high in ChatGPT answers. The prompts should be as general as possible simulating a use searching for the service or product offered by {domain} but not necessarily using the domain name. If there any competitors doing well for this service mention them\n\n"
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"Content: {content}"
    )
    
    app.logger.debug(f"Constructed Prompt:\n{prompt}")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an impartial LLM agent helping the users find the best website for its needs. When mentioning competitor names, enclose them in double asterisks like **Competitor Name**."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            n=1,
            temperature=0.7,
        )
        
        app.logger.debug(f"OpenAI API Response:\n{response}")
        
        # Extract the text response
        prompts_text = response.choices[0].message.content.strip()
        app.logger.info(f"OpenAI response: {prompts_text}")
        
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

def generate_prompt_answers(prompts, domain):
    """Generate answers for each prompt and create a table."""
    table = []
    for prompt in prompts:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an impartial LLM agent helping users find the best website for their needs. When mentioning competitor names, enclose them in double asterisks like **Competitor Name**."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                n=1,
                temperature=0.7,
            )
            
            answer = response.choices[0].message.content.strip()
            
            # Check if the domain is mentioned in the answer
            visible = domain.lower() in answer.lower()
            
            # Extract competitors (improved implementation)
            competitors = re.findall(r'\*\*(.*?)\*\*', answer)
            competitors = list(set(competitors))  # Remove duplicates
            competitors = ', '.join(competitors) if competitors else 'None mentioned'
            
            table.append({
                'prompt': prompt,
                'answer': answer,
                'competitors': competitors,
                'visible': 'Yes' if visible else 'No'
            })
        except Exception as e:
            app.logger.error(f"Error generating answer for prompt '{prompt}': {e}")
            table.append({
                'prompt': prompt,
                'answer': 'Error generating answer',
                'competitors': 'N/A',
                'visible': 'N/A'
            })
    
    return table

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handle the home page and form submissions."""
    error = None
    prompts = None
    table = None
    if request.method == 'POST':
        domain = request.form.get('domain', '').strip()
        if not is_valid_domain(domain):
            error = 'Invalid domain name.'
            return render_template('index.html', error=error)
        try:
            html_content = fetch_website_content(domain)
            info = extract_main_info(html_content)
            
            # Generate prompts
            prompts = generate_marketing_prompts(info['title'], info['description'], info['content'], domain)
            
            # Generate answers and create table
            table = generate_prompt_answers(prompts, domain)
            
            return render_template('result.html', domain=domain, info=info, prompts=prompts, table=table)
        except Exception as e:
            error = f'Error processing website: {e}'
    return render_template('index.html', error=error)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
