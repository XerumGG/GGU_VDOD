"""Single source of truth for development build identification."""

MAJOR = 0
MINOR = 2
PATCH = 6
BUILD = 51

PACKAGE_VERSION = f"{MAJOR}.{MINOR:03d}.{PATCH:03d}"
DEVELOPMENT_BUILD_LABEL = f"Development build : v{MAJOR}.{MINOR:03d}.{PATCH:03d} ({BUILD:03d})"
