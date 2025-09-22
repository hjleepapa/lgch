from flask import Blueprint, request, jsonify, render_template, Response
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph
import asyncio
import json
import os
import requests

from twilio.twiml.voice_response import VoiceResponse, Connect, Gather
from .state import AgentState
from .assistant_graph_todo import TodoAgent
from langchain_mcp_adapters.client import MultiServerMCPClient


lgch_todo_bp = Blueprint(
    'lgch_todo',
    __name__,
    url_prefix='/lgch_todo',
    template_folder='templates',
    static_folder='static'
)

def get_webhook_base_url():
    """Get the webhook base URL for Twilio webhooks."""
    # Check if we're in production or development
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('ENVIRONMENT') == 'production':
        # Production: Use environment variable or default domain
        return os.getenv('WEBHOOK_BASE_URL', 'https://hjlees.com')
    else:
        # Development: Try ngrok first, fallback to localhost
        try:
            # Get ngrok tunnels from local API
            response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
            tunnels = response.json()
            
            # Look for a Flask tunnel (HTTP tunnel for port 5000)
            for tunnel in tunnels.get('tunnels', []):
                if tunnel.get('config', {}).get('addr') == 'http://localhost:5000':
                    return tunnel.get('public_url', 'http://localhost:5000')
            
            # If no ngrok tunnel found, use localhost (for testing)
            print("WARNING: No ngrok tunnel found. Using localhost for development.")
            return "http://localhost:5000"
        except Exception as e:
            print(f"Error getting ngrok tunnel info: {e}")
            return "http://localhost:5000"

def get_websocket_url():
    """Get the WebSocket URL for Twilio Media Streams."""
    # Check if we're in production or development
    if os.getenv('FLASK_ENV') == 'production' or os.getenv('ENVIRONMENT') == 'production':
        # Production: Use environment variable or default domain
        base_url = os.getenv('WEBSOCKET_BASE_URL', 'wss://hjlees.com')
        return base_url
    else:
        # Development: Try ngrok first, fallback to localhost
        try:
            # Get ngrok tunnels from local API
            response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
            tunnels = response.json()
            
            # Look for a WebSocket tunnel (HTTP tunnel for port 5001)
            for tunnel in tunnels.get('tunnels', []):
                if tunnel.get('config', {}).get('addr') == 'http://localhost:5001':
                    public_url = tunnel.get('public_url', '')
                    if public_url.startswith('https://'):
                        # Convert https:// to wss://
                        return public_url.replace('https://', 'wss://')
            
            # If no ngrok tunnel found, use localhost (for testing)
            print("WARNING: No ngrok tunnel found. Using localhost for development.")
            return "ws://localhost:5001"
        except Exception as e:
            print(f"Error getting ngrok tunnel info: {e}")
            return "ws://localhost:5001"

# --- Twilio Voice Routes ---
@lgch_todo_bp.route('/twilio/call', methods=['POST'])
def twilio_call_webhook():
    """
    Handles incoming calls from Twilio.
    Uses Gather to collect speech input and redirect to processing endpoint.
    """
    # Get the current webhook base URL
    webhook_base_url = get_webhook_base_url()
    
    # Check if this is a continuation of the conversation
    is_continuation = request.args.get('is_continuation', 'false').lower() == 'true'
    
    response = VoiceResponse()
    
    # Use Gather to collect speech input with barge-in capability
    gather = response.gather(
        input='speech',
        action='/lgch_todo/twilio/process_audio',
        method='POST',
        speech_timeout='auto',
        timeout=10,
        barge_in=True  # Enable barge-in to interrupt while speaking
    )
    
    # Only say the welcome message if this is the initial call
    if not is_continuation:
        gather.say("Hello! I'm Luna, your personal productivity assistant. How can I help you today?", voice='Polly.Amy')
    
    # Fallback if no speech is detected
    response.say("I didn't hear anything. Please try again.", voice='Polly.Amy')
    response.redirect('/lgch_todo/twilio/call?is_continuation=true')
    
    print(f"Generated TwiML for incoming call: {str(response)}")
    return Response(str(response), mimetype='text/xml')

