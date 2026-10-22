"""core.settings — the one place ops reads the machine: every section of `config/`, composed.

Paths and knobs are a contract, not a lookup scattered across modules: every module
imports `settings` and nobody calls os.environ. The values live in one file,
`ops/config/settings.yaml`, split by section and never deeper than two levels; each
section is one class in `ops/config/`. The environment overrides any key as
`OPS_<SECTION>__<KEY>` (OPS_TRANSPILER__TARGETS__OPENCODE=/tmp/replica op transpiler check).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar, Final

from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource

from ops.config.common import CommonConfig
from ops.config.distill import DistillConfig
from ops.config.docs import DocsConfig
from ops.config.evaluator import EvaluatorConfig
from ops.config.layout import LayoutConfig
from ops.config.promote import PromoteConfig
from ops.config.reports import ReportsConfig
from ops.config.runners import RunnersConfig
from ops.config.tools import ToolsConfig
from ops.config.transpiler import TranspilerConfig
from ops.config.wiring import WiringConfig

#: The file every section is read from.
SETTINGS_FILE: Final[Path] = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"


class GlobalEnvSource(PydanticBaseSettingsSource):
    """`OPS_GLOBAL__<KEY>` into the `global` section.

    `global` is a keyword, so its field is `global_` with an alias — and pydantic-settings
    neither prefixes nor explodes the nested delimiter of an aliased field. This source
    restores the contract every other section has.
    """

    PREFIX: ClassVar[str] = "OPS_GLOBAL__"

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        found = {
            key[len(self.PREFIX) :].lower(): value for key, value in os.environ.items() if key.startswith(self.PREFIX)
        }
        return {"global": found} if found else {}


class Settings(BaseSettings):
    """Where ops reads its source and writes its output, on this machine."""

    model_config = SettingsConfigDict(
        yaml_file=SETTINGS_FILE,
        env_prefix="OPS_",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    #: The repo: resolved from this file so cwd never matters.
    ROOT: ClassVar[Path] = Path(__file__).resolve().parents[2]

    global_: CommonConfig = Field(default_factory=CommonConfig, alias="global")
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    wiring: WiringConfig = Field(default_factory=WiringConfig)
    transpiler: TranspilerConfig = Field(default_factory=TranspilerConfig)
    eval: EvaluatorConfig = Field(default_factory=EvaluatorConfig)
    reports: ReportsConfig = Field(default_factory=ReportsConfig)
    promote: PromoteConfig = Field(default_factory=PromoteConfig)
    runners: RunnersConfig = Field(default_factory=RunnersConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    docs: DocsConfig = Field(default_factory=DocsConfig)
    distill: DistillConfig = Field(default_factory=DistillConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """kwargs > environment > the YAML file. No dotenv, no secrets dir: one file is the contract."""
        return init_settings, env_settings, GlobalEnvSource(settings_cls), YamlConfigSettingsSource(settings_cls)

    @property
    def reports_dir(self) -> Path:
        """The reports root, anchored at the repo when the file names it relatively."""
        return self.reports.dir if self.reports.dir.is_absolute() else self.ROOT / self.reports.dir

    def run_dir(self, run_id: str) -> Path:
        """A run's folder: a workflow's under `workflows/<workflow>/`, so each keeps its own history; the rest flat.

        The id is `<stamp>-<plane>-<name>-<sha>`, so the folder follows from it alone — writing, resuming and
        resolving agree without reading anything."""
        match run_id.split("-"):
            case [_, "workflow", *name, _] if name:
                return self.reports_dir / "workflows" / "-".join(name) / run_id
            case _:
                return self.reports_dir / run_id


settings = Settings()
