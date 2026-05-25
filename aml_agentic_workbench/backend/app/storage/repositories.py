"""Repository abstractions for persistence operations."""

from sqlalchemy.orm import Session

from app.storage.models import AgentRun, AuditLog, JudgeResult, Report


class AgentRunRepository:
    """Persistence operations for agent runs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, run: AgentRun) -> AgentRun:
        """Persist an agent run."""
        self.session.add(run)
        return run

    def get(self, run_id: str) -> AgentRun | None:
        """Fetch an agent run by identifier."""
        return self.session.get(AgentRun, run_id)


class ReportRepository:
    """Persistence operations for reports."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, report: Report) -> Report:
        """Persist a report."""
        self.session.add(report)
        return report


class AuditLogRepository:
    """Persistence operations for audit logs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, log: AuditLog) -> AuditLog:
        """Persist an audit log."""
        self.session.add(log)
        return log


class JudgeResultRepository:
    """Persistence operations for judge results."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, result: JudgeResult) -> JudgeResult:
        """Persist a judge result."""
        self.session.add(result)
        return result

