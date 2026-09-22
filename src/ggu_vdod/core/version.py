"""Single source of truth for development build identification."""

MAJOR = 0
MINOR = 2
PATCH = 40
BUILD = 96

PACKAGE_VERSION = f"{MAJOR}.{MINOR}.{PATCH}"
DEVELOPMENT_BUILD_LABEL = f"#{BUILD:03d} Development build : v{MAJOR}.{MINOR}.{PATCH}"
