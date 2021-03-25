class ElectroChemSet:
    def __init__(self, name=None):
        self.name = name
        self.uA = []
        self.V = []
        self.id = []

    def insert_ec_data(self, ec_data):
        ec_id, V, uA = zip(*ec_data)
        self.V = V
        self.uA = uA
        self.id = ec_id

    def insert_ec_csv(self, ec_data):
        V, uA = zip(*ec_data)
        self.V = V
        self.uA = uA
        self.id = list(range(len(V)))
