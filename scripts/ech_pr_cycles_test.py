import numpy as np
import os
import numpy.lib.recfunctions as rf
from TMS_app.tools.opto_dataset import OptoDatasetB
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns


path = r'C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg\dane\FTO 25062021'
wvlgth_path = r'C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg\TMS_app\wavelength.txt'
sns.set_theme()

def find_nearest_lambda(lambda_nm, wavelength_array):
    # find nearest value, return index
    diff = [abs(item - lambda_nm) for item in wavelength_array]
    idx = diff.index(min(diff))
    return idx


def read_opto_file(filename):
    print('reading opto file')
    data = np.genfromtxt(filename, delimiter=',', encoding='utf-8', dtype=int)
    new_opto_dataset = OptoDatasetB()
    new_opto_dataset.wavelength = np.genfromtxt(wvlgth_path, delimiter=',')[2:]
    new_opto_dataset.insert_opto_from_csv(data)
    new_opto_dataset.ec_ids = list(new_opto_dataset.transmission.keys())
    return new_opto_dataset


def write_csv(root, U, I, fit_array, lbd_min_array, iodm, iodm_wavelength_start, iodm_wavelength_stop):
    print('writing to csv')
    length = len(U)
    iodm_start = [iodm_wavelength_start] * length
    iodm_stop = [iodm_wavelength_stop] * length
    data = [U, I, fit_array, lbd_min_array, iodm, iodm_start, iodm_stop]
    data_np = np.array(data)
    data_vertical = data_np.transpose()
    header = 'U[V], I[A], fit lbd[nm],lbd[nm],IODM,IODM range 1[nm], IODM range 2[nm]'
    np.savetxt(root+'\\dane.csv', data_vertical, delimiter=',', header=header)


def plot_data(root, lbd_min, fit_min, iodm):
    print('plotting')
    figure = plt.figure()
    min_ax = figure.add_subplot(111)

    min_ax.plot(lbd_min, '.', color='b', label='min')
    min_ax.plot(fit_min, '.', color='orange', label='fit')
    min_ax.set_xlabel('measurement')
    min_ax.set_ylabel('λ [nm]')
    min_ax.legend()

    iodm_ax = min_ax.twinx()
    iodm_ax.plot(iodm, '.', color='r')
    iodm_ax.set_ylabel('IODM', color='r')

    plt.savefig(root + '\opto_plot.png', bbox_inches='tight')


def plot_data_u(root, cycle, U, lbd_min, fit_min, iodm):
    print('plotting cycle {}'.format(cycle+1))
    figure = plt.figure()
    plt.title('Cycle {}'.format(cycle+1))
    min_ax = figure.add_subplot(111)
    min_ax.plot(U, lbd_min, '.', color='b', label='min')
    min_ax.plot(U, fit_min, '.', color='orange', label='fit')
    min_ax.set_xlabel('U [V]')
    min_ax.set_ylabel('λ [nm]')


    iodm_ax = min_ax.twinx()
    iodm_ax.plot(U, iodm, '.', color='r', label='IODM')
    iodm_ax.set_ylabel('IODM', color='r')
    min_ax.legend()
    fname = '\cycle {}.png'.format(cycle)
    plt.savefig(root + fname, bbox_inches='tight')


def anlys(ech_file, opto_file, path, iodm_range):
    # read ech_hello file
    ech_data = np.genfromtxt(ech_file, delimiter=',', dtype=str)
    try:
        ech_data = rf.structured_to_unstructured(ech_data)
    except ValueError:
        pass
    # divide into cycles
    cycles_dict = {}
    cycle_no = 0
    for num, row in enumerate(ech_data):
        if row[0].startswith('Cycle'):
            cycles_dict[row[0]] = num-cycle_no
            ech_data = np.delete(ech_data, num-cycle_no, axis=0)
            cycle_no = cycle_no+1
    ech_data = np.char.replace(ech_data, 'None', 'nan')
    ech_data = ech_data.astype(np.float)
    U, I = zip(*ech_data)

    # read opto file
    opto_dataset = read_opto_file(opto_file)
    print('calculating fit')
    fit_lbd_dict = opto_dataset.calc_auto_fit()
    _, fit_array = zip(*fit_lbd_dict.items())
    print('calculating iodm')
    ec_ids = opto_dataset.transmission.keys()
    if iodm_range is None:
        print('slow iodm calc')
        iodm_dict, iodm_wavelength_start, iodm_wavelength_stop = opto_dataset.automatic_IODM(ec_ids, 100)
        iodm_range = [iodm_wavelength_start, iodm_wavelength_stop]
    else:
        print('fast iodm calc for range {}-{} nm'.format(iodm_range[0], iodm_range[1]))
        iodm_dict = opto_dataset.send_IODM(ec_ids, iodm_range)
    _, iodm_array = zip(*iodm_dict.items())
    print('calculating min')
    min_lbd_dict = opto_dataset.calc_min(opto_dataset.transmission)
    _, lbd_min_array = zip(*min_lbd_dict.items())

    # save analysis.csv
    write_csv(path, U, I, fit_array[:len(U)], lbd_min_array[:len(U)], iodm_array[:len(U)], iodm_wavelength_start, iodm_wavelength_stop)
    # save plot for X(meas)
    plot_data(path, lbd_min_array, fit_array, iodm_array)

    for cycle in range(cycle_no):
        # save plots for each cycle
        start_cycle = cycles_dict["Cycle {}".format(cycle)]
        if cycle != (cycle_no-1):
            end_cycle = cycles_dict["Cycle {}".format(cycle+1)]
        else:
            end_cycle = ech_data.shape[0]
        range_cycle = list(range(start_cycle, end_cycle))
        U = ech_data[start_cycle:end_cycle, 0]

        iodm_cut_dict = {k: v for k, v in iodm_dict.items() if k in range_cycle}
        _, iodm_array = zip(*iodm_cut_dict.items())
        minlbd_cut_dict = {k: v for k, v in min_lbd_dict.items() if k in range_cycle}
        _, lbd_min_array = zip(*minlbd_cut_dict.items())
        fit_cut_dict = {k: v for k, v in fit_lbd_dict.items() if k in range_cycle}
        _, fit_array = zip(*fit_cut_dict.items())
        plot_data_u(path, cycle, U, lbd_min_array, fit_array, iodm_array)
        # save spectra for Vmax, Vmin, Vmid1, Vmid2 in each cycle:
        # lbd[nm], Cycle1: Umax [value], Cycle1: Umid1 [value], ...

    return iodm_range


if __name__ == '__main__':
    # list of files in folder
    iodm_range = None

    for root, subdir, files in os.walk(path):

        ech_file = None
        opto_file = None
        # cycles = ['Cycle 0', 'Cycle 1', 'Cycle 2']
        # cycles = ['Cycle 0', 'Cycle 1']
        for file in files:
            if file.startswith('clean_ech_hello_'):
                ech_file = os.path.join(root, file)
            elif file.startswith('clean_opto_') and file.endswith('.csv'):
                opto_file = os.path.join(root, file)

        if ech_file and opto_file:
            iodm_range = anlys(ech_file, opto_file, root, iodm_range)


