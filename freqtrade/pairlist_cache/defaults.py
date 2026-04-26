import os


def default_socket_path() -> str:
    return f"/tmp/ftpairlist-{os.getuid()}.sock"  # noqa: S108


def default_lock_path() -> str:
    return f"/tmp/ftpairlist-{os.getuid()}.lock"  # noqa: S108


IDLE_SHUTDOWN_S = 900
