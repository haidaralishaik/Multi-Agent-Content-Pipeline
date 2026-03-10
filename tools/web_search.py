"""
Web Search Tool - DuckDuckGo-powered web search (free, no API key required)

Used by the pipeline to gather real search results
before the Researcher agent runs.
"""

from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Real web search using DuckDuckGo (free, no API key needed).

    Returns clean, structured results compatible with the original
    Tavily-based interface.
    """

    def __init__(self):
        self.search_count = 0
        logger.info("WebSearch initialized (DuckDuckGo)")

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search the web using DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of dicts with title, snippet, url, source
        """
        from ddgs import DDGS

        self.search_count += 1
        logger.info(f"Web search #{self.search_count}: {query}")

        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))

            results = []
            for r in raw_results:
                url = r.get('href', '')
                try:
                    source = url.split('/')[2] if url else 'unknown'
                except IndexError:
                    source = 'unknown'

                results.append({
                    'title': r.get('title', ''),
                    'snippet': r.get('body', ''),
                    'url': url,
                    'source': source,
                })

            logger.info(f"Found {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.warning(f"Web search failed: {e}. Returning empty results.")
            return [{
                'title': 'Search unavailable',
                'snippet': f'Web search failed: {str(e)}. The researcher will use its training data.',
                'url': '',
                'source': 'error',
            }]


# Example usage
if __name__ == "__main__":
    search = WebSearchTool()
    results = search.search("Recent advances in RAG systems")
    print(f"Found {len(results)} results:")
    for r in results:
        print(f"\n  Title: {r['title']}")
        print(f"  URL: {r['url']}")
        print(f"  Snippet: {r['snippet'][:120]}...")
