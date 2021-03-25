from itertools import islice
import numpy as np
from data_magic import smooth

class OptoDatasetB:
    def __init__(self):
        self.name = ""
        self.wavelength = []
        self.transmission = {}
        # self.ec_ids = []

    def generate_data_for_plotting(self):
        ec_ids = self.transmission.keys()
        if len(ec_ids) <= 20:
            ec_items = ec_ids[::20]
        else:
            ec_items = ec_ids
        transmission_sub_dict = dict(islice(self.transmission.items(), 0, None, 20))
        # transmission_sub_dict = {k: self.transmission[k][::20] for k in ec_items}
        # return transmission_sub_dict, self.wavelength[::20]
        return transmission_sub_dict, self.wavelength

    def calc_sum_of_transmission(self, ec_id, wavelength_range):
        transmission = self.transmission[ec_id]
        sum_of_transmission = sum(transmission[wavelength_range[0]:wavelength_range[1]])
        return sum_of_transmission

    def send_IODM(self, ec_ids, wavelength_range, **kwargs):
        iodm = {}
        ref_id = kwargs['reference']
        ref = self.calc_sum_of_transmission(ref_id, wavelength_range)
        for ec_id in ec_ids:
            sum = self.calc_sum_of_transmission(ec_id, wavelength_range)
            iodm[ec_id] = sum/ref
        return iodm

    def calc_min(self, transmission, wavelength_range):
        min_lbd = {}
        for ec_id in transmission:
            cutout = transmission[ec_id][wavelength_range[0]:wavelength_range[1]]
            coutout_smooth = smooth(cutout)
            min_id = np.where(coutout_smooth == min(coutout_smooth))
            idx = wavelength_range[0]+min_id[0][0]
            min_lbd[ec_id] = self.wavelength[idx]
        return min_lbd

    def insert_opto_from_db(self, data_in):
        ec_id, opto_from_db = zip(*data_in)
        start = 0
        start_ec = ec_id[0]
        for num, ec_point in enumerate(ec_id):
            if ec_point != start_ec:
                self.transmission[start_ec] = opto_from_db[start:num]
                start = num
                start_ec = ec_point
            else:
                pass

    def insert_opto_from_csv(self, data_in):
        for num, opto_data in enumerate(data_in):
            self.transmission[num] = opto_data[2:]
        self.ec_id_range = self.transmission.keys()
