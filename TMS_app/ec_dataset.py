import logging
import numpy as np

significant_points = ['Umax', 'Umin', 'Umid1', 'Umid2']
cycles = ['Cycle 0', 'Cycle 1', 'Cycle 2']

class ElectroChemSet:
    def __init__(self, name=None):
        self.name = name
        self.uA = []
        self.V = []
        self.id = []
        self.cycles = dict.fromkeys(cycles)
        self.id_dict = dict.fromkeys(significant_points)

    def insert_ec_data(self, filename):
        data = open(filename)
        cycles_count = 0
        V, uA = [], []
        for num, row in enumerate(data):
            try:
                tmp_v, tmp_ua = row.split(', ')
            except ValueError:
                logging.error("doesn't seem like it's the right file")
                break
            try:
                V.append(float(tmp_v))
                uA.append(float(tmp_ua))
            except ValueError:
                self.cycles[tmp_v] = num-cycles_count
                cycles_count = cycles_count + 1
        self.V = V
        self.uA = uA
        self.id = range(len(V))

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

