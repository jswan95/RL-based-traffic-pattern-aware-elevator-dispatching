import numpy as np


class Random_Dispatcher:
    def __init__(self, con):
        self.con = con
        con.dispatcher = self

    def dispatch(self, requestFloor):
        con = self.con
        print("Tnow: ", con.Tnow())
        carID = np.random.randint(1, con.numOfElevator + 1)
        return con.carMap[carID]