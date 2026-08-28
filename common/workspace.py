# Copyright 2023-2024 NXP
"""Create workspace instance and set location."""

import os.path
from typing import Final

from memtool.common.factories import Singleton


class Workspace(metaclass=Singleton):
    """Workspace singleton class."""
    # Absolute path of workspace.
    __workspace = ""
    # Temporary directory from workspace.
    __TEMP_DIR: Final[str] = "temp"
    # Keys directory from workspace.
    __KEYS_DIR: Final[str] = "keys"
    # Private key directory from workspace.
    __PRIVATE_KEY_DIR: Final[str] = "private_key"
    # Public keys directory from workspace.
    __PUBLIC_KEYS: Final[str] = "public_keys"

    @staticmethod
    def get_instance():  # type: ignore
        """It gets singleton instance of workspace.

        @return: Singleton instance of workspace.
        """
        return Workspace()

    def get_location(self):  # type: ignore
        """It gets location of workspace as absolute path.

        @return: Absolute path of workspace.
        """
        return self.__workspace

    def set_location(self, location: str):  # type: ignore
        """It sets location of workspace as absolute path.

        @param location: Absolute path of workspace as string.
        """
        self.__workspace = os.path.abspath(location)

    def is_valid_location(self) -> bool:
        """It checks if current workspace location is a valid one.

        @return: True if workspace location is valid, false otherwise.
        """
        if self.__workspace is not None:
            if os.path.exists(self.__workspace) and os.path.isdir(self.__workspace):
                return True

        return False

    def get_temp_location(self) -> str:
        """It gets location of temporary directory from workspace as absolute path.

        @return: Absolute path of temporary directory from workspace.
        """
        return os.path.join(self.__workspace, self.__TEMP_DIR)

    def get_keys_location(self) -> str:
        """It gets location of keys directory from workspace as absolute path.

        @return: Absolute path of keys directory from workspace.
        """
        return os.path.join(self.__workspace, self.__TEMP_DIR, self.__KEYS_DIR)

    def get_private_key_location(self) -> str:
        """It gets location of private key directory from workspace as absolute path.

        @return: Absolute path of private key directory from workspace.
        """
        return os.path.join(self.__workspace, self.__TEMP_DIR, self.__KEYS_DIR, self.__PRIVATE_KEY_DIR)

    def get_public_keys_location(self) -> str:
        """It gets location of public keys directory from workspace as absolute path.

        @return: Absolute path of public keys directory from workspace.
        """
        return os.path.join(self.__workspace, self.__TEMP_DIR, self.__KEYS_DIR, self.__PUBLIC_KEYS)

    def ensure_location(self, location_to_ensure: str) -> None:
        """Ensure location exits in workspace.

        @param location_to_ensure: Location from workspace as absolute or relative path
        to be ensured that exists.
        """
        if os.path.abspath(self.__workspace) in os.path.abspath(location_to_ensure):
            location = location_to_ensure
        else:
            location = os.path.join(self.__workspace, location_to_ensure)
        if not os.path.exists(location):
            # Ensure parent location exits.
            parent_location = os.path.join(location, os.path.pardir)
            self.ensure_location(parent_location)
            # Create location if it does not exist.
            os.mkdir(location)
