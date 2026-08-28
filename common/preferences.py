# Copyright 2023 NXP
"""TODO:summary line."""
import json
import logging
import os.path
from json import JSONDecodeError

from memtool.common.factories import Singleton
from memtool.common.workspace import Workspace
from memtool.utils.constants import Const


class Preferences(metaclass=Singleton):
    """Workspace singleton class."""

    logger = logging.getLogger(__name__)
    __preferences = None
    PREFERENCES_FILE_NAME = '.preferences'

    class Name:
        """Class holding names of preferences."""
        SAVE_RESULTS = "save results"

    # Default value of save results preference.
    __save_results_default = False

    @staticmethod
    def get_instance():  # type: ignore
        """It gets singleton instance of preferences.

        @return: Singleton instance of preferences.
        """
        prefs_instance = Preferences()

        if prefs_instance.get_preferences() is None:
            preferences_file_path = os.path.join(Workspace.get_instance().get_location(),
                                                 Preferences.PREFERENCES_FILE_NAME)
            if os.path.exists(preferences_file_path):
                # Load saved preferences.
                with open(preferences_file_path, "rt", encoding="utf-8") as file:
                    try:
                        prefs_instance.set_preferences(json.load(file))
                    except JSONDecodeError:
                        prefs_instance.logger.error(f'Error while decoding preferences {preferences_file_path} file!')
                        # Use default preferences in case of failure to load saved preferences.
                        prefs_instance.set_default_preferences()
            else:
                # Use default preferences in case there are no saved preferences.
                prefs_instance.set_default_preferences()

        return prefs_instance

    def get_preferences(self):  # type: ignore
        """It gets preferences dictionary."""
        return self.__preferences

    def set_preferences(self, preferences: dict):  # type: ignore
        """It sets preferences dictionary.

        @param preferences: Preferences to be set.
        """
        self.__preferences = preferences

    def set_default_preferences(self):  # type: ignore
        """It sets default preferences into preferences dictionary."""
        self.__preferences = {Preferences.Name.SAVE_RESULTS: self.__save_results_default}

    def save_preferences(self):  # type: ignore
        """It saves preferences into preferences file of the workspace in JSON format."""
        preferences_file_path = os.path.join(Workspace.get_instance().get_location(), self.PREFERENCES_FILE_NAME)
        with open(preferences_file_path, "wt", encoding="utf-8") as f:
            f.write(json.dumps(self.__preferences, indent=Const.indent))

    def get_save_results_preference(self):  # type: ignore
        """It gets save results preference.

        @return: Value of save results preference from preferences dictionary
        or default value if not found in preferences dictionary.
        """
        return self.__preferences.get(Preferences.Name.SAVE_RESULTS, self.__save_results_default)

    def set_save_results_preference(self, save_results_value: bool):  # type: ignore
        """It sets save results preference value.

        @param save_results_value: Value of save results preference.
        """
        self.__preferences[Preferences.Name.SAVE_RESULTS] = save_results_value  # type: ignore
