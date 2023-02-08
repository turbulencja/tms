import logging
import numpy as np

significant_points = ['Umax', 'Umin', 'Umid1', 'Umid2']

class ElectroChemSet:
    def __init__(self, name=None, **kwargs):
        """
        self.name -
        self.uA -
        self.V -
        self.id -
        self.cycles -
        self.id_dict -
        """
        self.name = name
        self.uA = kwargs['uA']
        self.V = kwargs['V']
        self.id = kwargs['id']
        self.cycles = {}
        self.id_dict = dict.fromkeys(significant_points)

    def update_cycles_dict(self, tmp_cycle, num, cycles_count):
        row_number = num - cycles_count
        prev_key = next(iter(tmp_cycle))
        start_prev = tmp_cycle[prev_key]
        self.cycles[prev_key] = [start_prev, row_number - 1]

    def insert_ec_data(self, filename):
        data = open(filename)
        cycles_count = 0
        tmp_cycle = {}
        V, uA = [], []
        for num, row in enumerate(data):
            try:
                tmp_v, tmp_ua = row.split(', ')
                V.append(float(tmp_v))
                uA.append(float(tmp_ua))
            except ValueError:
                if row.startswith('Cycle'):
                    key = row.split(', ')[0]
                    row_number = num - cycles_count
                    if tmp_cycle:
                        self.update_cycles_dict(tmp_cycle, num, cycles_count)
                        tmp_cycle = {}
                    tmp_cycle[key] = row_number
                    cycles_count = cycles_count + 1
                else:
                    logging.warning("this doesn't seem like the right type of file")
                    return False
        if tmp_cycle:
            self.update_cycles_dict(tmp_cycle, num, cycles_count)
        else:
            self.cycles['Cycle 0'] = [0, num]

        self.V = V
        self.uA = uA
        self.id = range(len(V))
        return True

    def insert_ec_csv(self, ec_data):
        try:
            V, uA = zip(*ec_data)
            self.V = V
            self.uA = uA
            self.id = list(range(len(V)))
        except ValueError:
            logging.error("doesn't seem like it's the right file")

    def pick_significant_points(self):
        max_V = np.nanmax(self.V)
        ([max_V_idx]) = np.where(self.V == max_V)
        min_V = np.nanmin(self.V)
        ([min_V_idx]) = np.where(self.V == min_V)
        diff_idx = abs(max_V_idx[0]-min_V_idx[0])//2
        self.id_dict['Umax'] = max_V_idx
        self.id_dict['Umin'] = min_V_idx
        self.id_dict['Umid1'] = np.asarray([max_V_idx[0]+diff_idx])
        self.id_dict['Umid2'] = np.asarray([max_V_idx[0]-diff_idx])
        # convert negative indices to positive
        for id_key in ['Umid1', 'Umid2']:
            for num, item in enumerate(self.id_dict[id_key]):
                if item < 0:
                    self.id_dict[id_key][num] = len(self.V) + item


class ElectroChemCycle(ElectroChemSet):

    def __init__(self, cycle, **kwargs):
        ElectroChemSet.__init__(self, uA=kwargs['uA'], V=kwargs['V'], id=kwargs['id'])
        self.name = cycle
        self.cycles = None


if __name__ == "__main__":
    pass