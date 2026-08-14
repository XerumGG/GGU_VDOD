"""Single source of truth for development build identification."""

MAJOR = 0
MINOR = 2
PATCH = 7
BUILD = 54

PACKAGE_VERSION = f"{MAJOR}.{MINOR:02d}.{PATCH:02d}"
DEVELOPMENT_BUILD_LABEL = f"#{BUILD:03d} Development build : v{MAJOR}.{MINOR:02d}.{PATCH:02d}"
