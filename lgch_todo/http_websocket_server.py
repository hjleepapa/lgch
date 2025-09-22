#!/usr/bin/env python3
"""
Hybrid HTTP/WebSocket server for Twilio Media Streams.
Handles both HTTP requests (for ngrok health checks) and WebSocket connections.
"""

import asyncio
import logging
import sys
import os
from aiohttp import web, WSMsgType
import aiohttp

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the proper Twilio handler with AI integration
from lgch_todo.twilio_handler import twilio_handler

async def http_handler(request):
    """Handle HTTP requests (for ngrok health checks)."""
    logger.info(f"HTTP request from {request.remote}: {request.method} {request.path}")
    return web.Response(
        text="WebSocket server is running",
        content_type="text/plain",
        status=200
    )

async def websocket_handler(request):
    """Handle WebSocket connections from Twilio."""
    logger.info(f"WebSocket connection attempt from {request.remote}")
    
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    logger.info(f"WebSocket connection established with {request.remote}")
    
    try:
        # Create a wrapper to make aiohttp WebSocket compatible with twilio_handler
        class WebSocketWrapper:
            def __init__(self, aiohttp_ws):
                self.ws = aiohttp_ws
                self._closed = False
            
            async def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self._closed:
                    raise StopAsyncIteration
                
                try:
                    msg = await self.ws.receive()
                    if msg.type == WSMsgType.TEXT:
                        return msg.data
                    elif msg.type == WSMsgType.ERROR:
                        logger.error(f'WebSocket error: {self.ws.exception()}')
                        self._closed = True
                        raise StopAsyncIteration
                    elif msg.type == WSMsgType.CLOSE:
                        logger.info('WebSocket connection closed')
                        self._closed = True
                        raise StopAsyncIteration
                    else:
                        # Skip other message types
                        return await self.__anext__()
                except Exception as e:
                    logger.error(f"Error receiving WebSocket message: {e}")
                    self._closed = True
                    raise StopAsyncIteration
            
            async def send(self, data):
                await self.ws.send_str(data)
        
        # Use the wrapper with the AI-integrated handler
        wrapped_ws = WebSocketWrapper(ws)
        await twilio_handler(wrapped_ws)
        
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        logger.info("WebSocket connection handler finished")
    
    return ws

async def main():
    """Start the hybrid HTTP/WebSocket server."""
    logger.info("Starting Twilio Media Streams server on localhost:5001")
    
    # Create aiohttp app
    app = web.Application()
    
    # Add routes
    app.router.add_get('/', http_handler)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_get('/health', http_handler)
    
    # Start server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 5001)
    await site.start()
    
    logger.info("HTTP/WebSocket server started successfully on localhost:5001")
    logger.info("Ready to accept Twilio Media Streams connections...")
    logger.info("Server will handle: HTTP requests and WebSocket connections")
    
    # Keep the server running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
