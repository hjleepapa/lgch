import logging
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import InMemorySaver
from typing import List
from dotenv import load_dotenv

from .state import AgentState
from .mcps.local_servers.db_todo import TodoPriority, ReminderImportance


load_dotenv()

# Configure logging to suppress HTTP request logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


class TodoAgent:
    def __init__(
            self,
            name: str = "Luna",
            model: str = "gpt-4.1-mini-2025-04-14",
            #model: str = "gpt-5-nano-2025-08-07",
            #model: str = "gpt-4o-cluster",
            tools: List[BaseTool] = [],
            system_prompt: str = """You are Luna, the personal productivity assistant. You are responsible for helping users manage their todo lists, reminders, and calendar events. You have access to create, update, delete, and query todos, reminders, and calendar events.

            Your messages are read aloud to the user, so respond in a way that is easy to understand when spoken. Be brief and to the point.

            When creating new todos, you must classify the priority into one of the allowed levels below. Make reasonable assumptions when users don't specify:
            - Shopping tasks: typically medium priority
            - Work/urgent tasks: typically high priority  
            - Personal/hobby tasks: typically low priority
            - If user mentions "now" or a specific date, use that as the due date
            - If no priority is specified, default to medium
            - If no due date is specified, ALWAYS default to today (current date)
            
            IMPORTANT: Always provide a due_date when creating todos. If the user doesn't specify a date, use today's date as the default.

            <todo_priorities>
            {todo_priorities}
            </todo_priorities>

            <reminder_importance>
            {reminder_importance}
            </reminder_importance>

            <db_schema>
            You have access to a database with the following schema:
            - todos_lgch (id, created_at, updated_at, title, description, completed, priority, due_date, google_calendar_event_id)
            - reminders_lgch (id, created_at, updated_at, reminder_text, importance, reminder_date, google_calendar_event_id)
            - calendar_events_lgch (id, created_at, updated_at, title, description, event_from, event_to, google_calendar_event_id)
            </db_schema>

            All todos, reminders, and calendar events are automatically synchronized with Google Calendar.

            Available tools:
            - create_todo: Create a new todo item with title, description, priority, and optional due date
            - get_todos: Get all todo items
            - complete_todo: Mark a todo as completed
            - update_todo: Update todo properties (title, description, priority, due_date, completed status)
            - delete_todo: Delete a todo item
            - create_reminder: Create a new reminder with text, importance, and optional reminder date
            - get_reminders: Get all reminders
            - delete_reminder: Delete a reminder
            - create_calendar_event: Create a calendar event with title, start/end times, and description
            - get_calendar_events: Get all calendar events
            - delete_calendar_event: Delete a calendar event
            - query_db: Execute custom SQL queries on the database

            When users ask about their productivity, help them organize their tasks, set priorities, and manage their time effectively.
            """,
            ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.tools = tools

        self.llm = ChatOpenAI(name=self.name, model=model).bind_tools(tools=self.tools)
        self.graph = self.build_graph()

    def build_graph(self,) -> CompiledStateGraph:
        builder = StateGraph(AgentState)

        def assistant(state: AgentState):
            """The main assistant node that uses the LLM to generate responses."""
            # inject todo priorities and reminder importance into the system prompt
            system_prompt = self.system_prompt.format(
                todo_priorities=", ".join([p.value for p in TodoPriority]),
                reminder_importance=", ".join([i.value for i in ReminderImportance])
                )

            response = self.llm.invoke([SystemMessage(content=system_prompt)] + state.messages)
            state.messages.append(response)
            return state

        builder.add_node(assistant)
        builder.add_node(ToolNode(self.tools))

        builder.set_entry_point("assistant")
        builder.add_conditional_edges(
            "assistant",
            tools_condition
        )
        builder.add_edge("tools", "assistant")

        return builder.compile(checkpointer=InMemorySaver())

    def draw_graph(self,):
        if self.graph is None:
            raise ValueError("Graph not built yet")
        from IPython.display import Image

        return Image(self.graph.get_graph().draw_mermaid_png())

agent = TodoAgent()

if __name__ == "__main__":
    agent.draw_graph()
