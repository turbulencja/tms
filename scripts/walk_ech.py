import os
import numpy as np
import ech_to_echpr.ESPicoLib as ESPicoLib

root_cv = r'C:\Users\aerial triceratops\PycharmProjects\TechMatStrateg\dane\17052021 Awidyna-biotyna 0.5Pa'


def ech_conversion(root, fname):
    name = root+'\\'+fname
    with open(name) as file:
        k = file.readlines()
    res_ech = ESPicoLib.ParseResultFile(k)
    save_ech_p = root + '\\ech_hello' + fname[3:]
    with open(save_ech_p, 'w') as file:
        for elem in range(len(res_ech)):
            file.writelines('Cycle {}, {}\n'.format(elem, elem))
            for line in res_ech[elem]:
                if len(line) < 2:
                    file.writelines('{}, {}\n'.format(line[0], line[0]))
                else:
                    file.writelines('{}, {}\n'.format(line[0], line[1]))

if __name__=='__main__':
    for root, subdirs, files in os.walk(root_cv):
        ech_fname = None
        for name in files:
            if name.startswith('ech_2021'):
                ech_fname = name
                try:
                    # print(root)
                    ech_conversion(root, ech_fname)
                except UnicodeDecodeError:
                    print('ech error: '+root)
