# LGCH Todo System: LangGraph + Twilio + MCP + LangChain Voice AI

The LGCH Todo System leverages the power of LangGraph, Model Context Protocol (MCP), and LangChain to create an intelligent voice-enabled AI assistant named Luna. This system demonstrates advanced agent architecture with tool-calling capabilities, state management, and seamless integration with external services.

Luna can manage to-do tasks, reminders, and calendar events through natural voice interactions or web API calls. All data is stored in a PostgreSQL database and automatically synchronized with Google Calendar, providing a comprehensive productivity management solution.

## 🌟 Key Features

- **Voice-Enabled AI Assistant**: Natural conversation with Luna through voice or phone calls
- **Todo List Management**: Create, update, complete, and delete todos with priority levels
- **Reminder System**: Create and manage reminders with importance levels and dates
- **Calendar Event Management**: Schedule and manage calendar events with start/end times
- **Google Calendar Integration**: Automatic synchronization of all data with Google Calendar
- **Twilio Phone Integration**: Make and receive phone calls for voice interaction
- **WebSocket Real-time Communication**: Real-time audio streaming and processing
- **RESTful API Endpoints**: Programmatic access through web API
- **ngrok Tunnel Management**: Secure webhook handling for production deployment
- **MCP Tool Integration**: Model Context Protocol for standardized tool management
- **Database Persistence**: PostgreSQL storage with SQLAlchemy ORM

## 🛠️ Technology Stack

### Core Technologies

- **LangGraph**: Agent orchestration and state management
- **Model Context Protocol (MCP)**: Standardized tool management and server communication
- **LangChain**: LLM framework and tool integration
- **Flask**: Web framework for REST API and web interface
- **SQLAlchemy**: ORM for database operations
- **PostgreSQL**: Local database for data storage
- **OpenAI APIs**: GPT-4, Whisper (Speech-to-Text), TTS (Text-to-Speech)
- **Twilio**: Phone integration and Media Streams
- **ngrok**: Secure tunneling for webhook handling
- **WebSocket**: Real-time communication protocol
- **Google Calendar API**: Calendar synchronization

### Audio Processing

- **Twilio Media Streams**: Real-time audio streaming from phone calls
- **OpenAI Whisper**: Speech-to-text transcription
- **OpenAI TTS**: Text-to-speech audio generation
- **NumPy**: Audio processing and μ-law to PCM conversion

## 📋 Prerequisites

- Python 3.13
- OpenAI API key
- Twilio account with phone number
- ngrok account and authtoken
- Local PostgreSQL database
- Google Calendar API credentials
- Phone for voice interaction (or microphone/speakers for development)

## 🚀 Getting Started

### 1. Set up a virtual environment and install dependencies

Navigate to the `lgch_todo` directory and set up the environment:

```bash
cd lgch_todo
```

