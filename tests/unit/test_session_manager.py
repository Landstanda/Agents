#!/usr/bin/env python3

import pytest
import asyncio
from datetime import datetime, timedelta
from src.modules.session_manager import SessionManagerModule, Session, SessionManagerError
from pytest_asyncio import fixture

@fixture
async def session_manager():
    async with SessionManagerModule(session_timeout=3600, max_sessions=5) as manager:
        yield manager

@pytest.mark.asyncio
async def test_init():
    """Test module initialization"""
    manager = SessionManagerModule(session_timeout=1800, max_sessions=10)
    assert manager.session_timeout == 1800
    assert manager.max_sessions == 10
    assert len(manager.sessions) == 0

@pytest.mark.asyncio
async def test_create_session(session_manager):
    """Test session creation"""
    session = await session_manager.create_session("https://httpbin.org/get")
    assert session.domain == "httpbin.org/get"
    assert isinstance(session.cookies, dict)
    assert not session.is_authenticated
    assert session.auth_token is None

@pytest.mark.asyncio
async def test_get_session(session_manager):
    """Test getting existing session"""
    # Create initial session
    url = "https://httpbin.org/get"
    session1 = await session_manager.create_session(url)
    
    # Get same session
    session2 = await session_manager.get_session(url)
    assert session1.domain == session2.domain
    assert session1.cookies == session2.cookies

@pytest.mark.asyncio
async def test_session_expiry(session_manager):
    """Test session expiration"""
    url = "https://httpbin.org/get"
    session = await session_manager.create_session(url)
    session.expiry = datetime.now() - timedelta(hours=1)  # Set to expired
    
    # Should create new session when getting expired one
    new_session = await session_manager.get_session(url)
    assert new_session != session
    assert not new_session.is_expired()

@pytest.mark.asyncio
async def test_max_sessions(session_manager):
    """Test maximum session limit"""
    # Create max_sessions + 1 sessions
    base_url = "https://httpbin.org"
    for i in range(session_manager.max_sessions + 1):
        url = f"{base_url}/get?id={i}"
        await session_manager.create_session(url)
    
    # Should have exactly max_sessions sessions
    assert len(session_manager.sessions) == 1  # All requests go to same domain

@pytest.mark.asyncio
async def test_authentication(session_manager):
    """Test session authentication"""
    url = "https://httpbin.org/get"  # Using get endpoint for initial session
    auth_url = "https://httpbin.org/post"  # Using post endpoint for auth
    auth_data = {"username": "test", "password": "test123"}

    session = await session_manager.get_session(url)
    session = await session_manager.authenticate(auth_url, auth_data)

    assert session.is_authenticated
    assert session.domain == "httpbin.org"

@pytest.mark.asyncio
async def test_make_request(session_manager):
    """Test making request with session"""
    url = "https://httpbin.org/get"
    session = await session_manager.create_session(url)
    
    # Make request with session
    response = await session_manager.make_request("GET", url, session=session)
    assert response['status'] == 200
    assert 'data' in response

@pytest.mark.asyncio
async def test_clear_session(session_manager):
    """Test clearing specific session"""
    url = "https://httpbin.org/get"
    await session_manager.create_session(url)
    
    # Clear session
    session_manager.clear_session(url)
    assert "httpbin.org" not in session_manager.sessions

@pytest.mark.asyncio
async def test_clear_all_sessions(session_manager):
    """Test clearing all sessions"""
    # Create multiple sessions
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/get?test=1"
    ]
    for url in urls:
        await session_manager.create_session(url)
    
    # Clear all sessions
    session_manager.clear_all_sessions()
    assert len(session_manager.sessions) == 0

@pytest.mark.asyncio
async def test_get_active_sessions(session_manager):
    """Test getting active sessions"""
    # Create mix of active and expired sessions
    url1 = "https://httpbin.org/get"
    url2 = "https://httpbin.org/post"  # Use different path

    session1 = await session_manager.create_session(url1)
    session2 = await session_manager.create_session(url2)
    session2.expiry = datetime.now() - timedelta(hours=1)  # Set to expired
    
    active_sessions = session_manager.get_active_sessions()
    assert len(active_sessions) == 1
    assert active_sessions[0].domain == "httpbin.org/get"

@pytest.mark.asyncio
async def test_session_stats(session_manager):
    """Test session statistics"""
    # Create mix of sessions
    url1 = "https://httpbin.org/get"
    url2 = "https://httpbin.org/post"  # Use different path

    session1 = await session_manager.create_session(url1)
    session2 = await session_manager.create_session(url2)
    session1.is_authenticated = True
    
    stats = session_manager.get_session_stats()
    assert stats['total_sessions'] == 2  # Sessions are for different paths
    assert stats['active_sessions'] == 2
    assert stats['authenticated_sessions'] == 1
    assert stats['oldest_session'] is not None
    assert stats['newest_session'] is not None

@pytest.mark.asyncio
async def test_error_handling(session_manager):
    """Test error handling"""
    # Test invalid URL
    with pytest.raises(SessionManagerError):
        await session_manager.create_session("invalid-url")
    
    # Test invalid authentication
    with pytest.raises(SessionManagerError):
        await session_manager.authenticate(
            "https://httpbin.org/status/401",
            {"username": "invalid"}
        ) 