import re
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from pydantic import BaseModel, Field, field_validator


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    description: str = Field(default="", max_length=4000)


class ImageInput(BaseModel):
    reference: str = Field(min_length=1, max_length=500, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9./:@_-]*$")
    version: str = Field(min_length=1, max_length=100)


class RunInput(BaseModel):
    deployment_id: str
    spider: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_.-]+$")
    arguments: dict[str, str] = Field(default_factory=dict, max_length=100)
    settings: dict[str, str | int | float | bool] = Field(default_factory=dict, max_length=100)
    environment_id: str | None = None
    timeout: int = Field(default=3600, ge=10, le=604800)
    memory_mb: int = Field(default=512, ge=64, le=32768)
    cpu: float = Field(default=1, ge=0.1, le=32)
    max_retries: int = Field(default=0, ge=0, le=5)
    retry_delay: int = Field(default=30, ge=1, le=3600)
    criteria: dict[str, int] = Field(default_factory=dict)

    @field_validator("settings")
    @classmethod
    def allowed_settings(cls, v):
        allowed = {
            "LOG_LEVEL",
            "CONCURRENT_REQUESTS",
            "DOWNLOAD_DELAY",
            "DOWNLOAD_TIMEOUT",
            "ROBOTSTXT_OBEY",
            "RETRY_TIMES",
            "USER_AGENT",
            "CLOSESPIDER_TIMEOUT",
            "CLOSESPIDER_ITEMCOUNT",
            "AUTOTHROTTLE_ENABLED",
        }
        if set(v) - allowed:
            raise ValueError(f"Allowed settings: {', '.join(sorted(allowed))}")
        return v

    @field_validator("arguments")
    @classmethod
    def valid_args(cls, v):
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) or len(val) > 10000 for k, val in v.items()):
            raise ValueError("Invalid argument name or value length")
        return v

    @field_validator("criteria")
    @classmethod
    def valid_criteria(cls, v):
        if set(v) - {"min_items", "max_errors"} or any(x < 0 for x in v.values()):
            raise ValueError("Criteria supports nonnegative min_items and max_errors")
        return v


class ScheduleInput(RunInput):
    name: str = Field(min_length=1, max_length=100)
    cron: str | None = None
    timezone: str = "UTC"
    run_at: datetime | None = None
    overlap: Literal["allow", "forbid"] = "forbid"
    misfire: Literal["skip", "catch_up"] = "skip"
    max_concurrent: int = Field(default=1, ge=1, le=100)

    @field_validator("cron")
    @classmethod
    def valid_cron(cls, v):
        if v is not None and (len(v.split()) != 5 or not croniter.is_valid(v)):
            raise ValueError("Use a valid five-field cron expression")
        return v

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, v):
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as e:
            raise ValueError("Unknown IANA timezone") from e
        return v


class BuildOptions(BaseModel):
    python: Literal["3.12", "3.13"] = "3.12"
    build_args: dict[str, str] = Field(default_factory=dict)

    @field_validator("build_args")
    @classmethod
    def allowed(cls, v):
        if set(v) - {"PIP_INDEX_URL", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"}:
            raise ValueError("Only package index and proxy build arguments are allowed")
        return v


class LoginInput(BaseModel):
    email: str
    password: str


class TokenInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EnvironmentInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    variables: dict[str, str] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)

    @field_validator("variables", "secrets")
    @classmethod
    def names(cls, v):
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) for k in v):
            raise ValueError("Invalid environment variable name")
        if set(v) & {"PYTHONPATH", "PYTHONSTARTUP", "LD_PRELOAD", "LD_LIBRARY_PATH"}:
            raise ValueError("Reserved environment variable")
        return v


class RegistryInput(BaseModel):
    registry: str = Field(min_length=1, max_length=254, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9.:-]*$")
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=10000)


class UserInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1000)
    role: Literal["admin", "operator", "viewer"] = "viewer"
