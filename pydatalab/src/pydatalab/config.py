import hashlib
import json
import logging
import os
import platform
from pathlib import Path
from typing import Any

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydatalab.models import Person
from pydatalab.models.utils import RandomAlphabeticalRefcodeFactory, RefCodeFactory

__all__ = ("CONFIG", "ServerConfig", "DeploymentMetadata", "RemoteFilesystem")


def config_file_settings(settings_cls: type[BaseSettings] | None = None) -> dict[str, Any]:
    """Returns a dictionary of server settings loaded from the default or specified
    JSON config file location (via the env var `PYDATALAB_CONFIG_FILE`).

    """
    config_file = Path(os.getenv("PYDATALAB_CONFIG_FILE", "/app/config.json"))

    res = {}
    if config_file.is_file():
        logging.debug("Loading from config file at %s", config_file)
        config_file_content = config_file.read_text(encoding="utf-8")

        try:
            res = json.loads(config_file_content)
        except json.JSONDecodeError as json_exc:
            raise RuntimeError(f"Unable to read JSON config file {config_file}") from json_exc

    else:
        logging.debug("Unable to load from config file at %s", config_file)
        res = {}

    return res


class DeploymentMetadata(BaseModel):
    """A model for specifying metadata about a datalab deployment."""

    maintainer: Person | None = None
    issue_tracker: AnyUrl | None = Field("https://github.com/datalab-org/datalab/issues")
    homepage: AnyUrl | None = None
    source_repository: AnyUrl | None = Field("https://github.com/datalab-org/datalab")

    @field_validator("maintainer")
    @classmethod
    def strip_fields_from_person(cls, v):
        if not v.contact_email:
            raise ValueError("Must provide contact email for maintainer.")

        return Person(contact_email=v.contact_email, display_name=v.display_name)

    model_config = ConfigDict(extra="allow")


class BackupStrategy(BaseModel):
    """This model describes the config of a particular backup strategy."""

    active: bool | None = Field(
        True,
        description="Whether this backup strategy is active; i.e., whether it is actually used. All strategies will be disabled in testing scenarios.",
    )
    hostname: str | None = Field(
        None,
        description="The hostname of the SSH-accessible server on which to store the backup (`None` indicates local backups).",
    )
    location: Path = Field(
        description="The location under which to store the backups on the host. Each backup will be date-stamped and stored in a subdirectory of this location."
    )
    retention: int | None = Field(
        None,
        description="How many copies of this backup type to keep. For example, if the backup runs daily, this number indicates how many previous days worth of backup to keep. If the backup size ever decreases between days, the largest backup will always be kept.",
    )
    frequency: str | None = Field(
        None,
        description="The frequency of the backup, described in the crontab syntax.",
        examples=["5 4 * * *", "5 2 1 1,4,7,10 *"],
    )
    notification_email_address: str | None = Field(
        None, description="An email address to send backup notifications to."
    )
    notify_on_success: bool = Field(
        True,
        description="Whether to send a notification email on successful backup, or just for failures/warnings.",
    )


class RemoteFilesystem(BaseModel):
    """Configuration for specifying a single remote filesystem
    accessible from the server.
    """

    name: str = Field(description="The name of the filesystem to use in the UI.")
    hostname: str | None = Field(
        None,
        description="The hostname for the filesystem. `None` indicates the filesystem is already mounted locally.",
    )
    path: Path = Field(description="The path to the base of the filesystem to include.")


class SMTPSettings(BaseModel):
    """Configuration for specifying SMTP settings for sending emails."""

    MAIL_SERVER: str = Field("127.0.0.1", description="The SMTP server to use for sending emails.")
    MAIL_PORT: int = Field(587, description="The port to use for the SMTP server.")
    MAIL_USERNAME: str = Field(
        "",
        description="The username to use for the SMTP server. Will use the externally provided `MAIL_PASSWORD` environment variable for authentication.",
    )
    MAIL_USE_TLS: bool = Field(True, description="Whether to use TLS for the SMTP connection.")
    MAIL_DEFAULT_SENDER: str = Field(
        "", description="The email address to use as the sender for emails."
    )


