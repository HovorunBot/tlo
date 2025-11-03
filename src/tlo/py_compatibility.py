"""Module to contain compatibility objects based on different Python versions supported."""

__all__ = ["StrEnum", "Unpack"]

import enum
import sys

if sys.version_info < (3, 11):
    from typing_extensions import Unpack
else:
    from typing import Unpack


if sys.version_info < (3, 12):

    class StrEnum(str, enum.Enum):
        """Simple implementation of `str`-based `Enum` classes for old versions of Python."""

else:
    from enum import StrEnum
