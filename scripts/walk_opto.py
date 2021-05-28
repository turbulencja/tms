import os
from TMS_app.opto_dataset import OptoDatasetB
from TMS_app.ec_dataset import ElectroChemSet
import numpy as np
import matplotlib.pyplot as plt

root_cv = r'C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg\dane\pendrive\18052021 Awidyna-biotyna 0.1Pa'
wvlgth_path = r'wavelength.txt'
wavelength_range = [600, 750]  # w nm


def find_nearest_lambda(lambda_nm, wavelength_array):
    # find nearest value, return index
    diff = [abs(item - lambda_nm) for item in wavelength_array]
    idx = diff.index(min(diff))
    return idx

def read_ech_file(filename):
    print('reading ech file')
    data = np.genfromtxt(filename, delimiter=',')
    new_ec_dataset = ElectroChemSet()
    new_ec_dataset.insert_ec_csv(data)
    return new_ec_dataset

def read_opto_file(filename):
    print('reading opto file')
    data = np.genfromtxt(filename, delimiter=',', encoding='utf-8', dtype=int)
    new_opto_dataset = OptoDatasetB()
    new_opto_dataset.insert_opto_from_csv(data)
    new_opto_dataset.wavelength = np.genfromtxt(wvlgth_path, delimiter=',')[2:]
    new_opto_dataset.ec_ids = list(new_opto_dataset.transmission.keys())
    return new_opto_dataset

def calc_wavelength_range_ids(wavelength_array):
    wvlgth_start = find_nearest_lambda(wavelength_range[0], wavelength_array)
    wvlgth_stop = find_nearest_lambda(wavelength_range[1],
                                           wavelength_array)
    wavelength_range_ids = [wvlgth_start, wvlgth_stop]
    return wavelength_range_ids

def analysis_full(root, ech_file, opto_file):
    ec_dataset = read_ech_file(root+'\\'+ech_file)
    opto_dataset = read_opto_file(root+'\\'+opto_file)
    wavelength_range_ids = calc_wavelength_range_ids(opto_dataset.wavelength)
    ec_items = list(range(len(ec_dataset.V)))
    print('calculating iodm')
    iodm_dict, iodm_wavelength_start, iodm_wavelength_stop = opto_dataset.automatic_IODM(ec_items, 100)
    _, iodm_array = zip(*iodm_dict.items())
    v = [ec_dataset.V[item] for item in ec_items]
    uA = [ec_dataset.uA[item] for item in ec_items]
    ec_ids_transmission = {k: opto_dataset.transmission[k] for k in ec_items}
    print('calculating min transmission')
    min_lbd_dict = opto_dataset.calc_min(ec_ids_transmission, wavelength_range_ids)
    _, lbd_min_array = zip(*min_lbd_dict.items())
    write_csv(root, v, uA, lbd_min_array, iodm_array, iodm_wavelength_start, iodm_wavelength_stop)

def write_csv(root, fit_array, lbd_min_array, iodm, iodm_wavelength_start, iodm_wavelength_stop):
    print('writing to csv')
    iodm_start = [iodm_wavelength_start] * len(iodm)
    iodm_stop = [iodm_wavelength_stop] * len(iodm)
    data = [fit_array, lbd_min_array, iodm, iodm_start, iodm_stop]
    data_np = np.array(data)
    data_vertical = data_np.transpose()
    header = 'fit lbd[nm],lbd[nm],IODM,IODM range 1[nm], IODM range 2[nm]'
    np.savetxt(root+'\\dane.csv', data_vertical, delimiter=',', header=header)

def opto_analysis(root, opto_fname):
    print('reading csv')
    # read opto_csv
    opto_dataset = read_opto_file(root+'\\'+opto_fname)
    wavelength_range_ids = calc_wavelength_range_ids(opto_dataset.wavelength)
    print('calculating min')
    min_lbd_dict = opto_dataset.calc_min(opto_dataset.transmission, wavelength_range_ids)
    _, lbd_min_array = zip(*min_lbd_dict.items())
    print('calculating iodm')
    iodm_dict, iodm_wavelength_start, iodm_wavelength_stop = opto_dataset.\
        automatic_IODM(opto_dataset.transmission.keys(), 100)
    _, iodm_array = zip(*iodm_dict.items())
    print('calculating fit')
    fit_lbd_dict = opto_dataset.fit_min(opto_dataset.transmission)
    _, fit_array = zip(*fit_lbd_dict.items())

    plot_data(lbd_min_array, fit_array, iodm_array)
    write_csv(root, fit_array, lbd_min_array, iodm_array, iodm_wavelength_start, iodm_wavelength_stop)

def plot_data(lbd_min, fit_min, iodm):
    print('plotting')
    figure = plt.figure()
    min_ax = figure.add_subplot(111)
    color = 'b'
    min_ax.plot(lbd_min, '.', color=color, label='min')
    min_ax.plot(fit_min, '.', color='g', label='fit')
    min_ax.set_xlabel('measurement')
    min_ax.set_ylabel('λ [nm]', color=color)
    min_ax.legend()

    color = 'r'
    iodm_ax = min_ax.twinx()
    iodm_ax.plot(iodm, '.', color=color)
    iodm_ax.set_ylabel('IODM', color=color)

    plt.savefig(root + '\opto_plot.png', bbox_inches='tight')


if __name__=='__main__':
    wavelength = np.genfromtxt(wvlgth_path, delimiter=',')[2:]
    for root, subdirs, files in os.walk(root_cv):
        ech_fname = None
        opto_fname = None
        for name in files:
            if name.startswith('opto_'):
                opto_fname = name
                # analysis_full(root, ech_fname, opto_fname)
                try:
                    print(root)
                    opto_analysis(root, opto_fname)
                except UnicodeDecodeError:
                    print('opto error: '+root)



