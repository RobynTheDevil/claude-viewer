from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("claude-viewer")
except PackageNotFoundError:
    __version__ = "0+unknown"
