"""Small pure formatting helpers used by the status and progress UI."""


def format_rate(bytes_per_second):
    """Format a transfer rate using compact binary units."""
    if not bytes_per_second:
        return "0 B/s"
    value = float(bytes_per_second)
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024 or unit == "GB/s":
            return f"{value:.1f} {unit}"
        value /= 1024


def format_bytes(byte_count):
    """Format a byte count using compact binary units."""
    if not byte_count:
        return "0 B"
    value = float(byte_count)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
