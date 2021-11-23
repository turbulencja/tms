import logging
import numpy as np

significant_points = ['Umax', 'Umin', 'Umid1', 'Umid2']

class ElectroChemSet:
    def __init__(self, name=None):
        self.name = name
        self.uA = []
        self.V = []
        self.id = []
        self.id_dict = dict.fromkeys(significant_points)

    def insert_ec_data(self, ec_data):
        ec_id, V, uA = zip(*ec_data)
        self.V = V
        self.uA = uA
        self.id = ec_id

    def insert_ec_csv(self, ec_data):
        try:
            V, uA = zip(*ec_data)
            self.V = V
            self.uA = uA
            self.id = list(range(len(V)))
        except ValueError:
            logging.error("doesn't seem like it's the right file")

    def pick_significant_points(self):
        max_V = np.max(self.V)
        ([[max_V_idx]]) = np.where(self.V == max_V)
        min_V = np.min(self.V)
        ([[min_V_idx]]) = np.where(self.V == min_V)
        diff_idx = abs(max_V_idx-min_V_idx)//2
        self.id_dict['Umax'] = max_V_idx
        self.id_dict['Umin'] = min_V_idx
        self.id_dict['Umid1'] = max_V_idx+diff_idx
        self.id_dict['Umid2'] = max_V_idx-diff_idx

