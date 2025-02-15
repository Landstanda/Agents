#!/usr/bin/env python3

import aiohttp
import asyncio
from typing import Dict, Optional, Any, List
import json
import logging
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from yarl import URL
from src.utils.logging import get_logger
from src.modules.core_request import CoreRequestModule, CoreRequestError

logger = get_logger(__name__)

class SessionManagerError(Exception):
    """Custom exception for SessionManagerModule errors"""
    pass

class Session:
    """Represents a single website session"""
    
    def __init__(self, domain: str):
        self.domain = domain
        self.cookies: Dict[str, str] = {}
        self.headers: Dict[str, str] = {}
        self.last_accessed: datetime = datetime.now()
        self.is_authenticated: bool = False
        self.auth_token: Optional[str] = None
        self.expiry: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        if self.expiry:
            return datetime.now() > self.expiry
        return False
    
    def update_access_time(self):
        """Update last accessed timestamp"""
        self.last_accessed = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for storage"""
        return {
            'domain': self.domain,
            'cookies': self.cookies,
            'headers': self.headers,
            'last_accessed': self.last_accessed.isoformat(),
            'is_authenticated': self.is_authenticated,
            'auth_token': self.auth_token,
            'expiry': self.expiry.isoformat() if self.expiry else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create session from dictionary"""
        session = cls(data['domain'])
        session.cookies = data['cookies']
        session.headers = data['headers']
        session.last_accessed = datetime.fromisoformat(data['last_accessed'])
        session.is_authenticated = data['is_authenticated']
        session.auth_token = data['auth_token']
        session.expiry = datetime.fromisoformat(data['expiry']) if data['expiry'] else None
        return session

