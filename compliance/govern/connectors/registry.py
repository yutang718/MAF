from govern.connectors.archery import ArcheryConnector
from govern.connectors.base import Connector
from govern.connectors.github import GitHubConnector
from govern.connectors.gitlab import GitLabConnector
from govern.connectors.m365 import M365Connector

CONNECTOR_TYPES: dict[str, type[Connector]] = {
    cls.kind: cls for cls in (M365Connector, GitHubConnector, GitLabConnector, ArcheryConnector)
}
