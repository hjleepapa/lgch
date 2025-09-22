import asyncio
import base64
import json
import logging
import websockets
import os
import wave
from datetime import datetime
from typing import AsyncGenerator
import numpy as np

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph

from .assistant_graph_todo import TodoAgent
from .voice_utils import play_audio_async_generator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress noisy logs from other libraries
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


async def save_call_recording(audio_data: bytes, call_sid: str, from_number: str = None, to_number: str = None) -> str:
    """Save call recording to file and database.
    
    Args:
        audio_data: Raw audio data from Twilio
        call_sid: Twilio Call SID
        from_number: Caller's phone number
        to_number: Called phone number
        
    Returns:
        Path to the saved recording file
    """
    try:
        logger.info(f"Starting call recording save for SID: {call_sid}")
        logger.info(f"Audio data size: {len(audio_data)} bytes")
        
        # Validate audio data
        if not audio_data or len(audio_data) == 0:
            logger.error("No audio data provided for recording")
            return None
        
        # Create recordings directory if it doesn't exist
        # Get the project root directory (where app.py is located)
        # __file__ is lgch_todo/twilio_handler.py
        # We want to go up 2 levels to get to the project root
        project_root = os.path.dirname(os.path.dirname(__file__))
        recordings_dir = os.path.join(project_root, "recordings")
        logger.info(f"Recordings directory: {recordings_dir}")
        os.makedirs(recordings_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"call_{call_sid}_{timestamp}.wav"
        file_path = os.path.join(recordings_dir, filename)
        logger.info(f"Recording file path: {file_path}")
        
        # Convert μ-law audio to WAV format
        try:
            # Convert μ-law to linear PCM using numpy
            ulaw_array = np.frombuffer(audio_data, dtype=np.uint8)
            # μ-law to linear conversion
            sign = ((ulaw_array & 0x80) != 0) * -1
            exponent = (ulaw_array & 0x70) >> 4
            mantissa = ulaw_array & 0x0F
            
            # Reconstruct the linear value
            linear = np.zeros_like(ulaw_array, dtype=np.int16)
            for i in range(len(ulaw_array)):
                if exponent[i] == 0:
                    linear[i] = (mantissa[i] << 1) + 33
                else:
                    linear[i] = ((mantissa[i] << (exponent[i] + 1)) + (1 << (exponent[i] + 2))) - 33
                
                if sign[i]:
                    linear[i] = -linear[i]
            
            pcm_audio = linear.tobytes()
            logger.info(f"Converted audio to PCM: {len(pcm_audio)} bytes")
        except Exception as e:
            logger.error(f"Error converting audio format: {e}")
            return None
        
        # Create WAV file
        try:
            with wave.open(file_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 2 bytes per sample
                wav_file.setframerate(8000)  # 8kHz sample rate
                wav_file.writeframes(pcm_audio)
            logger.info(f"WAV file created successfully: {file_path}")
        except Exception as e:
            logger.error(f"Error creating WAV file: {e}")
            return None
        
        # Calculate file size and duration
        file_size = os.path.getsize(file_path)
        duration_seconds = len(pcm_audio) // (8000 * 2)  # 8kHz, 2 bytes per sample
        logger.info(f"File size: {file_size} bytes, Duration: {duration_seconds} seconds")
        
        # Save to database
        try:
            from .mcps.local_servers.db_todo import create_call_recording
            await create_call_recording(
                call_sid=call_sid,
                recording_path=file_path,
                from_number=from_number,
                to_number=to_number,
                duration_seconds=duration_seconds,
                file_size_bytes=file_size,
                status="completed"
            )
            logger.info(f"Call recording saved to database: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save recording to database: {e}")
            import traceback
            logger.error(f"Database error traceback: {traceback.format_exc()}")
        
        return file_path
        
    except Exception as e:
        logger.error(f"Error saving call recording: {e}")
        return None


async def stream_graph_response(
    input_data: dict, graph: StateGraph, config: dict
) -> AsyncGenerator[str, None]:
    """
    Streams the text response from the LangGraph agent.
    This is a simplified version for text-only streaming to the console.
    """
    full_response = ""
    async for chunk in graph.astream(input=input_data, config=config, stream_mode="values"):
        if "messages" in chunk:
            message = chunk["messages"][-1]
            if isinstance(message, AIMessage) and message.content:
                # Yield the new content
                new_content = message.content.replace(full_response, "")
                yield new_content
                full_response = message.content


async def twilio_handler(websocket):
    """
    Handles the Twilio WebSocket connection for a voice call.
    Manages audio streams and interaction with the LangGraph agent.
    """
    logger.info("🔌 WebSocket connection established in twilio_handler.")
    logger.info(f"WebSocket type: {type(websocket)}")

    # --- Agent and Tools Setup ---
    # This part is similar to original main.py
    from langchain_mcp_adapters.client import MultiServerMCPClient
    import os
    
    try:
        # Get the directory where this file is located (lgch_todo)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mcp_config_path = os.path.join(current_dir, "mcps", "mcp_config.json")
        
        with open(mcp_config_path) as f:
            mcp_config = json.load(f)

        # Set working directory to project root for MCP servers
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        original_cwd = os.getcwd()
        os.chdir(project_root)
        
        try:
            client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
            tools = await client.get_tools()
            agent_graph = TodoAgent(tools=tools).build_graph()
            logger.info("✅ Agent and tools initialized successfully")
        finally:
            os.chdir(original_cwd)
    except Exception as e:
        logger.error(f"❌ Error initializing agent: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Create a simple fallback agent without MCP tools
        agent_graph = TodoAgent(tools=[]).build_graph()
        logger.info("⚠️ Using fallback agent without MCP tools")

    # Each call gets a unique thread_id for conversation memory
    # We'll get the call_sid from the Twilio Media Streams 'start' event
    call_sid = None
    config = {"configurable": {"thread_id": f"twilio-{call_sid or 'unknown'}"}}
    logger.info(f"Using thread_id: {config['configurable']['thread_id']}")

    # --- Initial Greeting ---
    intro_text = ""
    try:
        initial_input = {
            "messages": [
                HumanMessage(content="You have just received a phone call. Briefly introduce yourself as Luna, the personal productivity assistant, and ask how you can help.")
            ]
        }

        # Stream the intro message text to console and get audio for Twilio
        async for text_chunk in stream_graph_response(initial_input, agent_graph, config):
            intro_text += text_chunk
            print(text_chunk, end="", flush=True)

        print("\n")

        # Generate the audio for the intro and stream it to Twilio
        if intro_text:
            logger.info("Streaming intro audio to Twilio...")
            audio_generator = play_audio_async_generator(intro_text, stream=True)
            await stream_audio_to_twilio(websocket, call_sid, audio_generator)
    except Exception as e:
        logger.error(f"❌ Error generating intro: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Continue without intro audio

    # --- Main Interaction Loop ---
    audio_buffer = bytearray()
    full_call_audio = bytearray()  # Store entire call audio for recording
    from_number = None
    to_number = None
    # https://www.twilio.com/docs/voice/media-streams/websocket-messages#start-message
    async for message in websocket:
        try:
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                # Extract call_sid and phone numbers from the start event
                call_sid = data.get("callSid")
                from_number = data.get("from")
                to_number = data.get("to")
                if call_sid:
                    config = {"configurable": {"thread_id": f"twilio-{call_sid}"}}
                    logger.info(f"Updated thread_id with call_sid: {config['configurable']['thread_id']}")
                    logger.info(f"Call from {from_number} to {to_number}")

            elif event == "media":
                try:
                    # Append incoming audio chunks to a buffer
                    payload = data["media"]["payload"]
                    audio_chunk = base64.b64decode(payload)
                    audio_buffer.extend(audio_chunk)
                    full_call_audio.extend(audio_chunk)  # Store for full call recording
                    
                    # Periodic save every 10KB of audio to prevent data loss
                    if len(full_call_audio) % 10240 == 0 and len(full_call_audio) > 0:
                        logger.info(f"Periodic audio checkpoint: {len(full_call_audio)} bytes collected")
                except Exception as e:
                    logger.error(f"Error processing media event: {e}")
                    # Don't let media processing errors crash the handler

            elif event == "stop":
                try:
                    logger.info("Stop event received. Processing accumulated audio.")
                    if not audio_buffer:
                        logger.warning("No audio in buffer to process.")
                        continue

                    # 1. Transcribe the buffered audio
                    from .voice_utils import transcribe_audio_bytes
                    transcribed_text = await transcribe_audio_bytes(bytes(audio_buffer))
                    audio_buffer.clear() # Clear buffer for next turn

                    if not transcribed_text or len(transcribed_text.strip()) < 2:
                        logger.info(f"Skipping transcription (too short): '{transcribed_text}'")
                        continue

                    logger.info(f"--- You --- \n{transcribed_text}\n")

                    # 2. Get response from the agent
                    agent_input = {"messages": [HumanMessage(content=transcribed_text)]}
                    agent_response_text = ""
                    
                    print("--- Assistant ---\n")
                    async for text_chunk in stream_graph_response(agent_input, agent_graph, config):
                        agent_response_text += text_chunk
                        print(text_chunk, end="", flush=True)
                    print("\n")

                    # 3. Send the agent's response back to Twilio
                    if agent_response_text:
                        logger.info("Sending agent response to Twilio...")
                        
                        # Check if WebSocket is still open before sending response
                        if websocket.close_code is not None:
                            logger.warning("WebSocket connection closed before sending response")
                            return
                        
                        try:
                            # Send a simple text response
                            logger.info("Sending text response to Twilio...")
                            await websocket.send(json.dumps({
                                "event": "response",
                                "streamSid": call_sid,
                                "text": agent_response_text
                            }))
                            logger.info("Successfully sent text response to Twilio")
                            
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("WebSocket connection closed during response sending")
                        except Exception as e:
                            logger.error(f"Error sending response: {e}")
                            import traceback
                            logger.error(f"Traceback: {traceback.format_exc()}")

                    # After responding, send a "mark" message to signal completion
                    await websocket.send(json.dumps({
                        "event": "mark",
                        "streamSid": data.get("streamSid", call_sid),
                        "mark": { "name": "agent_turn_complete" }
                    }))
                except Exception as e:
                    logger.error(f"Error processing stop event: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    # Continue processing other events even if one fails

        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}", exc_info=True)

    # Save call recording when WebSocket closes
    logger.info(f"WebSocket closing. Full call audio size: {len(full_call_audio)} bytes, Call SID: {call_sid}")
    if full_call_audio and call_sid:
        logger.info("Saving call recording...")
        try:
            recording_path = await save_call_recording(
                audio_data=bytes(full_call_audio),
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number
            )
            if recording_path:
                logger.info(f"Call recording saved successfully: {recording_path}")
            else:
                logger.error("Failed to save call recording")
        except Exception as e:
            logger.error(f"Error saving call recording: {e}")
    else:
        logger.warning(f"Skipping recording save - Audio: {len(full_call_audio) if full_call_audio else 0} bytes, SID: {call_sid}")
        
    # Additional safety: Save recording even if WebSocket doesn't close properly
    if full_call_audio and call_sid and len(full_call_audio) > 1000:  # Only if we have substantial audio
        logger.info("Safety save: Attempting to save recording with substantial audio data")
        try:
            recording_path = await save_call_recording(
                audio_data=bytes(full_call_audio),
                call_sid=f"{call_sid}_safety",
                from_number=from_number,
                to_number=to_number
            )
            if recording_path:
                logger.info(f"Safety recording saved: {recording_path}")
        except Exception as e:
            logger.error(f"Error in safety recording save: {e}")

    logger.info("WebSocket connection closed.")


async def stream_audio_to_twilio(websocket, stream_sid: str, audio_generator: AsyncGenerator[bytes, None]):
    """Streams audio chunks from a generator to Twilio as base64 encoded media messages."""
    try:
        chunk_count = 0
        async for audio_chunk in audio_generator:
            # Check if WebSocket is still open
            if websocket.close_code is not None:
                logger.warning("WebSocket connection closed, stopping audio streaming")
                break
                
            # Twilio expects audio in mulaw format, base64 encoded.
            # For simplicity, we are sending raw audio from OpenAI TTS and letting Twilio handle it.
            # For production, you would convert to 8-bit PCMU/mulaw.
            
            payload = base64.b64encode(audio_chunk).decode("utf-8")
            
            try:
                await websocket.send(json.dumps({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "payload": payload
                    }
                }))
                chunk_count += 1
                
                # Send a ping every 10 chunks to keep connection alive
                if chunk_count % 10 == 0:
                    await websocket.ping()
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed during audio chunk streaming")
                break
            except Exception as e:
                logger.error(f"Error sending audio chunk {chunk_count}: {e}")
                break
                
        logger.info(f"Successfully streamed {chunk_count} audio chunks to Twilio")
        
    except websockets.exceptions.ConnectionClosed:
        logger.warning("WebSocket connection closed during audio streaming")
    except Exception as e:
        logger.error(f"Error streaming audio to Twilio: {e}")


def run_async_handler(websocket):
    """Runs the async handler in a new event loop."""
    try:
        asyncio.run(twilio_handler(websocket))
    except Exception as e:
        logger.error(f"Error running async handler: {e}")