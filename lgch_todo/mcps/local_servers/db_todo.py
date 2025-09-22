from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import List, Optional
from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
import os
from pydantic import BaseModel
from enum import StrEnum
import pandas as pd
try:
    from google_calendar import get_calendar_service
except ImportError:
    # Fallback for when running as MCP server
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from google_calendar import get_calendar_service

load_dotenv()

# ----------------------------
# SQLAlchemy Models
# ----------------------------

class Base(DeclarativeBase):
     pass


class DBTodo(Base):
    __tablename__ = "todos_lgch"

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"), onupdate=datetime.now)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    priority: Mapped[str] = mapped_column(String, nullable=False, server_default=text("medium"))
    due_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    google_calendar_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class DBReminder(Base):
    __tablename__ = "reminders_lgch"

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"), onupdate=datetime.now)
    reminder_text: Mapped[str] = mapped_column(String, nullable=False)
    importance: Mapped[str] = mapped_column(String, nullable=False, server_default=text("medium"))
    reminder_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    google_calendar_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class DBCalendarEvent(Base):
    __tablename__ = "calendar_events_lgch"

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"), onupdate=datetime.now)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    event_from: Mapped[datetime] = mapped_column(nullable=False)
    event_to: Mapped[datetime] = mapped_column(nullable=False)
    google_calendar_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class DBCallRecording(Base):
    __tablename__ = "call_recordings_lgch"

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True, server_default=text("gen_random_uuid()"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    call_sid: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    from_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recording_path: Mapped[str] = mapped_column(String, nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    transcription: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'completed'"))  # completed, failed, processing 

# ----------------------------
# Pydantic Models
# ----------------------------

class TodoPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Todo(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    title: str
    description: Optional[str]
    completed: bool
    priority: TodoPriority
    due_date: Optional[datetime]
    google_calendar_event_id: Optional[str]


class ReminderImportance(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Reminder(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    reminder_text: str
    importance: ReminderImportance
    reminder_date: Optional[datetime]
    google_calendar_event_id: Optional[str]


class CalendarEvent(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    title: str
    description: Optional[str]
    event_from: datetime
    event_to: datetime
    google_calendar_event_id: Optional[str]


class CallRecording(BaseModel):
    id: UUID
    created_at: datetime
    call_sid: str
    from_number: Optional[str]
    to_number: Optional[str]
    recording_path: str
    duration_seconds: Optional[int]
    file_size_bytes: Optional[int]
    transcription: Optional[str]
    status: str

# ----------------------------
# DB Session
# ----------------------------

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(url=os.getenv("DB_URI"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ----------------------------
# MCP Server
# ----------------------------

mcp = FastMCP("db_todo")


@mcp.tool()
async def create_todo(
    title: str,
    description: Optional[str] = None,
    priority: TodoPriority = TodoPriority.MEDIUM,
    due_date: Optional[datetime] = None,
    ) -> str:
    """Create a new todo item.
    
    Args:
        title: The title of the todo item.
        description: An optional description of the todo item.
        priority: The priority level of the todo. Options are: low, medium, high, urgent
        due_date: The due date for the todo item. If not specified, will automatically default to today's date.

    Returns:
        The created todo item.
    """
    with SessionLocal() as session:
        # Set default due date to today if not provided
        if due_date is None:
            due_date = datetime.now(timezone.utc)
            
        new_todo = DBTodo(
            title=title,
            description=description,
            priority=priority.value,
            due_date=due_date,
            )
        session.add(new_todo)
        session.commit()
        session.refresh(new_todo)
        
        # Create corresponding calendar event
        try:
            # Set default times for calendar event
            start_time = due_date if due_date else datetime.now(timezone.utc)
            end_time = start_time + timedelta(hours=1)
            
            # Create local calendar event
            new_event = DBCalendarEvent(
                title=f"TODO: {title}",
                description=f"{description or ''}\n\nPriority: {priority.value}\nFrom: LGCH Todo System",
                event_from=start_time,
                event_to=end_time,
            )
            session.add(new_event)
            session.commit()
            session.refresh(new_event)
            
            # Sync with Google Calendar
            calendar_service = get_calendar_service()
            google_event_id = calendar_service.create_event(
                title=f"TODO: {title}",
                description=f"{description or ''}\n\nPriority: {priority.value}\nFrom: LGCH Todo System",
                start_time=start_time,
                end_time=end_time
            )
            if google_event_id:
                new_event.google_calendar_event_id = google_event_id
                new_todo.google_calendar_event_id = google_event_id
                session.commit()
                session.refresh(new_todo)
                session.refresh(new_event)
        except Exception as e:
            print(f"Failed to create calendar event or sync with Google Calendar: {e}")
    
    return Todo.model_validate(new_todo.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def get_todos() -> str:
    """Get all todo items.
    
    Returns:
        A list of all todo items.
    """
    with SessionLocal() as session:
        todos = session.query(DBTodo).all()
        todos_list = [Todo.model_validate(todo.__dict__).model_dump_json(indent=2) for todo in todos]
    return f"[{', \n'.join(todos_list)}]"

@mcp.tool()
async def complete_todo(id: UUID) -> str:
    """Mark a todo item as completed.
    
    Args:
        id: The id of the todo item to complete.

    Returns:
        The updated todo item.
    """
    with SessionLocal() as session:
        todo = session.query(DBTodo).filter(DBTodo.id == id).first()
        if not todo:
            return "Todo not found"
        
        todo.completed = True
        session.commit()
        
        # Update Google Calendar event
        if todo.google_calendar_event_id:
            try:
                calendar_service = get_calendar_service()
                calendar_service.update_event(
                    event_id=todo.google_calendar_event_id,
                    title=f"COMPLETED: {todo.title}",
                    description=f"{todo.description or ''}\n\nPriority: {todo.priority}\nStatus: Completed\nFrom: LGCH Todo System"
                )
            except Exception as e:
                print(f"Failed to update Google Calendar event: {e}")
        
        session.refresh(todo)
    
    return Todo.model_validate(todo.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def update_todo(
    id: UUID,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[TodoPriority] = None,
    due_date: Optional[datetime] = None,
    completed: Optional[bool] = None,
    ) -> str:
    """Update a todo item by id.
    
    Args:
        id: The id of the todo item to update.
        title: The new title of the todo item.
        description: The new description of the todo item.
        priority: The new priority level of the todo. Options are: low, medium, high, urgent
        due_date: The new due date for the todo item.
        completed: The new completion status of the todo item.

    Returns:
        The updated todo item.
    """
    with SessionLocal() as session:
        todo = session.query(DBTodo).filter(DBTodo.id == id).first()
        if not todo:
            return "Todo not found"
        
        if title:
            todo.title = title
        if description is not None:
            todo.description = description
        if priority:
            todo.priority = priority.value
        if due_date is not None:
            todo.due_date = due_date
        if completed is not None:
            todo.completed = completed

        session.commit()
        session.refresh(todo)
    
    return Todo.model_validate(todo.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def delete_todo(id: UUID) -> str:
    """Delete a todo item by id.
    
    Args:
        id: The id of the todo item to delete.

    Returns:
        The deleted todo item.
    """
    with SessionLocal() as session:
        todo = session.query(DBTodo).filter(DBTodo.id == id).first()
        if not todo:
            return "Todo not found"
        
        # Delete from Google Calendar first
        if todo.google_calendar_event_id:
            try:
                calendar_service = get_calendar_service()
                calendar_service.delete_event(todo.google_calendar_event_id)
            except Exception as e:
                print(f"Failed to delete Google Calendar event: {e}")
        
        session.delete(todo)
        session.commit()
    
    return Todo.model_validate(todo.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def create_reminder(
    reminder_text: str,
    importance: ReminderImportance = ReminderImportance.MEDIUM,
    reminder_date: Optional[datetime] = None,
    ) -> str:
    """Create a new reminder.
    
    Args:
        reminder_text: The text content of the reminder.
        importance: The importance level of the reminder. Options are: low, medium, high, urgent
        reminder_date: An optional date/time for the reminder.

    Returns:
        The created reminder.
    """
    with SessionLocal() as session:
        # Handle both string and enum inputs for importance
        importance_value = importance.value if hasattr(importance, 'value') else importance
        
        new_reminder = DBReminder(
            reminder_text=reminder_text,
            importance=importance_value,
            reminder_date=reminder_date,
            )
        session.add(new_reminder)
        session.commit()
        session.refresh(new_reminder)
        
        # Create corresponding calendar event
        try:
            # Set default times for calendar event
            start_time = reminder_date if reminder_date else datetime.now(timezone.utc)
            end_time = start_time + timedelta(minutes=30)  # Reminders are typically shorter events
            
            # Create local calendar event
            new_event = DBCalendarEvent(
                title=f"REMINDER: {reminder_text}",
                description=f"Importance: {importance_value}\nFrom: LGCH Todo System",
                event_from=start_time,
                event_to=end_time,
            )
            session.add(new_event)
            session.commit()
            session.refresh(new_event)
            
            # Sync with Google Calendar
            calendar_service = get_calendar_service()
            google_event_id = calendar_service.create_event(
                title=f"REMINDER: {reminder_text}",
                description=f"Importance: {importance_value}\nFrom: LGCH Todo System",
                start_time=start_time,
                end_time=end_time
            )
            if google_event_id:
                new_event.google_calendar_event_id = google_event_id
                new_reminder.google_calendar_event_id = google_event_id
                session.commit()
                session.refresh(new_reminder)
                session.refresh(new_event)
        except Exception as e:
            print(f"Failed to create calendar event or sync reminder with Google Calendar: {e}")
    
    return Reminder.model_validate(new_reminder.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def get_reminders() -> str:
    """Get all reminders.
    
    Returns:
        A list of all reminders.
    """
    with SessionLocal() as session:
        reminders = session.query(DBReminder).all()
        reminders_list = [Reminder.model_validate(reminder.__dict__).model_dump_json(indent=2) for reminder in reminders]
    return f"[{', \n'.join(reminders_list)}]"

@mcp.tool()
async def delete_reminder(id: UUID) -> str:
    """Delete a reminder by id.
    
    Args:
        id: The id of the reminder to delete.

    Returns:
        The deleted reminder.
    """
    with SessionLocal() as session:
        reminder = session.query(DBReminder).filter(DBReminder.id == id).first()
        if not reminder:
            return "Reminder not found"
        
        # Delete from Google Calendar first
        if reminder.google_calendar_event_id:
            try:
                calendar_service = get_calendar_service()
                calendar_service.delete_event(reminder.google_calendar_event_id)
            except Exception as e:
                print(f"Failed to delete Google Calendar event: {e}")
        
        session.delete(reminder)
        session.commit()
    
    return Reminder.model_validate(reminder.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def create_calendar_event(
    title: str,
    event_from: datetime,
    event_to: datetime,
    description: Optional[str] = None,
    ) -> str:
    """Create a new calendar event.
    
    Args:
        title: The title of the calendar event.
        event_from: The start date and time of the event.
        event_to: The end date and time of the event.
        description: An optional description of the event.

    Returns:
        The created calendar event.
    """
    with SessionLocal() as session:
        new_event = DBCalendarEvent(
            title=title,
            description=description,
            event_from=event_from,
            event_to=event_to,
            )
        session.add(new_event)
        session.commit()
        session.refresh(new_event)
        
        # Sync with Google Calendar
        try:
            print(f"🔄 Attempting to sync calendar event: {title}")
            calendar_service = get_calendar_service()
            google_event_id = calendar_service.create_event(
                title=title,
                description=f"{description or ''}\n\nFrom: LGCH Todo System",
                start_time=event_from,
                end_time=event_to
            )
            if google_event_id:
                new_event.google_calendar_event_id = google_event_id
                session.commit()
                session.refresh(new_event)
                print(f"✅ Successfully created Google Calendar event: {google_event_id}")
            else:
                print("❌ Google Calendar event creation returned None")
        except Exception as e:
            print(f"❌ Failed to sync calendar event with Google Calendar: {e}")
            import traceback
            traceback.print_exc()
    
    return CalendarEvent.model_validate(new_event.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def get_calendar_events() -> str:
    """Get all calendar events.
    
    Returns:
        A list of all calendar events.
    """
    with SessionLocal() as session:
        events = session.query(DBCalendarEvent).all()
        events_list = [CalendarEvent.model_validate(event.__dict__).model_dump_json(indent=2) for event in events]
    return f"[{', \n'.join(events_list)}]"

@mcp.tool()
async def delete_calendar_event(id: UUID) -> str:
    """Delete a calendar event by id.
    
    Args:
        id: The id of the calendar event to delete.

    Returns:
        The deleted calendar event.
    """
    with SessionLocal() as session:
        event = session.query(DBCalendarEvent).filter(DBCalendarEvent.id == id).first()
        if not event:
            return "Calendar event not found"
        
        # Delete from Google Calendar first
        if event.google_calendar_event_id:
            try:
                calendar_service = get_calendar_service()
                calendar_service.delete_event(event.google_calendar_event_id)
            except Exception as e:
                print(f"Failed to delete Google Calendar event: {e}")
        
        session.delete(event)
        session.commit()
    
    return CalendarEvent.model_validate(event.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def create_call_recording(
    call_sid: str,
    recording_path: str,
    from_number: Optional[str] = None,
    to_number: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    file_size_bytes: Optional[int] = None,
    transcription: Optional[str] = None,
    status: str = "completed"
) -> str:
    """Create a new call recording record.
    
    Args:
        call_sid: Twilio Call SID (unique identifier)
        recording_path: Path to the audio recording file
        from_number: Caller's phone number
        to_number: Called phone number
        duration_seconds: Duration of the recording in seconds
        file_size_bytes: Size of the recording file in bytes
        transcription: Text transcription of the call
        status: Recording status (completed, failed, processing)

    Returns:
        The created call recording record
    """
    with SessionLocal() as session:
        recording = DBCallRecording(
            call_sid=call_sid,
            recording_path=recording_path,
            from_number=from_number,
            to_number=to_number,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size_bytes,
            transcription=transcription,
            status=status
        )
        session.add(recording)
        session.commit()
        session.refresh(recording)
    
    return CallRecording.model_validate(recording.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def get_call_recordings() -> str:
    """Get all call recordings.
    
    Returns:
        A list of all call recordings
    """
    with SessionLocal() as session:
        recordings = session.query(DBCallRecording).order_by(DBCallRecording.created_at.desc()).all()
    
    return [CallRecording.model_validate(recording.__dict__).model_dump() for recording in recordings]

@mcp.tool()
async def get_call_recording_by_sid(call_sid: str) -> str:
    """Get a call recording by Call SID.
    
    Args:
        call_sid: Twilio Call SID to search for

    Returns:
        The call recording record or error message
    """
    with SessionLocal() as session:
        recording = session.query(DBCallRecording).filter(DBCallRecording.call_sid == call_sid).first()
        
        if not recording:
            return f"Call recording with SID {call_sid} not found"
    
    return CallRecording.model_validate(recording.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def update_call_recording(
    call_sid: str,
    transcription: Optional[str] = None,
    status: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    file_size_bytes: Optional[int] = None
) -> str:
    """Update a call recording record.
    
    Args:
        call_sid: Twilio Call SID to update
        transcription: Updated transcription text
        status: Updated recording status
        duration_seconds: Updated duration in seconds
        file_size_bytes: Updated file size in bytes

    Returns:
        The updated call recording record
    """
    with SessionLocal() as session:
        recording = session.query(DBCallRecording).filter(DBCallRecording.call_sid == call_sid).first()
        
        if not recording:
            return f"Call recording with SID {call_sid} not found"
        
        if transcription is not None:
            recording.transcription = transcription
        if status is not None:
            recording.status = status
        if duration_seconds is not None:
            recording.duration_seconds = duration_seconds
        if file_size_bytes is not None:
            recording.file_size_bytes = file_size_bytes
            
        session.commit()
        session.refresh(recording)
    
    return CallRecording.model_validate(recording.__dict__).model_dump_json(indent=2)

@mcp.tool()
async def delete_call_recording(call_sid: str) -> str:
    """Delete a call recording by Call SID.
    
    Args:
        call_sid: Twilio Call SID to delete

    Returns:
        Success message or error
    """
    with SessionLocal() as session:
        recording = session.query(DBCallRecording).filter(DBCallRecording.call_sid == call_sid).first()
        
        if not recording:
            return f"Call recording with SID {call_sid} not found"
        
        # Delete the actual file if it exists
        try:
            if os.path.exists(recording.recording_path):
                os.remove(recording.recording_path)
        except Exception as e:
            return f"Error deleting file: {str(e)}"
        
        session.delete(recording)
        session.commit()
    
    return f"Call recording {call_sid} deleted successfully"

@mcp.tool()
async def query_db(query: str) -> str:
    """Query the database using SQL.
    
    Args:
        query: A valid PostgreSQL query to run.

    Returns:
        The query results
    """
    with SessionLocal() as session:
        result = session.execute(text(query))
        
    return pd.DataFrame(result.all(), columns=result.keys()).to_json(orient="records", indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio") 