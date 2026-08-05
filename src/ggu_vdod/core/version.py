"""Single source of truth for development build identification."""

MAJOR = 0
MINOR = 1
PATCH = 2
BUILD = 2

PACKAGE_VERSION = f"{MAJOR}.{MINOR}.{PATCH}.dev{BUILD}"
DEVELOPMENT_BUILD_LABEL = (
    f"Development build : v{MAJOR}.{MINOR:03d}.{PATCH:03d} ({BUILD:03d})"
)
