import copy
from can_tool.models.constants import DEFAULT_CLASSIC_CAN


class ConfigurationModel:
    def __init__(self):
        self.classic_can = copy.deepcopy(DEFAULT_CLASSIC_CAN)
        self.filters = []          # list of filter rules

    def reset(self):
        self.__init__()

    def get_configuration(self):
        return {"classic_can": copy.deepcopy(self.classic_can),
                "filters": copy.deepcopy(self.filters)}

    def set_classic_can(self, settings):
        self.classic_can = copy.deepcopy(settings)

    def get_classic_can(self):
        return copy.deepcopy(self.classic_can)

    def set_filters(self, rules):
        self.filters = copy.deepcopy(rules)

    def get_filters(self):
        return copy.deepcopy(self.filters)