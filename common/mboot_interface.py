# Copyright 2022-2023, 2025 NXP
"""TODO:summary line."""
import logging

from .factories import MBootFactory


class MBootInterface(MBootFactory):
    """Interface for implementing MBoot communication channels."""

    logger = logging.getLogger(__name__)

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Determine if the class can be instantiated.

        Each class tells the factory if it can handle the input
        """
        return False

    def load_image(self, filename="Binary Image") -> bool:  # type: ignore
        """Load binary with IVT header.

        @return: success?
        """
        pass

    def close(self):  # type: ignore
        """Free HID port."""
        pass
