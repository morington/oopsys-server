from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    CRITICAL = "critical"


class Source(str, Enum):
    PROJECTS = "projects"
    SERVER = "server"
    DOCKER = "docker"
    AGENT = "agent"


class AgentStatus(str, Enum):
    ONLINE = "online"
    DOWN = "down"


class ErrorGroupStatus(str, Enum):
    OPEN = "open"
    MUTED = "muted"
    RESOLVED = "resolved"


class NotificationKind(str, Enum):
    ERROR = "error"
    AGENT_DOWN = "agent_down"
    AGENT_RECOVERED = "agent_recovered"
    AGENT_FAULT = "agent_fault"
    SERVER_ERROR = "server_error"


class BotStatus(str, Enum):
    PENDING = "pending"
    LINKED = "linked"
    DISABLED = "disabled"
