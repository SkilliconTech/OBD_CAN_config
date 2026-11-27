from can_tool.models.config_model import ConfigurationModel
from can_tool.services.config_validator import (
    validate_complete_config, validate_filters,
)
from can_tool.core.repository_interface import ConfigurationRepository


class AppController:
    def __init__(self, repository: ConfigurationRepository):
        self.model = ConfigurationModel()
        self.repository = repository

    def save_configuration(self, path, data):
        validate_complete_config(data)
        self.repository.save(path, data)

    def load_configuration(self, path):
        data = self.repository.load(path)
        validate_complete_config(data)
        return data

    def update_classic_can(self, settings):
        self.model.set_classic_can(settings)

    def get_classic_can(self):
        return self.model.get_classic_can()

    def update_filters(self, rules):
        validate_filters(rules)
        self.model.set_filters(rules)

    def get_filters(self):
        return self.model.get_filters()