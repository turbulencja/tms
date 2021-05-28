from itertools import islice
import numpy as np
from data_magic import smooth
from collections import OrderedDict
from scipy.optimize import curve_fit

class OptoDatasetB:
    def __init__(self):
        self.name = ""
        self.wavelength = []
        self.transmission = OrderedDict()
        self.wavelength_range = [570, 770]
        self.ec_ids = []

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

    def automatic_IODM(self, ec_ids, window_size):
        '''
        :param ec_ids:
        :param window_size: in nanometers
        :return: list of IODM values
        '''
        # window size from nm to number of samples
        window_size_smpl, _ = self.find_nearest(self.wavelength[0]+window_size)
        cutoff_wvlgth, _ = self.find_nearest(900)
        # calc ftrans in running window
        ftrans_matrix = self.running_ftrans(ec_ids, window_size_smpl, cutoff=cutoff_wvlgth)
        # pick wavelength of maximal iodm amplitude
        diff, num_diff = 0, 0
        for num, row in enumerate(ftrans_matrix.transpose()):
            tmp = row.max()-row.min()
            if tmp > diff:
                diff = tmp
                num_diff = num
        iodm_lst = ftrans_matrix.transpose()[num_diff]
        iodm_dict = {ec_id: iodm_lst[num] for num, ec_id in enumerate(ec_ids)}
        return iodm_dict, self.wavelength[num], self.wavelength[num+window_size_smpl]

    def running_ftrans(self, ec_ids, window_size, cutoff=None):
        if cutoff is None:
            cutoff = len(self.wavelength)
        ftrans_matrix = []
        ftrans_reference = []
        # getting first transmission spectrum
        ref = next(iter(self.transmission.items()))[1][:cutoff]
        for num, _ in enumerate(ref[:-window_size]):
            ref_chunk = ref[num:num + window_size]
            ref_val = ref_chunk.sum()
            ftrans_reference.append(ref_val)
        for ec_id in ec_ids:
            row = self.transmission[ec_id][:cutoff]
            ftrans_array = []
            sum_array = []
            for num, _ in enumerate(row[:-window_size]):
                sum = row[num:num + window_size].sum()
                sum_array.append(sum)
                ftrans_value = sum / ftrans_reference[num]
                ftrans_array.append(ftrans_value)
            ftrans_matrix.append(ftrans_array)
        return np.array(ftrans_matrix)

    def calc_window_size(self, window_size):
        end_wlgth, _ = self.find_nearest(self.wavelength[0] + window_size)
        return end_wlgth

    def fit_min(self, transmission):
        fit_lbd = {}
        start, _ = self.find_nearest(self.wavelength_range[0])
        stop, _ = self.find_nearest(self.wavelength_range[1])
        wavelength_cut = np.array(self.wavelength[start:stop])
        # wavelength_fit = np.linspace(start, stop, num=500)
        for ec_id in transmission:
            data_cut = transmission[ec_id][start:stop]
            # curve fit
            popt, _ = curve_fit(self.objective, wavelength_cut, data_cut)
            a, b, c = popt
            # calculate the output for the range
            y_line = self.objective(wavelength_cut, a, b, c)
            idx = np.argmin(y_line)
            fit_lbd[ec_id] = wavelength_cut[idx]
        return fit_lbd

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
        # self.ec_id_range = self.transmission.keys()

    def find_nearest(self, value):
        diff = [abs(element - value) for element in self.wavelength]
        val_idx = diff.index(min(diff))
        val_real = self.wavelength[val_idx]
        return val_idx, val_real

    @staticmethod
    def objective(x, a, b, c):
        return a * x + b * x ** 2 + c
