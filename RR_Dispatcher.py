class RR_Dispatcher:
    def __init__(self, con):
        self.con = con
        con.dispatcher = self
        self.count = 0

    def updateCount(self):
        self.count += 1

    def dispatch(self, requestFloor):
        con = self.con
        numOfElevator = con.numOfElevator
        carID = self.count % numOfElevator + 1
        self.updateCount()
        return con.carMap[carID]




