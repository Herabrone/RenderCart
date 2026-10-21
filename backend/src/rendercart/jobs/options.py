from rendercart.auth.security import decrypt_secret, encrypt_secret
from rendercart.registry.models import ToolManifest


def _sensitive_fields(tool: ToolManifest) -> set[str]:
    if tool.options is None:
        return set()
    return {
        name
        for name, field in tool.options.model_fields.items()
        if isinstance(field.json_schema_extra, dict) and field.json_schema_extra.get("sensitive")
    }


def encrypt_sensitive_options(tool: ToolManifest, options: dict[str, object]) -> dict[str, object]:
    protected = dict(options)
    for name in _sensitive_fields(tool):
        value = protected.get(name)
        if isinstance(value, str) and not value.startswith("enc:"):
            protected[name] = f"enc:{encrypt_secret(value)}"
    return protected


def decrypt_sensitive_options(tool: ToolManifest, options: dict[str, object]) -> dict[str, object]:
    revealed = dict(options)
    for name in _sensitive_fields(tool):
        value = revealed.get(name)
        if isinstance(value, str) and value.startswith("enc:"):
            revealed[name] = decrypt_secret(value[4:])
    return revealed
