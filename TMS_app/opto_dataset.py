from itertools import islice
import numpy as np
from scipy.signal import general_gaussian
from collections import OrderedDict
from scipy.optimize import curve_fit
import logging


class OptoDatasetB:
    def __init__(self):
        self.name = ""
        self.wavelength = []
        self.transmission = OrderedDict()
        self.fit_range = None
        self.iodm_initial_range = None
        self.ec_ids = []

    def generate_data_for_plotting(self):
        transmission_sub_dict = dict(islice(self.transmission.items(), 0, None, 20))
        return transmission_sub_dict, self.wavelength

    def calc_sum_of_transmission(self, ec_id, wavelength_range):
        transmission = self.transmission[ec_id]
        sum_of_transmission = sum(transmission[wavelength_range[0]:wavelength_range[1]])
        return sum_of_transmission

    def send_IODM(self, ec_ids, wavelength_range):
        iodm = {}
        ref_id = min(self.ec_ids)
        wavelength_range_idx = [self.find_nearest(wavelength_range[0])[0], self.find_nearest(wavelength_range[1])[0]]
        ref = self.calc_sum_of_transmission(ref_id, wavelength_range_idx)
        for ec_id in ec_ids:
            sum = self.calc_sum_of_transmission(ec_id, wavelength_range_idx)
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
            if tmp > diff and self.iodm_initial_range[0]-window_size <= num <= self.iodm_initial_range[1]:
                diff = tmp
                num_diff = num
        iodm_lst = ftrans_matrix.transpose()[num_diff]
        iodm_dict = {ec_id: iodm_lst[num] for num, ec_id in enumerate(ec_ids)}
        return iodm_dict, self.wavelength[num_diff], self.wavelength[num_diff+window_size_smpl]

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

    def calc_fit_range(self):
        # self.ec_ids == []
        ref = self.transmission[min(self.ec_ids)]
        cutoff, _ = self.find_nearest(700)
        fft_ref = self.fft_smooth(ref)
        derivative_fft = np.gradient(fft_ref)

        deriv_first = derivative_fft[:cutoff]
        deriv_last = derivative_fft[cutoff:]
        fft_first = fft_ref[:cutoff]
        fft_last = fft_ref[cutoff:]

        first_peak = self.calc_maximal_peak(deriv_first, fft_first)[0][0]
        last_peak = self.calc_maximal_peak(deriv_last, fft_last)[0][0] + cutoff

        cut_derivative_fft = derivative_fft[first_peak:last_peak]
        infl_min = np.where(cut_derivative_fft == cut_derivative_fft.min())[0][0] + first_peak
        infl_max = np.where(cut_derivative_fft == cut_derivative_fft.max())[0][0] + first_peak
        return infl_min, infl_max

    def calc_auto_fit(self):
        if not self.fit_range:
            self.fit_range = self.calc_fit_range()
        fit_lbd = {}
        start, stop = self.fit_range[0], self.fit_range[1]
        wavelength_cut = np.array(self.wavelength[start:stop])
        for ec_id in self.transmission:
            data_cut = self.transmission[ec_id][start:stop]
            y_line = self.calc_fit(wavelength_cut, data_cut)
            idx = np.argmin(y_line)
            fit_lbd[ec_id] = wavelength_cut[idx]
        return fit_lbd

    def fit_min(self, transmission):
        fit_lbd = {}
        if not self.fit_range:
            self.fit_range = self.calc_fit_range()
        start, _ = self.find_nearest(self.fit_range[0])
        stop, _ = self.find_nearest(self.fit_range[1])
        wavelength_cut = np.array(self.wavelength[start:stop])
        for ec_id in transmission:
            data_cut = transmission[ec_id][start:stop]
            y_line = self.calc_fit(wavelength_cut, data_cut)
            idx = np.argmin(y_line)
            fit_lbd[ec_id] = wavelength_cut[idx]
        return fit_lbd

    def calc_min(self, transmission):
        min_lbd = {}
        for ec_id in transmission:
            cutout = transmission[ec_id][self.fit_range[0]:self.fit_range[1]]
            cutout_smooth = self.fft_smooth(cutout)
            min_id = np.where(cutout_smooth == min(cutout_smooth))
            idx = self.fit_range[0]+min_id[0][0]
            min_lbd[ec_id] = self.wavelength[idx]
        return min_lbd

    def insert_opto_from_csv(self, data_in):
        for num, opto_data in enumerate(data_in):
            self.transmission[num] = opto_data[2:]
        self.fit_range = self.calc_fit_range()
        self.iodm_initial_range = [self.fit_range[0] - 100, self.fit_range[1] + 100]

    def find_nearest(self, value):
        diff = [abs(element - value) for element in self.wavelength]
        # START HERE
        val_idx = diff.index(min(diff))
        val_real = self.wavelength[val_idx]
        return val_idx, val_real

    def calc_fit(self, x_data, y_data):
        popt, _ = curve_fit(self.quadratic_poly, x_data, y_data)
        a, b, c = popt
        fit_data = self.quadratic_poly(x_data, a, b, c)
        return fit_data

    @staticmethod
    def quadratic_poly(x, a, b, c):
        return a * x + b * x ** 2 + c

    @staticmethod
    def calc_maximal_peak(deriv_arr, arr):
        # 1. znalezc miejsca gdzie grad przechodzi przez 0
        zero_crossings = np.where(np.diff(np.sign(deriv_arr)))[0]
        # 2. znalezc miejsce maksymalnej wartosci dla punktów z #1
        try:
            max_p = arr[zero_crossings].max()
            idx_max_p = np.where(arr == max_p)
        except ValueError:
            # only for empty OptoCycleDataset
            idx_max_p = [np.array([0])]
        return idx_max_p

    @staticmethod
    def fft_smooth(X):
        sigma = 40
        m = 1
        win = np.roll(general_gaussian(X.shape[0], m, sigma), X.shape[0] // 2)
        fX = np.fft.fft(X)
        Xf = np.real(np.fft.ifft(fX * win))
        return Xf


class OptoCycleDataset(OptoDatasetB):
    def __init__(self):
        OptoDatasetB.__init__(self)
        self.cycle = None

    def insert_opto_from_csv(self, data_in, cycle):
        self.ec_ids = list(range(cycle[0], cycle[1]+1))
        self.transmission = dict(zip(self.ec_ids, data_in))
        self.fit_range = self.calc_fit_range()
        self.iodm_initial_range = [self.fit_range[0]-100, self.fit_range[1]+100]

