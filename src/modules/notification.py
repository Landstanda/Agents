#!/usr/bin/env python3

import logging
from typing import Dict, Any, List
from ..utils.logging import get_logger

logger = get_logger(__name__)

class NotificationModule:
    """Module for handling system notifications and alerts"""
    
    def __init__(self):
        self.channels = {
            'email': True,
            'slack': True,
            'desktop': True
        }
    
    async def send_notification(self, recipient: str, message: str, 
                              channel: str = "all", **kwargs) -> Dict[str, Any]:
        """Send a notification through specified channel(s)"""
        try:
            logger.info(f"Sending notification to {recipient} via {channel}")
            
            if channel == "all":
                # Send through all available channels
                results = {}
                for ch in self.channels:
                    if self.channels[ch]:
                        results[ch] = await self._send_via_channel(
                            channel=ch,
                            recipient=recipient,
                            message=message,
                            **kwargs
                        )
                return {
                    "status": "success",
                    "results": results
                }
            else:
                # Send through specific channel
                result = await self._send_via_channel(
                    channel=channel,
                    recipient=recipient,
                    message=message,
                    **kwargs
                )
                return {
                    "status": "success",
                    "result": result
                }
                
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _send_via_channel(self, channel: str, recipient: str, 
                              message: str, **kwargs) -> Dict[str, Any]:
        """Send notification through a specific channel"""
        try:
            # Implement channel-specific sending logic
            if channel == "email":
                # Use EmailSenderModule for email notifications
                return {"delivered": True, "channel": "email"}
            
            elif channel == "slack":
                # Use SlackModule for Slack notifications
                return {"delivered": True, "channel": "slack"}
            
            elif channel == "desktop":
                # Implement desktop notifications
                return {"delivered": True, "channel": "desktop"}
            
            else:
                raise ValueError(f"Unsupported notification channel: {channel}")
                
        except Exception as e:
            logger.error(f"Error sending via {channel}: {str(e)}")
            return {
                "delivered": False,
                "error": str(e)
            }
    
    def enable_channel(self, channel: str) -> None:
        """Enable a notification channel"""
        if channel in self.channels:
            self.channels[channel] = True
    
    def disable_channel(self, channel: str) -> None:
        """Disable a notification channel"""
        if channel in self.channels:
            self.channels[channel] = False
    
    def get_enabled_channels(self) -> List[str]:
        """Get list of enabled notification channels"""
        return [ch for ch, enabled in self.channels.items() if enabled] 