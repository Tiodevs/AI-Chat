from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("atrium-api")
except PackageNotFoundError:
    __version__ = "0.1.0"
