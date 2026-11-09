import json
import os
from pathlib import Path


class ConfigManager:
    _instance = None  # Class-level attribute to store the singleton instance

    def __new__(cls, config_path=None, initial_config=None):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path=None, initial_config=None):
        if self._initialized:  # Avoid reinitializing the singleton instance
            return
        
        # Initialize with either a file path or a dictionary
        if initial_config is not None:
            self.config = initial_config.copy()  # Create a copy to avoid reference issues
            self.config_path = None  # No file path when using a dictionary
        else:
            self.config_path = Path(config_path) if config_path else self.get_config_path()
            self.config = self.load_config()
        
        self.substitute_env_variables()
        self._initialized = True

    def load_config(self):
        """
        Load configuration from the file.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file {self.config_path} not found.")

        with self.config_path.open("r") as f:
            return json.load(f)

    def save_config(self):
        """
        Save the current configuration back to the file.
        If initialized with a dictionary, this operation is skipped.
        """
        if self.config_path:
            with self.config_path.open("w") as f:
                json.dump(self.config, f, indent=4)

    def substitute_env_variables(self):
        """
        Substitute environment variables in the configuration values.
        """

        def substitute(value):
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                return os.getenv(env_var) or value  # Replace with env value or keep original
            if isinstance(value, dict):
                return {k: substitute(v) for k, v in value.items()}
            if isinstance(value, list):
                return [substitute(v) for v in value]
            return value

        self.config = substitute(self.config)

    def get(self, key, default=None):
        """
        Get a configuration value using dot notation.
        """
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_as_int(self, key, default=None):
        value = self.get(key, default)
        return int(value) if value is not None else default

    def get_as_bool(self, key, default=None):
        value = self.get(key, default)
        return bool(value) if value is not None else default

    def set(self, key, value):
        """
        Set a configuration value using dot notation.
        """
        keys = key.split(".")
        config_section = self.config
        for k in keys[:-1]:
            if k not in config_section:
                config_section[k] = {}
            config_section = config_section[k]
        config_section[keys[-1]] = value
        self.save_config()  # Will only save if config_path is set

    def update(self, updates):
        """
        Bulk update configuration with a dictionary of values.
        """
        for key, value in updates.items():
            self.set(key, value)

    def export_config(self):
        """
        Export the current configuration as a dictionary.
        """
        return self.config.copy()

    @classmethod
    def get_config_path(cls):
        """
        Get the path to the config.json file in the project.

        Returns:
            Path: The absolute path to the config.json file.

        Raises:
            FileNotFoundError: If config.json does not exist.
        """
        current_file = Path(__file__).resolve()

        config_dir = current_file.parents[0]
        config_file_path = config_dir / "config.json"

        # Check if the file exists
        if not config_file_path.exists():
            raise FileNotFoundError(f"config.json not found at {config_file_path}")

        return str(config_file_path)