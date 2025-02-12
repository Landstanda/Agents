#!/usr/bin/env python3

import pytest
import asyncio
import aiohttp
from src.modules.core_request import CoreRequestModule, CoreRequestError
import json
from datetime import datetime, timedelta
import time
from pytest_asyncio import fixture

@fixture
async def request_module():
    module = CoreRequestModule()
    await module.__aenter__()
    yield module
    await module.__aexit__(None, None, None)

@pytest.mark.asyncio
async def test_init():
    """Test module initialization"""
    module = CoreRequestModule(
        max_retries=5,
        rate_limit=30,
        cache_ttl=600,
        timeout=45
    )
    assert module.max_retries == 5
    assert module.rate_limit == 30
    assert module.timeout == 45
    assert module.cache.ttl == 600

@pytest.mark.asyncio
async def test_get_request(request_module):
    """Test basic GET request"""
    response = await request_module.get("https://httpbin.org/get")
    assert response['status'] == 200
    assert 'data' in response
    assert 'headers' in response
    assert 'timestamp' in response

@pytest.mark.asyncio
async def test_post_request(request_module):
    """Test POST request with data"""
    test_data = {"key": "value"}
    response = await request_module.post(
        "https://httpbin.org/post",
        json_data=test_data
    )
    assert response['status'] == 200
    assert json.loads(response['data']['data']) == test_data

@pytest.mark.asyncio
async def test_request_with_params(request_module):
    """Test request with URL parameters"""
    params = {'param1': 'value1', 'param2': 'value2'}
    response = await request_module.get(
        "https://httpbin.org/get",
        params=params
    )
    assert response['status'] == 200
    assert response['data']['args'] == params

@pytest.mark.asyncio
async def test_request_with_headers(request_module):
    """Test request with custom headers"""
    headers = {'X-Custom-Header': 'test-value'}
    response = await request_module.get(
        "https://httpbin.org/headers",
        headers=headers
    )
    assert response['status'] == 200
    assert 'X-Custom-Header' in response['data']['headers']
    assert response['data']['headers']['X-Custom-Header'] == 'test-value'

@pytest.mark.asyncio
async def test_cache_functionality(request_module):
    """Test request caching"""
    url = "https://httpbin.org/get"
    
    # First request
    response1 = await request_module.get(url)
    time1 = response1['timestamp']
    
    # Second request (should be cached)
    response2 = await request_module.get(url)
    time2 = response2['timestamp']
    
    assert time1 == time2  # Timestamps should be identical for cached response
    assert request_module.get_cache_size() > 0

@pytest.mark.asyncio
async def test_cache_control(request_module):
    """Test cache control"""
    url = "https://httpbin.org/get"
    
    # Request with cache
    response1 = await request_module.get(url, use_cache=True)
    
    # Request without cache
    response2 = await request_module.get(url, use_cache=False)
    
    assert response1['timestamp'] != response2['timestamp']

@pytest.mark.asyncio
async def test_rate_limiting(request_module):
    """Test rate limiting"""
    start_time = time.time()
    
    # Make multiple requests quickly
    urls = ["https://httpbin.org/get"] * 5
    responses = await asyncio.gather(
        *[request_module.get(url) for url in urls]
    )
    
    end_time = time.time()
    duration = end_time - start_time
    
    assert all(r['status'] == 200 for r in responses)
    assert len(responses) == 5

@pytest.mark.asyncio
async def test_error_handling(request_module):
    """Test error handling"""
    with pytest.raises(CoreRequestError):
        await request_module.get("https://httpbin.org/status/404")

@pytest.mark.asyncio
async def test_timeout_handling(request_module):
    """Test timeout handling"""
    with pytest.raises(CoreRequestError):
        await request_module.get(
            "https://httpbin.org/delay/10",
            custom_timeout=1
        )

@pytest.mark.asyncio
async def test_retry_mechanism(request_module):
    """Test retry mechanism"""
    # Use an endpoint that returns JSON
    url = "https://httpbin.org/json"
    response = await request_module.get(url)
    assert response['status'] == 200
    assert isinstance(response['data'], dict)

@pytest.mark.asyncio
async def test_cache_stats(request_module):
    """Test cache statistics"""
    url = "https://httpbin.org/get"
    
    # Make some requests to generate cache stats
    await request_module.get(url)
    await request_module.get(url)
    
    stats = request_module.get_cache_stats()
    assert 'size' in stats
    assert 'maxsize' in stats
    assert 'ttl' in stats
    assert 'hits' in stats
    assert 'misses' in stats

@pytest.mark.asyncio
async def test_clear_cache(request_module):
    """Test cache clearing"""
    url = "https://httpbin.org/get"
    
    # Make a request to populate cache
    await request_module.get(url)
    assert request_module.get_cache_size() > 0
    
    # Clear cache
    request_module.clear_cache()
    assert request_module.get_cache_size() == 0 