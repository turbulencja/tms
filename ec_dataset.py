from time import time


class ElectroChemPoint:
    def __init__(self, uA, V, timestamp):
        self.uA = uA
        self.V = V
        self.timestamp = timestamp
        self.opto_meas = None


class ElectroChemSetB:
    def __init__(self, name):
        self.name = name
        self.ec_set = {}

    def load_ec_data(self, uA, V, timestamp=None):
        if not timestamp:
            timestamp = len(self.ec_set.keys())
        new_ec_point = ElectroChemPoint(uA, V, timestamp)
        self.ec_set[timestamp] = new_ec_point


class ElectroChemSet:
    def __init__(self, name):
        self.name = name
        self.uA = []
        self.V = []
        self.timestamp = []