@lgch_todo_bp.route('/twilio/process_audio', methods=['POST'])
def process_audio_webhook():
    """
    Handles audio processing requests from Twilio.
    Processes the audio and returns TwiML with the agent's response.
    
    Features:
    - Barge-in capability: Users can interrupt the agent while it's speaking
    - Continuous conversation flow
    - Graceful error handling
    """
    try:
        # Get the transcribed text from the request
        transcribed_text = request.form.get('SpeechResult', '')
        call_sid = request.form.get('CallSid', '')
        
        print(f"Processing audio for call {call_sid}: {transcribed_text}")
        
        if not transcribed_text or len(transcribed_text.strip()) < 2:
            response = VoiceResponse()
            
            # Use Gather with barge-in for "didn't catch that" response
            gather = Gather(
                input='speech',
                action='/lgch_todo/twilio/process_audio',
                method='POST',
                speech_timeout='auto',
                timeout=10,
                barge_in=True
            )
            gather.say("I didn't catch that. Could you please repeat?", voice='Polly.Amy')
            response.append(gather)
            
            # Fallback
            response.say("I didn't hear anything. Please try again.", voice='Polly.Amy')
            response.redirect('/lgch_todo/twilio/call?is_continuation=true')
            return Response(str(response), mimetype='text/xml')
        
        # Check if user wants to end the call
        exit_phrases = ['exit', 'goodbye', 'bye', 'that\'s it', 'that is it', 'thank you', 'thanks', 'done', 'finished', 'end call', 'hang up']
        if any(phrase in transcribed_text.lower() for phrase in exit_phrases):
            # End the call gracefully
            response = VoiceResponse()
            response.say("Thank you for using Luna! Have a great day!", voice='Polly.Amy')
            response.hangup()
            return Response(str(response), mimetype='text/xml')
        
        # Process with the agent
        agent_response = asyncio.run(_run_agent_async(transcribed_text))
        
        # Return TwiML with the agent's response and barge-in capability
        response = VoiceResponse()
        
        # Use Gather with speech input to enable barge-in functionality
        gather = Gather(
            input='speech',
            action='/lgch_todo/twilio/process_audio',
            method='POST',
            speech_timeout='auto',
            timeout=10,
            barge_in=True  # Enable barge-in to interrupt while speaking
        )
        
        # Add the agent's response to the gather
        gather.say(agent_response, voice='Polly.Amy')
        response.append(gather)
        
        # Fallback if no speech is detected after the response
        response.say("I didn't hear anything. Please try again.", voice='Polly.Amy')
        response.redirect('/lgch_todo/twilio/call?is_continuation=true')
        
        print(f"Generated TwiML response: {str(response)}")
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print(f"Error processing audio: {e}")
        response = VoiceResponse()
        
        # Use Gather with barge-in for error messages too
        gather = Gather(
            input='speech',
            action='/lgch_todo/twilio/process_audio',
            method='POST',
            speech_timeout='auto',
            timeout=10,
            barge_in=True
        )
        gather.say("I'm sorry, I encountered an error processing your request. Please try again.", voice='Polly.Amy')
        response.append(gather)
        
        # Fallback
        response.say("I didn't hear anything. Please try again.", voice='Polly.Amy')
        response.redirect('/lgch_todo/twilio/call?is_continuation=true')
        return Response(str(response), mimetype='text/xml')

# WebSocket server is now handled by a separate process
# See websocket_server.py for the Twilio voice streaming implementation

# --- Web/API Routes ---
@lgch_todo_bp.route('/')
def index():
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'lgch_todo_index.html')
    if os.path.exists(template_path):
        return render_template('lgch_todo_index.html')
    return "LGCH Todo: LangGraph + MCP integration is ready. POST to /lgch_todo/run_agent with JSON {prompt: str}."


async def _get_agent_graph() -> StateGraph:
    """Helper to initialize the agent graph with tools."""
    config_path = os.path.join(os.path.dirname(__file__), 'mcps', 'mcp_config.json')
    if not os.path.exists(config_path):
        # Fallback path for when running from the root directory
        config_path = os.path.join('lgch_todo', 'mcps', 'mcp_config.json')

    with open(config_path) as f:
        mcp_config = json.load(f)
    
    # Set working directory to project root for MCP servers
    # __file__ is: /Users/hj/Web Development Projects/1. Main/lgch_todo/routes.py
    # We need: /Users/hj/Web Development Projects/1. Main
    project_root = os.path.dirname(os.path.dirname(__file__))
    original_cwd = os.getcwd()
    os.chdir(project_root)
    
    # Update the MCP config with absolute paths
    for server_name, server_config in mcp_config["mcpServers"].items():
        if "args" in server_config and len(server_config["args"]) > 0:
            # Convert relative path to absolute path
            relative_path = server_config["args"][0]
            if not os.path.isabs(relative_path):
                absolute_path = os.path.join(project_root, relative_path)
                server_config["args"][0] = absolute_path
    
    try:
        client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
        tools = await client.get_tools()
        return TodoAgent(tools=tools).build_graph()
    finally:
        os.chdir(original_cwd)


async def _run_agent_async(prompt: str) -> str:
    """Runs the agent for a given prompt and returns the final response."""
    agent_graph = await _get_agent_graph()

    input_state = AgentState(
        messages=[HumanMessage(content=prompt)],
        customer_id=""
    )
    config = {"configurable": {"thread_id": "flask-thread-1"}}

    # Stream through the graph to execute the agent logic
    async for _ in agent_graph.astream(input=input_state, stream_mode="values", config=config):
        pass

    final_state = agent_graph.get_state(config=config)
    last_message = final_state.values.get("messages")[-1]
    return getattr(last_message, 'content', "")


@lgch_todo_bp.route('/run_agent', methods=['POST'])
def run_agent():
    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt')
    if not prompt:
        return jsonify({"error": "Missing 'prompt' in JSON body"}), 400

    try:
        result = asyncio.run(_run_agent_async(prompt))
        return jsonify({"result": result})
    except Exception as e:
        # Log the full error for debugging
        print(f"Error in /run_agent: {e}")
        return jsonify({"error": str(e)}), 500
