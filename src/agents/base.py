"""BaseAgent with version check. All agents require PIPELINE_VERSION=v3."""

from abc import ABC

from src.config.settings import get_settings


class BaseAgent(ABC):
    """Base for all V3 agents. _check_version() raises NotImplementedError unless v3."""

    version_required: str = "v3"

    def _check_version(self) -> None:
        settings = get_settings()
        if settings.pipeline_version != self.version_required:
            raise NotImplementedError(
                f"{self.__class__.__name__} requires PIPELINE_VERSION={self.version_required}. "
                f"Current: PIPELINE_VERSION={settings.pipeline_version}"
            )
