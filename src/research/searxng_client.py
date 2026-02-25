"""
SearXNG Client - Self-Hosted Search Engine Interface
====================================================

This module provides a Python client for interacting with SearXNG,
a privacy-respecting metasearch engine that aggregates results from
multiple search engines (Google, Bing, DuckDuckGo, etc.).

Features:
- Simple API for searching with JSON results
- Error handling and retry logic
- Connection pooling for performance
- Support for multiple search parameters
- Low overhead (~10-20MB RAM for client)

SearXNG Setup:
- Run scripts/setup_searxng.sh to install
- Uses ~150-200MB RAM (Docker container)
- Runs on http://localhost:8888

Author: Auto-Git Project
License: MIT
"""

import requests
from typing import List, Dict, Any, Optional
import time
import logging
from urllib.parse import urlencode, quote_plus


class SearXNGClient:
    """
    Client for interacting with SearXNG search engine.
    
    This client provides methods to search using SearXNG's JSON API
    and handles connection errors, retries, and result parsing.
    
    Attributes:
        base_url (str): Base URL of SearXNG instance
        timeout (int): Request timeout in seconds
        max_retries (int): Maximum number of retry attempts
        session (requests.Session): Persistent session for connection pooling
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8888",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize SearXNG client.
        
        Args:
            base_url: Base URL of SearXNG instance (default: http://localhost:8888)
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum retry attempts on failure (default: 3)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Create persistent session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AutoGit-SearXNG-Client/1.0',
            'Accept': 'application/json'
        })
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
    def search(
        self,
        query: str,
        num_results: int = 10,
        categories: Optional[str] = None,
        engines: Optional[str] = None,
        language: str = "en",
        time_range: Optional[str] = None,
        safe_search: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search using SearXNG and return parsed results.
        
        Args:
            query: Search query string
            num_results: Maximum number of results to return (default: 10)
            categories: Comma-separated categories (e.g., "general,it")
            engines: Comma-separated engines (e.g., "google,bing")
            language: Language code (default: "en")
            time_range: Time range filter ("day", "week", "month", "year")
            safe_search: Safe search level (0=off, 1=moderate, 2=strict)
            
        Returns:
            List of result dictionaries with keys: title, url, content, engine
            
        Raises:
            ConnectionError: If unable to connect to SearXNG
            ValueError: If query is empty or invalid
            
        Example:
            >>> client = SearXNGClient()
            >>> results = client.search("Python web scraping", num_results=5)
            >>> for result in results:
            ...     print(f"{result['title']}: {result['url']}")
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")
            
        # Get raw JSON response
        response_data = self.search_json(
            query=query,
            categories=categories,
            engines=engines,
            language=language,
            time_range=time_range,
            safe_search=safe_search
        )
        
        # Parse and format results
        results = []
        raw_results = response_data.get('results', [])
        
        for item in raw_results[:num_results]:
            result = {
                'title': item.get('title', 'No title'),
                'url': item.get('url', ''),
                'content': item.get('content', ''),
                'engine': item.get('engine', 'unknown'),
                'score': item.get('score', 0.0),
                'category': item.get('category', 'general')
            }
            results.append(result)
            
        self.logger.info(f"Search '{query}' returned {len(results)} results")
        return results
        
    def search_json(
        self,
        query: str,
        categories: Optional[str] = None,
        engines: Optional[str] = None,
        language: str = "en",
        time_range: Optional[str] = None,
        safe_search: int = 0
    ) -> Dict[str, Any]:
        """
        Search using SearXNG and return raw JSON response.
        
        Args:
            query: Search query string
            categories: Comma-separated categories
            engines: Comma-separated engines
            language: Language code
            time_range: Time range filter
            safe_search: Safe search level (0-2)
            
        Returns:
            Raw JSON response as dictionary
            
        Raises:
            ConnectionError: If unable to connect to SearXNG
            
        Example:
            >>> client = SearXNGClient()
            >>> data = client.search_json("artificial intelligence")
            >>> print(f"Found {len(data['results'])} results")
        """
        # Build query parameters
        params = {
            'q': query,
            'format': 'json',
            'language': language,
            'safesearch': safe_search
        }
        
        if categories:
            params['categories'] = categories
        if engines:
            params['engines'] = engines
        if time_range:
            params['time_range'] = time_range
            
        # Construct URL
        url = f"{self.base_url}/search"
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Search attempt {attempt + 1}/{self.max_retries}: {query}")
                
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()
                
                return response.json()
                
            except requests.exceptions.ConnectionError as e:
                last_error = e
                # Connection refused = server not running; no point retrying
                if "actively refused" in str(e) or "Connection refused" in str(e):
                    self.logger.warning(f"SearXNG not running at {self.base_url} \u2014 skipping (WinError 10061)")
                    break
                self.logger.warning(f"Connection error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
            except requests.exceptions.Timeout as e:
                last_error = e
                self.logger.warning(f"Timeout error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.HTTPError as e:
                last_error = e
                self.logger.error(f"HTTP error: {e}")
                # Don't retry on HTTP errors (4xx, 5xx)
                break
                
            except Exception as e:
                last_error = e
                self.logger.error(f"Unexpected error: {e}")
                break
                
        # All retries failed
        error_msg = f"Failed to connect to SearXNG at {self.base_url}: {last_error}"
        self.logger.error(error_msg)
        raise ConnectionError(error_msg)
        
    def is_available(self) -> bool:
        """
        Check if SearXNG service is available.
        
        Returns:
            True if service is reachable, False otherwise
            
        Example:
            >>> client = SearXNGClient()
            >>> if client.is_available():
            ...     print("SearXNG is ready")
            ... else:
            ...     print("SearXNG is not running")
        """
        try:
            response = self.session.get(
                self.base_url,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.debug(f"Availability check failed: {e}")
            return False
            
    def get_engines(self) -> List[str]:
        """
        Get list of available search engines.
        
        Returns:
            List of engine names
            
        Note:
            This requires SearXNG to be running
        """
        try:
            # Try to get preferences page which lists engines
            response = self.session.get(
                f"{self.base_url}/preferences",
                timeout=5
            )
            # This is a simplification - actual implementation would parse HTML
            # For now, return common engines
            return [
                'google', 'bing', 'duckduckgo', 'wikipedia',
                'github', 'stackoverflow', 'arxiv'
            ]
        except Exception as e:
            self.logger.debug(f"Failed to get engines: {e}")
            return []
            
    def search_specific_engine(
        self,
        query: str,
        engine: str,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search using a specific engine only.
        
        Args:
            query: Search query
            engine: Engine name (e.g., 'google', 'bing', 'github')
            num_results: Maximum results to return
            
        Returns:
            List of search results
            
        Example:
            >>> client = SearXNGClient()
            >>> results = client.search_specific_engine("Python", "github")
        """
        return self.search(
            query=query,
            num_results=num_results,
            engines=engine
        )
        
    def search_code(
        self,
        query: str,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for code examples using programming-focused engines.
        
        Args:
            query: Code search query
            num_results: Maximum results
            
        Returns:
            List of code-related results
        """
        return self.search(
            query=query,
            num_results=num_results,
            categories="it",
            engines="github,stackoverflow"
        )
        
    def search_papers(
        self,
        query: str,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for academic papers using scientific engines.
        
        Args:
            query: Research query
            num_results: Maximum results
            
        Returns:
            List of academic results
        """
        return self.search(
            query=query,
            num_results=num_results,
            categories="science",
            engines="arxiv,google"
        )
        
    def close(self):
        """Close the session and cleanup resources."""
        self.session.close()
        
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Example usage and testing
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("SearXNG Client Test")
    print("=" * 60)
    print()
    
    # Initialize client
    client = SearXNGClient()
    
    # Check availability
    print("Checking SearXNG availability...")
    if client.is_available():
        print("✓ SearXNG is running!")
    else:
        print("✗ SearXNG is not running")
        print("Run: bash scripts/setup_searxng.sh")
        exit(1)
        
    print()
    print("-" * 60)
    print("Test 1: Search for 'Python web scraping'")
    print("-" * 60)
    
    try:
        results = client.search("Python web scraping", num_results=3)
        
        print(f"\nFound {len(results)} results:\n")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['title']}")
            print(f"   URL: {result['url']}")
            print(f"   Engine: {result['engine']}")
            print(f"   Preview: {result['content'][:100]}...")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        
    print("-" * 60)
    print("Test 2: Search GitHub for 'langchain python'")
    print("-" * 60)
    
    try:
        results = client.search_code("langchain python", num_results=3)
        
        print(f"\nFound {len(results)} code results:\n")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['title']}")
            print(f"   URL: {result['url']}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        
    print("-" * 60)
    print("Test 3: Search papers for 'machine learning transformers'")
    print("-" * 60)
    
    try:
        results = client.search_papers("machine learning transformers", num_results=3)
        
        print(f"\nFound {len(results)} academic results:\n")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['title']}")
            print(f"   URL: {result['url']}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        
    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)
    
    # Cleanup
    client.close()
