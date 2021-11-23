import numpy as np
from scipy.signal import savgol_filter, general_gaussian


def fft_smooth(X):
    sigma = 40
    m = 1
    win = np.roll(general_gaussian(X.shape[0], m, sigma), X.shape[0] // 2)
    fX = np.fft.fft(X)
    Xf = np.real(np.fft.ifft(fX * win))
    return Xf


def calc_maximal_peak(arr):
    # 1. znalezc miejsca gdzie grad przechodzi przez 0
    zero_crossings = np.where(np.diff(np.sign(arr)))[0]
    # 2. znalezc miejsce maksymalnej wartosci dla punktów z #1
    max_p = arr[zero_crossings].max()
    idx_max_p = np.where(arr == max_p)
    return idx_max_p
