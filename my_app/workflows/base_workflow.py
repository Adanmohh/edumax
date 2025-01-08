from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import logging
import sys
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

class WorkflowEvent(BaseModel):
    """Base class for workflow events"""
    timestamp: datetime = datetime.utcnow()
    event_type: str
    event_data: Dict[str, Any] = {}

class WorkflowContext:
    """Context for storing workflow state"""
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.events: list[WorkflowEvent] = []
        
    def add_event(self, event: WorkflowEvent):
        """Add event to context history"""
        self.events.append(event)
        
    def get_events_by_type(self, event_type: str) -> list[WorkflowEvent]:
        """Get all events of a specific type"""
        return [e for e in self.events if e.event_type == event_type]
        
    def set_data(self, key: str, value: Any):
        """Set data in context"""
        self.data[key] = value
        
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data from context"""
        return self.data.get(key, default)

class BaseWorkflow:
    """Base class for all workflows"""
    
    def __init__(self, workflow_id: Optional[uuid.UUID] = None):
        self.workflow_id = workflow_id or uuid.uuid4()
        self.ctx = WorkflowContext()
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{self.workflow_id}")
        
        # Setup workflow artifacts directory
        self.workflow_artifacts_path = Path("workflow_artifacts")
        self.workflow_artifacts_path.mkdir(exist_ok=True)
        
        # Setup workflow-specific directory
        self.workflow_dir = self.workflow_artifacts_path / str(self.workflow_id)
        self.workflow_dir.mkdir(exist_ok=True)
        
    async def emit_event(self, event_type: str, event_data: Dict[str, Any] = {}):
        """Emit a workflow event"""
        event = WorkflowEvent(
            event_type=event_type,
            event_data=event_data
        )
        self.ctx.add_event(event)
        self.logger.info(f"Event emitted: {event_type}")
        return event
        
    async def handle_error(self, error: Exception, step: str):
        """Handle workflow errors"""
        error_event = await self.emit_event(
            "error",
            {
                "error": str(error),
                "step": step,
                "traceback": logging.traceback.format_exc()
            }
        )
        self.logger.error(f"Error in step {step}: {error}")
        return error_event
        
    def get_artifact_path(self, filename: str) -> Path:
        """Get path for workflow artifact"""
        return self.workflow_dir / filename
        
    async def run(self, *args, **kwargs):
        """Template method for workflow execution"""
        raise NotImplementedError("Workflow must implement run method")
        
    async def cleanup(self):
        """Cleanup workflow artifacts"""
        try:
            import shutil
            if self.workflow_dir.exists():
                shutil.rmtree(self.workflow_dir)
            self.logger.info("Workflow artifacts cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up workflow artifacts: {e}")
            
    def __str__(self):
        return f"{self.__class__.__name__}(workflow_id={self.workflow_id})"
