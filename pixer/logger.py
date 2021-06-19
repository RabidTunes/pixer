TRACE = "TRACE"
DEBUG = "DEBUG"
INFO = "INFO"
WARN = "WARN"
ERROR = "ERROR"
active_log_level = DEBUG
log_levels = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]
active_log_tags = []


def log(level, text, tags=None):
    if tags is None:
        tags = []
    if active_log_level is not None:
        if log_levels.index(level) >= log_levels.index(active_log_level):
            if not tags or all(elem in active_log_tags for elem in tags):
                print("[" + str(level) + "]" + str(tags) + " " + str(text))
