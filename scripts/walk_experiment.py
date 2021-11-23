import os
from TMS_app.opto_dataset import OptoDatasetB
from TMS_app.ec_dataset import ElectroChemSet
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

root_cv = r'C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg\dane\[archive]\Kasia_2021.04.25\dane\-1.5-0.2,st0.2, 100mV 2c\opto_ech__2021_04_20_15_34_47'
wvlgth_path = r'../TMS_app/wavelength.txt'
sns.set_theme()

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
    # data = np.genfromtxt(filename, delimiter=',', encoding='utf-8', dtype=int)
    print(filename)
    data = np.genfromtxt(filename, delimiter=',', dtype=int)

    new_opto_dataset = OptoDatasetB()
    new_opto_dataset.insert_opto_from_csv(data)
    new_opto_dataset.wavelength = np.genfromtxt(wvlgth_path, delimiter=',')[2:]
    new_opto_dataset.ec_ids = list(new_opto_dataset.transmission.keys())
    return new_opto_dataset

def analysis_full(root, ech_file, opto_file):
    ec_dataset = read_ech_file(root+'\\'+ech_file)
    opto_dataset = read_opto_file(root+'\\'+opto_file)
    ec_items = list(range(len(ec_dataset.V)))
    print('calculating iodm')
    iodm_dict, iodm_wavelength_start, iodm_wavelength_stop = opto_dataset.automatic_IODM(ec_items, 100)
    _, iodm_array = zip(*iodm_dict.items())
    v = [ec_dataset.V[item] for item in ec_items]
    uA = [ec_dataset.uA[item] for item in ec_items]
    ec_ids_transmission = {k: opto_dataset.transmission[k] for k in ec_items}
    print('calculating min transmission')
    min_lbd_dict = opto_dataset.calc_min(ec_ids_transmission)
    _, lbd_min_array = zip(*min_lbd_dict.items())
    print('calculating min fit')
    fit_lbd_dict = opto_dataset.fit_min(opto_dataset.transmission)
    _, fit_array = zip(*fit_lbd_dict.items())
    plot_data(v, lbd_min_array, fit_array, iodm_array)
    write_csv(root, v, uA, fit_array, lbd_min_array, iodm_array, iodm_wavelength_start, iodm_wavelength_stop)

def plot_data(v, lbd_min, fit_min, iodm):
    print('plotting')
    figure = plt.figure()
    min_ax = figure.add_subplot(111)
    color = 'b'
    min_ax.plot(v, lbd_min, '.', color=color, label='min')
    min_ax.plot(v, fit_min[:len(v)], '.', color='g', label='fit')
    min_ax.set_xlabel('measurement')
    min_ax.set_ylabel('λ [nm]', color=color)
    min_ax.legend()

    color = 'r'
    iodm_ax = min_ax.twinx()
    iodm_ax.plot(v, iodm, '.', color=color)
    iodm_ax.set_ylabel('IODM', color=color)

    plt.savefig(root + '\opto_plot.png', bbox_inches='tight')

def write_csv(root, v, uA, fit_array, lbd_min_array, iodm, iodm_wavelength_start, iodm_wavelength_stop):
    print('writing to csv')
    iodm_start = [iodm_wavelength_start] * len(v)
    iodm_stop = [iodm_wavelength_stop] * len(v)
    fit_array = fit_array[:len(v)]
    data = [v, uA, fit_array, lbd_min_array, iodm, iodm_start, iodm_stop]
    data_np = np.array(data)
    data_vertical = data_np.transpose()
    header = 'U[V],I[A],fit[nm], lbd[nm],IODM,IODM range 1[nm], IODM range 2[nm]'
    np.savetxt(root+'\\dane.csv', data_vertical, delimiter=',', header=header)


if __name__=='__main__':
    for root, subdirs, files in os.walk(root_cv):
        ech_fname = None
        opto_fname = None
        for name in files:
            if name.startswith('ech_pr_'):
                ech_fname = name
            if name.startswith('opto_') and name.endswith('.csv'):
                opto_fname = name
        if ech_fname and opto_fname:
            print('calculating')
            print(root)
            analysis_full(root, ech_fname, opto_fname)



