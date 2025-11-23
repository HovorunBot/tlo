"""Module to contain compatibility objects based on different Python versions supported."""

__all__ = ["StrEnum"]

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum
