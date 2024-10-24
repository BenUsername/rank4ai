import asyncio
from crawl4ai import AsyncWebCrawler

async def analyze_website(url):
    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(url=url)
        
        if result.success:
            print(f"Analysis of {url}:")
            
            if hasattr(result, 'markdown'):
                print("\nContent summary (from markdown):")
                print(result.markdown[:1000] + "..." if len(result.markdown) > 1000 else result.markdown)
            else:
                print("\nNo markdown content found. Available attributes:")
                for attr in dir(result):
                    if not attr.startswith('_'):
                        print(f"- {attr}")
        else:
            print(f"Failed to fetch content from {url}")

async def main():
    url = "https://www.lodgify.com/"
    await analyze_website(url)

if __name__ == "__main__":
    asyncio.run(main())
