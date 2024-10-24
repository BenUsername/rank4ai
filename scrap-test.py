import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from bs4 import BeautifulSoup
import re
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TimeoutError, TCPTimedOutError

class LodgifySpider(scrapy.Spider):
    name = 'lodgify'
    start_urls = ['https://www.lodgify.com/']

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': False,
        'DOWNLOAD_DELAY': 3,
        'HTTPERROR_ALLOW_ALL': True,  # Allow the spider to process error responses
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, errback=self.errback_httpbin)

    def parse(self, response):
        if response.status == 403:
            self.logger.error(f"Access forbidden (403) on {response.url}")
            return

        # Extract the title
        title = response.css('title::text').get()
        
        # Extract the meta description
        description = response.css('meta[name="description"]::attr(content)').get()
        
        # Extract main content
        main_content = response.css('main::text').getall()
        if not main_content:
            main_content = response.css('body::text').getall()
        main_content = ' '.join(main_content).strip()
        
        # Clean up the content
        main_content = re.sub(r'\s+', ' ', main_content)
        
        # Generate a summary
        summary = self.generate_summary(title, description, main_content)
        
        # Print the summary to the console
        print("\n" + "="*50)
        print("Website Summary")
        print("="*50)
        print(f"Title: {title}")
        print(f"Description: {description}")
        print(f"Summary: {summary}")
        print("="*50 + "\n")

    def generate_summary(self, title, description, content):
        # Simple logic to generate a summary
        if description:
            return description
        elif len(content) > 200:
            return content[:200] + "..."
        else:
            return content

    def errback_httpbin(self, failure):
        # Log any errors
        self.logger.error(repr(failure))

        if failure.check(HttpError):
            response = failure.value.response
            self.logger.error(f"HttpError on {response.url}")
        elif failure.check(DNSLookupError):
            request = failure.request
            self.logger.error(f"DNSLookupError on {request.url}")
        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error(f"TimeoutError on {request.url}")

def run_spider():
    process = CrawlerProcess(get_project_settings())
    process.crawl(LodgifySpider)
    process.start()

if __name__ == "__main__":
    run_spider()