(Recommended) use [uv](https://github.com/uvlabs/uv) for dependency management:

```bash
uv sync
```

Alternatively, using pip:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

### 2. Set up environment variables

Create a `.env` file in the project root with the following variables:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key

# Database Configuration
DB_URI=postgresql://username:password@localhost:5432/database_name

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Google Calendar Configuration
GOOGLE_CREDENTIALS_B64=base64_encoded_google_credentials_json
GOOGLE_TOKEN_B64=base64_encoded_token_pickle  # Optional, auto-generated

# Webhook Configuration
WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok.io
WEBSOCKET_BASE_URL=wss://your-ngrok-url.ngrok.io
```

### 3. Set up the database

Create the required tables by running the SQL script:

```bash
psql -d your_database -f generate_tables.sql
```

### 4. Set up Google Calendar API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API
4. Create credentials (OAuth 2.0 Client ID)
5. Download the credentials JSON file
6. Base64 encode the JSON file and add it to your `.env` as `GOOGLE_CREDENTIALS_B64`

### 5. Set up Twilio

1. Create a [Twilio account](https://www.twilio.com/)
2. Purchase a phone number with voice capabilities
3. Configure the webhook URL in your Twilio phone number settings
4. Add your Twilio credentials to the `.env` file

### 6. Set up ngrok

1. Install ngrok: `brew install ngrok` (macOS) or download from [ngrok.com](https://ngrok.com/)
2. Get your authtoken from the [ngrok dashboard](https://dashboard.ngrok.com/)
3. Configure ngrok: `ngrok config add-authtoken your_ngrok_token`

### 7. Run the application

#### Production Setup (Recommended)
```bash
# Start all servers and ngrok tunnels
python start_servers.py
```

This will start:
- Flask server on port 5000
- WebSocket server on port 5001
- ngrok tunnels for webhooks
- All necessary background processes

#### Development Setup
```bash
# Start individual components
python app.py                    # Flask server
python lgch_todo/http_websocket_server.py  # WebSocket server
python setup_ngrok_tunnels.py   # ngrok tunnels
```

#### Access Points
- `http://localhost:5000/lgch_todo/` - LGCH Todo web interface
- `http://localhost:5000/lgch-tech-spec` - Technical specification page
- `ws://localhost:5001/ws` - WebSocket endpoint for voice calls

## 🎤 Using Luna

### Phone Voice Interface (Production)
1. Run the application with `python start_servers.py`
2. Call your Twilio phone number
3. Speak your request naturally (e.g., "Create a high priority todo to finish the project report by tomorrow")
4. Luna will process your request, interact with the database and Google Calendar, and respond verbally
5. Continue the conversation or hang up to end the call

### Web Interface
1. Run the Flask application with `python app.py`
2. Visit `http://localhost:5000/lgch_todo/` for the web interface
3. Use the REST API endpoint `/lgch_todo/run_agent` to interact with Luna programmatically

#### API Usage
Send a POST request to `/lgch_todo/run_agent` with JSON payload:

```json
{
  "prompt": "Create a high priority todo to finish the project report by tomorrow"
}
```

Response:
```json
{
  "result": "I've created a high priority todo for you: 'Finish the project report by tomorrow'. The task has been added to your todo list and synced with your Google Calendar."
}
```

### Example Commands

**Todo Management:**
- "Create a todo to buy groceries with high priority"
- "Show me all my pending todos"
- "Mark the grocery shopping todo as completed"
- "Delete the old project todo"

**Reminder Management:**
- "Create a reminder to call mom tomorrow at 2 PM"
- "Set a reminder for the doctor appointment next week"
- "Delete the reminder about the meeting"

**Calendar Events:**
- "Schedule a meeting for next Friday from 2 to 3 PM"
- "What's on my calendar for this week?"
- "Create a calendar event for the team standup tomorrow"

**General:**
- "What can you help me with?"
- "Show me my productivity summary"
- "Help me organize my tasks for today"

## 🧩 Project Structure

```plaintext
Project Root/
├── app.py                       # Main Flask application
├── start_servers.py             # Production server startup script
├── setup_ngrok_tunnels.py       # ngrok tunnel management
├── ngrok.yml                    # ngrok configuration file
├── requirements.txt             # Python dependencies
├── recordings/                  # Call recording storage (git-ignored)
└── lgch_todo/                   # LGCH Todo module
    ├── __init__.py              # Package initialization, exports blueprint
    ├── routes.py                # Flask routes and Twilio webhooks
    ├── http_websocket_server.py # Hybrid HTTP/WebSocket server
    ├── twilio_handler.py        # Twilio Media Streams handler
    ├── assistant_graph_todo.py  # LangGraph agent definition
    ├── state.py                 # Agent state management
    ├── voice_utils.py           # Audio recording and playback
    ├── generate_tables.sql      # Database schema
    ├── templates/               # Flask templates
    │   └── lgch_todo_index.html # Web interface template
    └── mcps/                    # Model Context Protocol servers
        ├── mcp_config.json      # MCP server configuration
        └── local_servers/
            ├── db_todo.py       # Database operations via MCP
            └── google_calendar.py # Calendar operations via MCP
```

### Flask Integration
The project is integrated into a larger Flask application with the following structure:

```plaintext
main_project/
├── app.py                       # Main Flask application
├── lgch_todo/                   # LGCH Todo module (this project)
├── syfw_todo/                   # Other todo modules
├── vapi_todo/                   # Other todo modules
├── blnd_todo/                   # Other todo modules
└── templates/
    └── lgch_tech_spec.html      # Technical specification page
```

## 🔧 Customizing the Agent

### Modifying the System Prompt

To change Luna's personality or capabilities, edit the `system_prompt` in `assistant_graph_todo.py`:

```python
system_prompt = """You are Luna, the personal productivity assistant...
```

### Flask Integration Customization

The Flask integration provides a REST API endpoint at `/lgch_todo/run_agent`. You can customize the web interface by:

1. **Modifying the template**: Edit `templates/lgch_todo_index.html` to change the web interface
2. **Adding new endpoints**: Add new routes in `routes.py` for additional functionality
3. **Customizing the API response**: Modify the `run_agent` function in `routes.py` to change how responses are formatted

### Adding New Tools

1. Create a new MCP server or add tools to the existing one in `mcps/local_servers/`
2. Register the server in `mcps/mcp_config.json`
3. The tools will be automatically available to the agent

### Changing Voice Settings

Modify the TTS settings in `voice_utils.py`:

```python
async def play_audio(message: str):
    # ...
    async with openai_async.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="fable",  # Change the voice here
        input=cleaned_message,
        instructions="Speak in a cheerful, helpful tone with a brisk pace.",  # Modify instructions
        response_format="pcm",
        speed=1.2,  # Adjust speed
    ) as response:
        # ...
```

## 📊 Database Schema

The application uses the following tables:

- **todos_lgch**: Todo items with title, description, priority, due date, and completion status
- **reminders_lgch**: Reminders with text, importance level, and reminder date
- **calendar_events_lgch**: Calendar events with title, description, start/end times
- **call_recordings_lgch**: Call recording metadata and file paths

All tables include Google Calendar event IDs for synchronization and are prefixed with `lgch_` for namespace isolation.

## 🔄 Google Calendar Integration

- **Automatic Sync**: All todos, reminders, and events are automatically synchronized with Google Calendar
- **Event Creation**: Todos become calendar events with "TODO:" prefix
- **Status Updates**: Completed todos update their calendar events to "COMPLETED:"
- **Reminder Events**: Reminders become calendar events with "REMINDER:" prefix
- **Cleanup**: Deleted items remove their associated calendar events
- **Bidirectional Sync**: Changes in Google Calendar can be reflected back to the system

## 🧪 Test Results and Validation

The LGCH Todo system has been thoroughly tested with a focus on the core MCP tools: create_todo, complete_todo, create_reminder, and delete_reminder functionality. All tests demonstrate successful integration across voice interface, database operations, and Google Calendar synchronization.

### Tested Components

1. **Create Todo Tool**: Voice input → Speech-to-Text → LangGraph Agent → create_todo MCP Tool → Database Storage → Google Calendar Sync → Text-to-Speech Response
2. **Complete Todo Tool**: Voice input → Speech-to-Text → LangGraph Agent → complete_todo MCP Tool → Database Update → Google Calendar Update → Text-to-Speech Response
3. **Create Reminder Tool**: Voice input → Speech-to-Text → LangGraph Agent → create_reminder MCP Tool → Database Storage → Google Calendar Sync → Text-to-Speech Response
4. **Delete Reminder Tool**: Voice input → Speech-to-Text → LangGraph Agent → delete_reminder MCP Tool → Database Removal → Google Calendar Removal → Text-to-Speech Response

### Supporting Infrastructure

- ✅ LangGraph Agent Processing
- ✅ Text-to-Speech (OpenAI TTS)
- ✅ WebSocket Communication
- ✅ ngrok Tunnel Management
- ✅ MCP Server Integration
- ✅ Twilio Phone Integration

## 📚 Learning Resources

- [Intro to LangGraph](https://youtu.be/31JoTDm7jkM)
- [Deploy LangGraph Agents](https://youtu.be/SGt786ne_Mk)
- [MCP with LangGraph Agents](https://youtu.be/F9mgEFor0cA)
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph/)
- [OpenAI API Documentation](https://platform.openai.com/docs/introduction)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction)
- [Twilio Voice API Documentation](https://www.twilio.com/docs/voice)
- [ngrok Documentation](https://ngrok.com/docs)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- [WebSocket Documentation](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.
