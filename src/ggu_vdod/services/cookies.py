"""Safe local validation helpers for user-selected Netscape cookies.txt files."""

from pathlib import Path


MAX_COOKIE_FILE_SIZE = 10 * 1024 * 1024


def inspect_netscape_cookie_file(path):
    """Return a domain-only summary without retaining or exposing cookie values."""
    cookie_path = Path(path)
    if not cookie_path.is_file():
        raise ValueError("Choose an existing cookies.txt file.")
    if cookie_path.stat().st_size > MAX_COOKIE_FILE_SIZE:
        raise ValueError("Cookie file is too large to import safely.")

    try:
        contents = cookie_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as error:
        raise ValueError(f"Cookie file could not be read: {error}") from error

    domains = set()
    valid_rows = 0
    invalid_rows = 0
    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        fields = raw_line.split("\t")
        if len(fields) != 7:
            invalid_rows += 1
            continue
        domain = fields[0].removeprefix("#HttpOnly_").lstrip(".").casefold()
        if not domain or any(char.isspace() for char in domain):
            invalid_rows += 1
            continue
        domains.add(domain)
        valid_rows += 1

    if not valid_rows:
        raise ValueError("This file does not contain valid Netscape-format cookie rows.")
    if invalid_rows > valid_rows:
        raise ValueError("Most entries are invalid; choose a standard Netscape-format cookies.txt file.")
    return {"cookie_count": valid_rows, "domains": tuple(sorted(domains))}


def get_temp_cookies_dir() -> Path:
    """Return path to temporary cookie database copy folder."""
    from ..config.paths import get_app_dir
    tmp_dir = Path(get_app_dir()) / "temp_cookies"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


def purge_all_temporary_cookie_files() -> int:
    """Purge all temporary copied cookie files and database sidecars."""
    tmp_dir = get_temp_cookies_dir()
    count = 0
    if tmp_dir.exists():
        for item in tmp_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    count += 1
                elif item.is_dir():
                    import shutil
                    shutil.rmtree(item, ignore_errors=True)
                    count += 1
            except Exception:
                pass
    return count
