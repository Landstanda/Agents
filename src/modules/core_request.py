#!/usr/bin/env python3

import aiohttp
import asyncio
import time
from typing import Dict, Any, Optional, Union, List
import json
import logging
from datetime import datetime, timedelta
import backoff
from cachetools import TTLCache
from ratelimit import limits, sleep_and_retry
from src.utils.logging import get_logger

logger = get_logger(__name__)

class CoreRequestError(Exception):
    """Custom exception for CoreRequestModule errors"""
    pass

class CoreRequestModule:
    """Module for handling all HTTP/HTTPS requests with advanced features"""
    
    def __init__(self, 
                 max_retries: int = 3,
                 rate_limit: int = 60,  # requests per minute
                 cache_ttl: int = 300,  # cache TTL in seconds
                 timeout: int = 30):    # request timeout in seconds
        """
        Initialize the request module
        
        Args:
            max_retries: Maximum number of retry attempts
            rate_limit: Maximum requests per minute
            cache_ttl: Cache time-to-live in seconds
            timeout: Request timeout in seconds
        """
        self.max_retries = max_retries
        self.rate_limit = rate_limit
        self.timeout = timeout
        
        # Initialize cache with TTL
        self.cache = TTLCache(maxsize=100, ttl=cache_ttl)
        
        # Initialize session
        self.session = None
        self.logger = logger
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    @sleep_and_retry
    @limits(calls=60, period=60)  # Default rate limit: 60 requests per minute
    @backoff.on_exception(backoff.expo,
                         (aiohttp.ClientError, asyncio.TimeoutError),
                         max_tries=3)
    async def request(self,
                     method: str,
                     url: str,
                     headers: Optional[Dict] = None,
                     params: Optional[Dict] = None,
                     data: Optional[Union[Dict, str]] = None,
                     json_data: Optional[Dict] = None,
                     use_cache: bool = True,
                     custom_retry: Optional[int] = None,
                     custom_timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Make an HTTP request with automatic retries, rate limiting, and caching
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            headers: Request headers
            params: URL parameters
            data: Form data or raw data
            json_data: JSON data
            use_cache: Whether to use caching for GET requests
            custom_retry: Override default retry count
            custom_timeout: Override default timeout
            
        Returns:
            Dict containing response data and metadata
            
        Raises:
            CoreRequestError: For request failures
        """
        method = method.upper()
        cache_key = f"{method}:{url}:{str(params)}:{str(headers)}"
        
        # Check cache for GET requests
        if method == "GET" and use_cache and cache_key in self.cache:
            self.logger.debug(f"Cache hit for {url}")
            return self.cache[cache_key]
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        timeout = custom_timeout or self.timeout
        retries = custom_retry or self.max_retries
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                
                # Check response status
                if response.status >= 400:
                    raise CoreRequestError(
                        f"Request failed with status {response.status}: {await response.text()}"
                    )
                
                # Parse response
                try:
                    result = {
                        'status': response.status,
                        'headers': dict(response.headers),
                        'data': await response.json(),
                        'timestamp': datetime.now().isoformat()
                    }
                except json.JSONDecodeError:
                    result = {
                        'status': response.status,
                        'headers': dict(response.headers),
                        'data': await response.text(),
                        'timestamp': datetime.now().isoformat()
                    }
                
                # Cache successful GET requests
                if method == "GET" and use_cache:
                    self.cache[cache_key] = result
                
                return result
                
        except asyncio.TimeoutError:
            self.logger.error(f"Request timeout for {url}")
            raise CoreRequestError(f"Request timeout after {timeout} seconds")
            
        except aiohttp.ClientError as e:
            self.logger.error(f"Request failed for {url}: {str(e)}")
            raise CoreRequestError(f"Request failed: {str(e)}")
    
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for GET requests"""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for POST requests"""
        return await self.request("POST", url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for PUT requests"""
        return await self.request("PUT", url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for DELETE requests"""
        return await self.request("DELETE", url, **kwargs)
    
    async def head(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for HEAD requests"""
        return await self.request("HEAD", url, **kwargs)
    
    def clear_cache(self):
        """Clear the request cache"""
        self.cache.clear()
    
    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self.cache)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'maxsize': self.cache.maxsize,
            'ttl': self.cache.ttl,
            'hits': getattr(self.cache, 'hits', 0),
            'misses': getattr(self.cache, 'misses', 0)
        } 