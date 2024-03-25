from DES import *
from utils import *

G_NumTools = 24
global G_ProdMQ

class JobGen(AModel):
    jid = 0

    def __init__(self, emq, fv, tv, ar):
        super().__init__()
        self.emq = emq
        self.fv = fv
        self.tv = tv
        self.ar = ar
        self.iat = ExpGen(1/ar)
        self.scheduleNextArrival()

    def scheduleNextArrival(self):
        self.emq.scheduleEvtMsg4(self.iat.get(), self, self, "narr")

    def processEvtMsg(self, e):
        if e.msg == "narr":
            print (e.time, e.msg)
            self.scheduleNextArrival()
            self.jid += 1
            msg =  f'{e.time} job {self.fv} {self.tv} {self.jid}'
            print(msg)
            self.emq.sendPairMsg(msg, e.time)
            # self.emq.simZMQ.pairSocket.send_string(msg)

            # send msg to OHT (time job fv tv)

def initializeJobGenerators(EMQ, numTools, loadFactor):
    r1 = 1*loadFactor

    for i in range(1, numTools+1):
        ts = f'T{i}L'
        for j in range(1,numTools+1):
            if i == j: continue
            td = f'T{j}U'
            jg = JobGen(EMQ, ts, td, r1)

class ProdEvtMsgQueue(EvtMsgQueue):
    def __init__(self, name):
        super().__init__(name)
        # self.barrier = infinity

    def processPairMsg(self, m):
        if m[1] == 'retrieved':
            pass
        elif m[1] == 'delivered':
            pass



if __name__ == "__main__":
    np.random.seed(100)

    config = '20bay'
    if config == '8bay':
        numTools = 8
        load = 0.008
    elif config == '20bay':
        numTools = 20
        load = 0.003
    elif config == '24bay':
        numTools = 24
        load = 0.0023

    G_ProdEMQ = ProdEvtMsgQueue('Production')
    G_EMQ = G_ProdEMQ
    G_ProdEMQ.makeZmq(syncMon=False, pair=True, pairBind=False)

    # GEMQ.makeZmq(False)

    initializeJobGenerators(G_ProdEMQ, numTools, load)

    G_ProdEMQ.runSimulation()