from typing import Any


def remove_keys_recursive(obj: Any, keys_to_remove: set[str]) -> Any:
    """Recursively removes specified keys from dictionaries or lists of dictionaries."""
    if isinstance(obj, dict):
        return {
            k: remove_keys_recursive(v, keys_to_remove)
            for k, v in obj.items()
            if k not in keys_to_remove
        }
    elif isinstance(obj, list):
        return [remove_keys_recursive(item, keys_to_remove) for item in obj]
    return obj
