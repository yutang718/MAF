"""Connector contract: read-only collection of facts and events from one source."""
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from govern.log import get_logger

logger = get_logger(__name__)


class SourceUnavailable(Exception):
    """The source can't provide this fact here: missing licence, permission or API tier.

    Not a failure of the organisation's controls, so checks that need the fact
    report "not available" instead of "fail".
    """


@dataclass(frozen=True)
class ConfigField:
    name: str
    label: dict[str, str]
    type: str = "string"  # string | int | bool | list | secret
    required: bool = False
    default: Any = None
    help: dict[str, str] | None = None

    @property
    def secret(self) -> bool:
        return self.type == "secret"


@dataclass
class EventRecord:
    kind: str
    external_id: str
    occurred_at: datetime
    actor: str = ""
    action: str = ""
    target: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Collected:
    facts: dict[str, Any] = field(default_factory=dict)
    unavailable: dict[str, str] = field(default_factory=dict)  # fact key -> reason
    errors: dict[str, str] = field(default_factory=dict)  # fact key -> unexpected error
    events: list[EventRecord] = field(default_factory=list)
    cursor: dict[str, Any] = field(default_factory=dict)
    # Expensive facts not refreshed this run; the collector reuses their last snapshot.
    carry_forward: set[str] = field(default_factory=set)

    def gather(self, key: str, fetch: Callable[[], Any]) -> Any:
        """Collect one fact, recording why if it can't be had. Returns the value or None."""
        try:
            value = fetch()
        except SourceUnavailable as e:
            self.unavailable[key] = str(e)
            return None
        except Exception as e:  # one broken endpoint shouldn't sink the whole run
            logger.exception(f"collecting {key} failed")
            self.errors[key] = f"{type(e).__name__}: {e}"
            return None
        self.facts[key] = value
        return value


class Connector(ABC):
    kind: ClassVar[str]
    title: ClassVar[dict[str, str]]
    fields: ClassVar[tuple[ConfigField, ...]]
    # Rough guidance shown in the UI next to the connector form.
    permissions_help: ClassVar[dict[str, str]] = {}

    def __init__(self, config: dict[str, Any], secrets: dict[str, str], cursor: dict[str, Any] | None = None):
        self.config = {f.name: config.get(f.name, f.default) for f in self.fields if not f.secret}
        self.secrets = secrets
        self.cursor = dict(cursor or {})

    @abstractmethod
    def test(self) -> str:
        """Authenticate and make one cheap call. Returns a human-readable success note."""

    @abstractmethod
    def collect(self) -> Collected:
        """Pull current facts and new events since self.cursor."""

    def close(self) -> None:
        pass


def validate_config(cls: type[Connector], config: dict[str, Any], secrets: dict[str, str],
                    existing_secrets: dict[str, str] | None = None) -> None:
    missing = []
    for f in cls.fields:
        if not f.required:
            continue
        if f.secret:
            if not (secrets.get(f.name) or (existing_secrets or {}).get(f.name)):
                missing.append(f.name)
        elif config.get(f.name) in (None, "", []):
            missing.append(f.name)
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
