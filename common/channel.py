# Copyright 2020-2025 NXP
"""TODO:summary line."""
from abc import abstractmethod
from typing import Optional, Tuple, Union

from .app import AppInterface, ApplicationCommand
from .config_data import ConfigData
from .factories import BackendFactory


class Channel(BackendFactory):
    """Base class for implementing communication channels."""

    @classmethod
    def matches(cls, *args) -> bool:  # type: ignore
        """Is the processor connected to the channel socket?"""
        return False

    def init_channel(self, config_data: ConfigData = None):  # type: ignore
        """Initialize channel.

        @param config_data: processor config data
        """
        pass

    def open(self, config_data: ConfigData) -> int:  # type: ignore
        """Open channel.

        @param config_data: processor config data
        @return: error code or success
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Ask for a self-reset."""

    @abstractmethod
    def is_alive(self, wait_for_response: bool = True) -> bool:
        """Check if the backend can communicate with the app.

        @param wait_for_response: True to wait for channel to be responsive, False otherwise
        @return: True if channel is alive, False otherwise
        """

    def close(self):  # type: ignore
        """Close channel."""
        pass

    @abstractmethod
    def write_data(self, address: int, width: int, data: bytes) -> bool:
        """Write data at address.

        @param address: application-level address
        @param width: data width
        @param data: data (hex-encoded byte stream)
        @return: True if operation was successful, false otherwise
        """

    @abstractmethod
    def read_data(self, address: int, width: int, count: int) -> Optional[str]:
        """Read data from address.

        @param address: application-level address
        @param width: data width
        @param count: number of elements
        @return: read data as string
        """

    @abstractmethod
    def write_symbol(self, symbol: Optional[Tuple[int, int, int]], value: int) -> bool:
        """Set an application-level symbol to a particular value.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @param value: value as int
        """

    @abstractmethod
    def read_symbol(self, symbol: Optional[Tuple[int, int, int]]) -> Union[None, int, str]:
        """Get the value of an application-level symbol.

        @param symbol: application-level symbol encoding (<address>, <access_size>, <len>)
        @return: symbol value of None if operation failed
        """

    def set_application(self, application: AppInterface):  # type: ignore
        """Set application.

        @param application: current application
        """
        pass

    def execute_command(self, cmd: ApplicationCommand, data: None | bytearray, timeout: None | float):  # type: ignore
        """Execute command.

        @param cmd: application command
        @param data: command parameters
        @timeout: how long we're wainting for test result
        @return: true if command was succesfully executed
        """
        pass
