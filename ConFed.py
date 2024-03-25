import elevator_controller as oht
import ProdSmallFab as fab
from DES import *


class OHTProxyMsgQueue(EvtMsgQueue, AModel):
    def __init__(self, name):
        super().__init__(name)
        self.clockName = "ohtClock"
        self.timeScale = 0

    def processEvtMsg(self, e):
        if e.msg == 'loaded':                  # vtx-name    job-id
            pairMsg = f"{self.Tnow} retr {e.param[0]} {e.param[1]}"
            self.sendPairMsg(pairMsg)
        elif e.msg == 'unloaded':
            pairMsg = f"{self.Tnow} deli {e.param[0]} {e.param[1]}"
            self.sendPairMsg(pairMsg)

    def processPairMsg(self, m):
        t = float(m[0])
        if m[1] == 'job':  # time job fv tv id
            t = float(m[0])
            param = (m[2], m[4])
            e = EvtMsg(t+12.0, None, self, "loaded", param=param)
            self.scheduleEvtMsg(e)
            param = (m[3], m[4])
            e = EvtMsg(t+25.0, None, self, "unloaded", param=param)
            self.scheduleEvtMsg(e)

        # # schedule retrieval & delivery event into partner's EMQ directly
        # if m[1] == 'job':  # time job fv tv id
        #     ct = self.partner.con.equips[m[2]]
        #     nt = self.partner.con.equips[m[3]]
        #     jid = int(m[4])
        #     self.partner.scheduleEvtMsg4(12.0, None, ct, "retr", param=jid)
        #     self.partner.scheduleEvtMsg4(25.0, None, nt, "deli", param=jid)



class FabProxyMsgQueue(EvtMsgQueue, AModel):
    def __init__(self, name):
        super().__init__(name)
        self.clockName = "prodClock"
        self.timeScale = 0
        self.createJobGenProxy(0.008, 8)

    def createJobGenProxy(self, loadFactor, nTool):
        r1 = 1 * loadFactor
        for i in range(1, nTool + 1):
            ts = f'T{i}L'
            for j in range(1, nTool + 1):
                if i == j: continue
                td = f'T{j}U'
                oht.JobGenerator(self, self, i, ts, td, r1, proxy=True)

    def processEvtMsg(self, e):
        if e.msg == 'narr':  # time job fv tv job-id, job-id=0
            jobGen = e.fm
            jobGen.scheduleNextArrival()
            jobMsg = f"{self.Tnow} job {jobGen.fv} {jobGen.tv} 0"
            self.sendPairMsg(jobMsg)



if __name__ == "__main__":
    config, mon = '8bay', True
    ohtEMQ = oht.prepareOHTFed(config=config, mon=mon, intGen=False)
    # ohtEMQ = OHTProxyMsgQueue("OHTProxy")

    fabEMQ = fab.prepareFabFed(config=config, mon=False, sync=False)
    # fabEMQ = FabProxyMsgQueue("FabProxy")
    ohtEMQ.runDualFedSimInternal(fabEMQ)
    # the above line is same as the following two lines
    # ohtEMQ.pairingInternal(fabEMQ)
    # ohtEMQ.runSimulation()