class ServerConfig(BaseSettings):
    """A model that provides settings for deploying the API."""

    APP_URL: str | None = Field(
        None,
        description="The canonical URL for any UI associated with this instance; will be used for redirects on user login/registration.",
    )

    SECRET_KEY: str = Field(
        hashlib.sha512((platform.platform() + str(platform.python_build)).encode()).hexdigest(),
        description="The secret key to use for Flask. This value should be changed and/or loaded from an environment variable for production deployments.",
    )

    MONGO_URI: str = Field(
        "mongodb://localhost:27017/datalabvue",
        description="The URI for the underlying MongoDB.",
    )
    SESSION_LIFETIME: int = Field(
        7 * 24,
        description="The lifetime of each authenticated session, in hours.",
    )

    FILE_DIRECTORY: str | Path = Field(
        Path(__file__).parent.joinpath("../files").resolve(),
        description="The path under which to place stored files uploaded to the server.",
    )

    LOG_FILE: str | Path | None = Field(
        None,
        description="The path to the log file to use for the server and all associated processes (e.g., invoke tasks)",
    )

    DEBUG: bool = Field(True, description="Whether to enable debug-level logging in the server.")

    TESTING: bool = Field(
        False, description="Whether to run the server in testing mode, i.e., without user auth."
    )

    IDENTIFIER_PREFIX: str = Field(
        None,
        description="The prefix to use for identifiers in this deployment, e.g., 'grey' in `grey:AAAAAA`",
    )

    REFCODE_GENERATOR: type[RefCodeFactory] = Field(
        RandomAlphabeticalRefcodeFactory, description="The class to use to generate refcodes."
    )

    REMOTE_FILESYSTEMS: list[RemoteFilesystem] = Field(
        [],
        description="A list of dictionaries describing remote filesystems to be accessible from the server.",
    )

    REMOTE_CACHE_MAX_AGE: int = Field(
        60,
        description="The maximum age, in minutes, of the remote filesystem cache after which it should be invalidated.",
    )

    REMOTE_CACHE_MIN_AGE: int = Field(
        1,
        description="The minimum age, in minutes, of the remote filesystem cache, below which the cache will not be invalidated if an update is manually requested.",
    )

    BEHIND_REVERSE_PROXY: bool = Field(
        False,
        description="Whether the Flask app is being deployed behind a reverse proxy. If `True`, the reverse proxy middleware described in the [Flask docs](https://flask.palletsprojects.com/en/2.2.x/deploying/proxy_fix/) will be attached to the app.",
    )

    GITHUB_ORG_ALLOW_LIST: list[str] | None = Field(
        [],
        description="A list of GitHub organization IDs (available from `https://api.github.com/orgs/<org_name>`, and are immutable) or organisation names (which can change, so be warned), that the membership of which will be required to register a new datalab account. Setting the value to `None` will allow any GitHub user to register an account.",
    )

    DEPLOYMENT_METADATA: DeploymentMetadata | None = Field(
        None, description="A dictionary containing metadata to serve at `/info`."
    )

    ORCID_AUTO_ACTIVATE_ACCOUNTS: bool = Field(
        False,
        description="Whether to automatically activate accounts created via ORCID registration.",
    )

    GITHUB_AUTO_ACTIVATE_ACCOUNTS: bool = Field(
        False,
        description="Whether to automatically activate accounts created via GitHub registration.",
    )

    EMAIL_AUTO_ACTIVATE_ACCOUNTS: bool = Field(
        False,
        description="Whether to automatically activate accounts created via email registration.",
    )

    AUTO_ACTIVATE_ACCOUNTS: bool = Field(
        False,
        description="Whether to automatically activate accounts created via any registration method.",
    )

    EMAIL_DOMAIN_ALLOW_LIST: list[str] | None = Field(
        [],
        description="A list of domains for which users will be able to register accounts if they have a matching verified email address, which still need to be verified by an admin. Setting the value to `None` will allow any email addresses at any domain to register *and activate* an account, otherwise the default `[]` will not allow any email addresses registration.",
    )

    EMAIL_AUTH_SMTP_SETTINGS: SMTPSettings | None = Field(
        None,
        description="A dictionary containing SMTP settings for sending emails for account registration.",
    )

    MAX_CONTENT_LENGTH: int = Field(
        10 * 1000**3,
        description=r"""Direct mapping to the equivalent Flask setting. In practice, limits the file size that can be uploaded.
Defaults to 10 GB to avoid filling the tmp directory of a server.

Warning: this value will overwrite any other values passed to `FLASK_MAX_CONTENT_LENGTH` but is included here to clarify
its importance when deploying a datalab instance.""",
    )

    MAX_BATCH_CREATE_SIZE: int = Field(
        10_000,
        description="Maximum number of items that can be created in a single batch operation.",
    )

    BACKUP_STRATEGIES: dict[str, BackupStrategy] | None = Field(
        {
            "daily-snapshots": BackupStrategy(
                hostname=None,
                location="/tmp/datalab-backups/daily-snapshots/",  # noqa: S108
                frequency="5 4 * * *",  # 4:05 every day
                retention=7,
            ),
            "weekly-snapshots": BackupStrategy(
                hostname=None,
                location="/tmp/datalab-backups/weekly-snapshots/",  # noqa: S108
                frequency="5 3 * * 1",  # 03:05 every Monday
                retention=5,
            ),
            "quarterly-snapshots": BackupStrategy(
                hostname=None,
                location="/tmp/datalab-backups/quarterly-snapshots/",  # noqa: S108
                frequency="5 2 1 1,4,7,10 *",  # first of January, April, July, October at 02:05
                retention=4,
            ),
        },
        description="The desired backup configuration.",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_cache_ages(cls, values):
        min_age = values.get("REMOTE_CACHE_MIN_AGE")
        max_age = values.get("REMOTE_CACHE_MAX_AGE")

        if min_age is not None and max_age is not None and min_age > max_age:
            raise RuntimeError(
                f"The maximum cache age must be greater than the minimum cache age: min {min_age=}, max {max_age=}"
            )
        return values

    @field_validator("IDENTIFIER_PREFIX", mode="before")
    @classmethod
    def validate_identifier_prefix(cls, v, info):
        """Make sure that the identifier prefix is set and is valid, raising clear error messages if not."""
        data = info.data if hasattr(info, "data") else {}
        if data.get("TESTING") or v is None:
            return "test"

        if len(v) > 12:
            raise RuntimeError(
                f"Identifier prefix must be less than 12 characters long, received {v=}"
            )

        # test a trial refcode
        from pydatalab.models.utils import Refcode

        try:
            Refcode(f"{v}:AAAAAA")
        except ValidationError as exc:
            raise RuntimeError(
                f"Invalid identifier prefix: {v}. Validation with refcode `AAAAAA` returned error: {exc}"
            )
        return v

    model_config = SettingsConfigDict(
        env_prefix="PYDATALAB_",
        extra="allow",
        env_file=".env",
        env_file_encoding="utf-8",
        validate_assignment=True,
        case_sensitive=False,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            config_file_settings,
            file_secret_settings,
        )

    @model_validator(mode="before")
    @classmethod
    def deactivate_backup_strategies_during_testing(cls, values):
        if values.get("TESTING"):
            for name in values.get("BACKUP_STRATEGIES", {}):
                values["BACKUP_STRATEGIES"][name].active = False
        return values

    @field_validator("LOG_FILE", mode="before")
    @classmethod
    def make_missing_log_directory(cls, v):
        """Make sure that the log directory exists and is writable."""
        if v is None:
            return v
        try:
            v = Path(v)
            v.parent.mkdir(exist_ok=True, parents=True)
            v.touch(exist_ok=True)
        except Exception as exc:
            raise RuntimeError(f"Unable to create log file at {v}") from exc
        return v

    def update(self, values: dict):
        """Update the configuration with new values, following Pydantic v1 behavior."""
        for key, value in values.items():
            key_upper = key.upper()
            if hasattr(self, key_upper):
                setattr(self, key_upper, value)
            else:
                setattr(self, key_upper, value)


CONFIG: ServerConfig = ServerConfig()
"""The global server configuration object.
This is a singleton instance of the `ServerConfig` model.
"""


class AuthMechanisms(BaseModel):
    github: bool = False
    orcid: bool = False
    email: bool = False


class AIIntegrations(BaseModel):
    openai: bool = False
    anthropic: bool = False


class FeatureFlags(BaseModel):
    auth_mechanisms: AuthMechanisms = AuthMechanisms()
    ai_integrations: AIIntegrations = AIIntegrations()
    email_notifications: bool = False


FEATURE_FLAGS: FeatureFlags = FeatureFlags()
"""The global feature flags object.

This is a singleton of `FeatureFlags` that can be used to see
the enabled features of the app at a higher-level to the
configuration (e.g., includes runtime environment checks).
"""