class SessionManagerModule:
    """Module for managing web sessions across multiple domains"""
    
    def __init__(self, 
                 session_timeout: int = 3600,  # 1 hour default timeout
                 max_sessions: int = 100):     # Maximum number of concurrent sessions
        """
        Initialize session manager
        
        Args:
            session_timeout: Session timeout in seconds
            max_sessions: Maximum number of concurrent sessions
        """
        self.logger = logger
        self.session_timeout = session_timeout
        self.max_sessions = max_sessions
        self.sessions: Dict[str, Session] = {}
        self.request_module = CoreRequestModule()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.request_module.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.request_module.__aexit__(exc_type, exc_val, exc_tb)
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed_url = URL(url)
        # Remove query parameters but keep path
        path = str(parsed_url.path)
        if not path:
            path = "/"
        return str(parsed_url.host) + path

    def _extract_base_domain(self, url: str) -> str:
        """Extract base domain without path"""
        return str(URL(url).host)
    
    def _parse_cookies(self, cookie_header: str) -> Dict[str, str]:
        """Parse cookie header into dictionary"""
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        return {k: v.value for k, v in cookie.items()}
    
    async def create_session(self, url: str) -> Session:
        """
        Create a new session for a domain
        
        Args:
            url: URL to create session for
            
        Returns:
            Session object
            
        Raises:
            SessionManagerError: If session creation fails
        """
        try:
            # Validate URL format first
            try:
                parsed_url = URL(url)
                if not parsed_url.host:
                    raise ValueError("Invalid URL: no host found")
            except Exception as e:
                raise SessionManagerError(f"Invalid URL format: {str(e)}")
            
            domain = self._extract_domain(url)
            
            # Check if we're at the session limit
            if len(self.sessions) >= self.max_sessions:
                # Remove oldest session
                oldest = min(self.sessions.values(), key=lambda s: s.last_accessed)
                del self.sessions[oldest.domain]
            
            session = Session(domain)
            session.expiry = datetime.now() + timedelta(seconds=self.session_timeout)
            
            # Store session before making request to avoid duplicate creation
            self.sessions[domain] = session
            
            # Make initial request to get cookies if needed
            try:
                response = await self.request_module.get(url)
                if 'set-cookie' in response['headers']:
                    session.cookies = self._parse_cookies(response['headers']['set-cookie'])
            except CoreRequestError:
                # If GET fails, the session is still valid but without cookies
                pass
            
            return session
            
        except SessionManagerError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to create session for {url}: {str(e)}")
            raise SessionManagerError(f"Session creation failed: {str(e)}")
    
    async def get_session(self, url: str, create_if_missing: bool = True) -> Session:
        """
        Get session for a domain
        
        Args:
            url: URL to get session for
            create_if_missing: Whether to create session if it doesn't exist
            
        Returns:
            Session object
        """
        domain = self._extract_domain(url)
        
        if domain in self.sessions:
            session = self.sessions[domain]
            
            # Check if session has expired
            if session.is_expired():
                del self.sessions[domain]
                if create_if_missing:
                    return await self.create_session(url)
                raise SessionManagerError(f"Session for {domain} has expired")
                
            session.update_access_time()
            return session
            
        if create_if_missing:
            return await self.create_session(url)
            
        raise SessionManagerError(f"No session found for {domain}")
    
    async def authenticate(self, 
                         url: str,
                         auth_data: Dict[str, Any],
                         auth_method: str = 'POST') -> Session:
        """
        Authenticate session
        
        Args:
            url: Authentication endpoint URL
            auth_data: Authentication data (credentials)
            auth_method: HTTP method for auth request
            
        Returns:
            Authenticated session
        """
        try:
            base_domain = self._extract_base_domain(url)
            # Find any existing session for this domain
            existing_sessions = [s for s in self.sessions.values() 
                               if s.domain.startswith(base_domain)]
            
            if existing_sessions:
                session = existing_sessions[0]
            else:
                session = await self.create_session(url)
            
            # Make auth request
            response = await self.request_module.request(
                method=auth_method,
                url=url,
                json_data=auth_data,
                headers={'Cookie': '; '.join(f'{k}={v}' for k, v in session.cookies.items())}
            )
            
            # Update session with new cookies/headers
            if 'set-cookie' in response['headers']:
                session.cookies.update(self._parse_cookies(response['headers']['set-cookie']))
            
            # Look for common auth tokens in response
            data = response['data']
            if isinstance(data, dict):
                for key in ['token', 'access_token', 'auth_token', 'jwt']:
                    if key in data:
                        session.auth_token = data[key]
                        break
            
            session.is_authenticated = True
            session.update_access_time()
            session.expiry = datetime.now() + timedelta(seconds=self.session_timeout)
            
            # Update domain to base domain after authentication
            session.domain = base_domain
            self.sessions[base_domain] = session
            
            return session
            
        except Exception as e:
            self.logger.error(f"Authentication failed for {url}: {str(e)}")
            raise SessionManagerError(f"Authentication failed: {str(e)}")
    
    async def make_request(self,
                         method: str,
                         url: str,
                         session: Optional[Session] = None,
                         **kwargs) -> Dict[str, Any]:
        """
        Make request using session
        
        Args:
            method: HTTP method
            url: Request URL
            session: Optional session to use
            **kwargs: Additional request parameters
            
        Returns:
            Response data
        """
        try:
            if not session:
                session = await self.get_session(url)
            
            # Add session cookies and headers
            headers = kwargs.get('headers', {})
            if session.cookies:
                headers['Cookie'] = '; '.join(f'{k}={v}' for k, v in session.cookies.items())
            if session.auth_token:
                headers['Authorization'] = f'Bearer {session.auth_token}'
            kwargs['headers'] = headers
            
            response = await self.request_module.request(method, url, **kwargs)
            
            # Update session cookies
            if 'set-cookie' in response['headers']:
                session.cookies.update(self._parse_cookies(response['headers']['set-cookie']))
            
            session.update_access_time()
            return response
            
        except Exception as e:
            self.logger.error(f"Request failed for {url}: {str(e)}")
            raise SessionManagerError(f"Request failed: {str(e)}")
    
    def clear_session(self, url: str):
        """Clear session for domain"""
        domain = self._extract_domain(url)
        if domain in self.sessions:
            del self.sessions[domain]
    
    def clear_all_sessions(self):
        """Clear all sessions"""
        self.sessions.clear()
    
    def get_active_sessions(self) -> List[Session]:
        """Get list of active sessions"""
        now = datetime.now()
        return [s for s in self.sessions.values() 
                if s.expiry and s.expiry > now]
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        active_sessions = self.get_active_sessions()
        authenticated = [s for s in active_sessions if s.is_authenticated]
        
        oldest = None
        newest = None
        if active_sessions:
            oldest = min(active_sessions, key=lambda s: s.last_accessed).last_accessed
            newest = max(active_sessions, key=lambda s: s.last_accessed).last_accessed
        
        return {
            'total_sessions': len(self.sessions),
            'active_sessions': len(active_sessions),
            'authenticated_sessions': len(authenticated),
            'oldest_session': oldest.isoformat() if oldest else None,
            'newest_session': newest.isoformat() if newest else None
        } 