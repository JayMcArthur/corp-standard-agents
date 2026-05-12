class TeamAgentsError(Exception):
    """Base error for expected command failures."""


class ValidationError(TeamAgentsError):
    """Raised when repository or config data is malformed."""


class ResolutionError(TeamAgentsError):
    """Raised when a workspace cannot be resolved safely."""


class ProtectionError(TeamAgentsError):
    """Raised when local write protection cannot be installed."""


class GitError(TeamAgentsError):
    """Raised for git command failures."""

