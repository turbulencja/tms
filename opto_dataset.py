from time import strftime


class OptoMeas:
    def __init__(self, transmission, timestamp, previous=None):
        self.transmission = transmission
        self.timestamp = timestamp
        self.ec_point = None
        self.previous_meas = previous
        self.next_meas = None


class OptoDataset:
    def __init__(self):
        self.wavelength = None
        self.name = ""
        self.opto_set = {}
        self.IODM_wavelength_range = ()

    def load_opto_meas(self, transmission, timestamp=None):
        if not timestamp:
            # timestamp = strftime('%H.%M.%S_')+str(len(self.opto_set.keys()))
            timestamp = len(self.opto_set.keys())
        new_optomeas = OptoMeas(transmission, timestamp)
        self.opto_set[timestamp] = new_optomeas

    def load_transmission_matrix(self, transmission):
        for column in transmission:
            self.load_opto_meas(column)


class OptoDatasetB:
    def __init__(self):
        self.name = ""
        self.wavelength = None
        self.transmission = None
        self.timestamp = []
        self.ec_measurement = None