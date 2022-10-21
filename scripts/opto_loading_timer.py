import numpy as np
from datetime import datetime
from TMS_app.ec_dataset import ElectroChemSet
from TMS_app.opto_dataset import OptoCycleDataset
import os


def read_opto_cycle_csv(filename):
    """
    reading optical file into separate cycles
    :param filename: path to file
    :return:
    """

    data = open(filename)
    wavelength = read_wavelengths()
    opto_cycles = dict.fromkeys(cycles.keys())
    tmp = dict.fromkeys(cycles.keys())
    for cycle in cycles:
        tmp[cycle] = []

    for num, row in enumerate(data):
        for cycle in cycles:
            if cycles[cycle][0] <= num <= cycles[cycle][1]:
                row = row.split(',')
                row = [int(x) for x in row]
                tmp[cycle].append(row)
            else:
                pass
    for cycle in tmp:
        new_cycle = OptoCycleDataset()
        new_cycle.wavelength = wavelength
        new_cycle.insert_opto_from_csv(tmp[cycle], cycles[cycle])
        opto_cycles[cycle] = new_cycle
    return opto_cycles


def read_opto_cycle_csv_2(filename):
    """
    reading optical file into separate cycles
    :param filename: path to file
    :return:
    """
    data = np.genfromtxt(filename, delimiter=',', encoding='utf-8', dtype=int)
    opto_cycles = dict.fromkeys(cycles.keys())
    wavelength = read_wavelengths()
    for cycle in cycles:
        opto_cycle_tmp = OptoCycleDataset()
        opto_cycle_tmp.wavelength = wavelength
        opto_cycle_tmp.insert_opto_from_csv(data[cycles[cycle][0]:
                                                 cycles[cycle][1]],
                                            cycles[cycle])
        opto_cycles[cycle] = opto_cycle_tmp
    return opto_cycles


def read_ec_csv(filename):
    new_ec_dataset = ElectroChemSet()
    new_ec_dataset.insert_ec_data2(filename)
    ec_dataset = new_ec_dataset
    cycles = ec_dataset.cycles
    return cycles


def read_wavelengths():
    wavelength = np.genfromtxt(r"C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg2\TMS_app\wavelength.txt", delimiter=',')[2:]
    return wavelength


if __name__ == '__main__':

    ec_path = r"C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg_old\dane\17052021 Awidyna-biotyna 0.5Pa - Kopia\Awidyna 0.0001\CV, Ferr\opto_ech__2021_05_17_16_00_37\ech_hello_2021_05_17_16_03_07.csv"
    opto_path = r"C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg_old\dane\17052021 Awidyna-biotyna 0.5Pa - Kopia\Awidyna 0.0001\CV, Ferr\opto_ech__2021_05_17_16_00_37\opto_2021_05_17_16_03_07.csv"

    # root = r"C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg_old\dane\17052021 Awidyna-biotyna 0.5Pa - Kopia"
    #
    # for dir, subdirs, files in os.walk(root):
    #     for file in files:
    #         if file.startswith('ech_hello_'):
    #             print(dir)
    #             ec_path = os.path.join(dir, file)
    #             opto_path = ec_path.replace('ech_hello', 'opto')

    cycles = read_ec_csv(ec_path)
    start = datetime.now()
    cycles_genfromtxt = read_opto_cycle_csv_2(opto_path)
    read_1 = datetime.now()
    print(f"reading with genfromtxt: {read_1 - start}")
    print(cycles_genfromtxt)
    start = datetime.now()
    cycles_openfile = read_opto_cycle_csv(opto_path)
    read_2 = datetime.now()
    print(f"reading with open file: {read_2 - start}")
    print(cycles_openfile)


