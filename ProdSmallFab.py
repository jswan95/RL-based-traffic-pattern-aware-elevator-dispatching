from DES import *
from utils import *
import enum
import numpy as np

class Foup:
    fid = 0
    upt = [12, 20]
    upt2 = [upt[0]/2, upt[1]/2]
    PSeq = [[1,5,7,3,6,8], [1,6,2,4,5,8]]
    PTime= [[upt,upt2,upt,upt,upt2], [upt,upt2,upt,upt,upt2]]

    @staticmethod
    def getFid():
        Foup.fid += 1
        return Foup.fid

    def __init__(self, type, t):
        self.type = type
        self.pSeq = Foup.PSeq[type]
        self.pTime = Foup.PTime[type]
        self.step = 0
        self.nStep = len(self.pSeq)
        self.id = Foup.getFid()
        self.genAt = t

    def getProcTime(self):
        pt = self.pTime[self.step]
        return np.random.uniform(pt[0], pt[1])

    def currTool(self):
        return self.pSeq[self.step]

    def nextTool(self):
        if self.step >= self.nStep:
            return None
        return self.pSeq[self.step + 1]


class FoupGen(AModel):
    def __init__(self, con, ua, ub):
        super().__init__()
        self.con = con
        self.iat = UnifGen(ua, ub)
        self.scheduleNextArrival()

    def scheduleNextArrival(self):
        dt = self.iat.get()
        self.con.emq.scheduleEvtMsg4(self.iat.get(), self, self, "narr", extern=True)

    def processEvtMsg(self, e):
        if e.msg == "narr":
            self.scheduleNextArrival()
            p = np.random.random()
            if p < 0.5:
                type = 0
            else:
                type = 1
            foup = Foup(type, self.con.Tnow())
            self.con.throwIn(foup)


#  EquipState.IDLE.name : 'IDLE'
#  EquipState.IDLE.value : 0
class EquipState(enum.Enum):
    IDLE = 11
    BUSY = 4
    SETUP = 6
    DOWN = 1

class Equip(AModel):
    def __init__(self, id, emq, con):
        super().__init__()
        self.id = id
        self.emq = emq
        self.con = con
        self.inPort = []
        self.outPort = []
        self.state = EquipState.IDLE
        self.job = None
        self.prevJobType = -1
        self.setupTime = 15
        self.util = TimeAverage(self.Tnow())

    def Tnow(self):
        return self.con.Tnow()

    def busy(self):
        return self.state == EquipState.BUSY

    def idle(self):
        return self.state == EquipState.IDLE

    def toolName(self):
        return f"T{self.id}"

    def outVertexName(self):  # name in OHT fed
        return f"T{self.id}L"

    def inVertexName(self):   # name in OHT fed
        return f"T{self.id}U"

    def outPortName(self):    # name in Monitor
        return f"Tool.OP{self.id}"

    def inPortName(self):    # name in Monitor
        return f"Tool.IP{self.id}"

    def toolName(self):  # name in Monitor
        return f"Tool.T{self.id}"

    @staticmethod
    def searchById(port, id):
        for i in range(len(port)):
            if port[i].id == id:
                return i
        return None

    def dequeuePortById(self, port, id):
        i = self.searchById(port, id)
        if i is None: return
        job = port.pop(i)
        self.sendMonQSize(port)
        return job

    def dequeuePortByType(self, port):
        if len(port) == 0: return
        k = 0
        for i in range(len(port)):
            if port[i].type == self.prevJobType:
                k = i
                break
        job = port.pop(k)
        self.sendMonQSize(port)
        return job

    def enqueuePort(self, port, job):
        port.append(job)
        self.sendMonQSize(port)

    def dequeuePort(self, port):
        job = port.pop(0)
        self.sendMonQSize(port)
        return job

    def sendMonQSize(self, portQ):
        if id(portQ) == id(self.inPort):
            self.emq.sendMonMsg(f"queue {self.inPortName()} {len(portQ)}")
        else:
            self.emq.sendMonMsg(f"queue {self.outPortName()} {len(portQ)}")

    def sendMonEquipUtil(self):
        emq = self.con.emq
        msg = f"widget utilT{self.id} text {self.util.timeAvg(emq.Tnow) * 100:.2f}%"
        emq.sendMonMsg(msg)

    def sendMonEquipState(self):
        self.emq.sendMonMsg(f"color {self.toolName()} {self.state.value}")
        self.sendMonQSize(self.inPort)
        self.sendMonQSize(self.outPort)
        if self.id == 5 or self.id == 6:
            self.sendMonEquipUtil()

    def setState(self, s):
        self.state = s
        self.emq.sendMonMsg(f"color {self.toolName()} {s.value}")

        if s == EquipState.IDLE:
            self.job = None
        elif s == EquipState.BUSY:
            self.util.stateChange(self.Tnow(), 1)
        else:
            self.util.stateChange(self.Tnow(), 0)
        if self.id == 5 or self.id == 6:
            self.sendMonEquipUtil()

    def startProc(self):
        if (not self.idle()) or len(self.inPort) == 0:
            return
        # job = self.dequeuePort(self.inPort)  # FIFO selection
        job = self.dequeuePortByType(self.inPort)  # selection by type
        self.job = job
        if job.type != self.prevJobType:  # setup change needed
            self.setState(EquipState.SETUP)
            self.emq.scheduleEvtMsg4(self.setupTime, self, self, "setupEnd", param=job)
        else:
            self.setState(EquipState.BUSY)
            self.emq.scheduleEvtMsg4(job.getProcTime(), self, self, "jobEnd", param=job, extern=True)
        # print (f'Job-{job.id} started on Eq-{self.id}')

    def endProc(self):
        self.enqueuePort(self.outPort, self.job)
        # print (f'Job-{self.job.id} ended on Eq-{self.id}')
        self.prevJobType = self.job.type
        self.job = None
        self.setState(EquipState.IDLE)
        self.startProc()
        # ask OHT to transport

    def processEvtMsg(self, e):
        # print(e.msg, 'Tool', self.id)
        if e.msg == "jobEnd":
            # assert self.job == e.param
            self.endProc()
            self.instantEvtMsg(self.con, 'callOHT', param=e.param)
        elif e.msg == "setupEnd":
            self.setState(EquipState.BUSY)
            self.emq.scheduleEvtMsg4(self.job.getProcTime(), self, self, "jobEnd", param=self.job, extern=True)
        elif e.msg == "deli":
            jid = e.param
            job = self.con.fromOHT(jid)
            self.enqueuePort(self.inPort, job)
            job.step += 1  # advance to next step
            # print(f'Job-{job.id} step = {job.step}')
            self.startProc()
        elif e.msg == "retr":
            jid = e.param
            job = self.dequeuePortById(self.outPort, jid)
            assert job is not None
            self.con.toOHT(job)

class InitStorage(Equip):
    def __init__(self, id, emq, con):
        super().__init__(id, emq, con)

    def foupArrival(self, job):
        self.outPort.append(job)
        self.instantEvtMsg(self.con, 'callOHT', param=job)
        self.sendMonEquipState()

    def sendMonEquipState(self):
        self.sendMonQSize(self.outPort)

class FinStorage(Equip):
    def __init__(self, id, emq, con):
        super().__init__(id, emq, con)

    def collectFoup(self, job):
        # self.enqueuePort(self.inPort, job)
        # no need to save job, just increase queue size
        self.enqueuePort(self.inPort, None)
        con = self.con
        emq = con.emq
        con.tat.append(self.Tnow() - job.genAt)
        con.wip -= 1
        con.wipAvg.stateChange(emq.Tnow, con.wip)
        con.produced += 1
        self.sendMonEquipState()

    def sendMonEquipState(self):
        con = self.con
        emq = con.emq
        self.sendMonQSize(self.inPort)
        emq.sendMonMsg(f"widget TAT text {con.tat.avg():.1f}")
        emq.sendMonMsg(f"widget curWIP text {con.wip}")
        emq.sendMonMsg(f"widget avgWIP text {con.wipAvg.timeAvg(emq.Tnow):.2f}")
        emq.sendMonMsg(f"widget produced text {con.produced}")
        emq.sendMonMsg(f"widget producedPerDay text {con.produced/emq.Tnow*86400:.2f}")


    def processEvtMsg(self, e):
        if e.msg == "deli":
            jid = e.param
            job = self.con.fromOHT(jid)
            self.collectFoup(job)
        else:
            super().processEvtMsg(e)

class FabController(AModel):
    def __init__(self, emq):
        super().__init__()
        self.emq = emq
        emq.con = self
        self.inOHT = {}
        self.equips = {}
        self.initEquip(8)
        self.foupGen = FoupGen(self, 8, 12)
        self.wip = 0
        self.wipAvg = TimeAverage(emq.Tnow)
        self.produced = 0
        self.tat = Accumulator()

    def initEquip(self, nEquip):
        self.nEquip = nEquip
        for i in range(nEquip):
            if i == 0:
                eq = InitStorage(i+1, self.emq, self)
            elif i < nEquip-1:
                eq = Equip(i+1, self.emq, self)
            else:
                eq = FinStorage(i+1, self.emq, self)
            self.equips[eq.id] = eq
            self.equips[eq.outVertexName()] = eq
            self.equips[eq.inVertexName()] = eq

    def throwIn(self, foup):
        self.equips[1].foupArrival(foup)
        self.wip += 1

    # def getEquipFromName(self, name):
    #     return self.equips[name]

    def Tnow(self):
        return self.emq.Tnow

    def toOHT(self, job):
        self.inOHT[job.id] = job

    def fromOHT(self, jobId):
        job = self.inOHT.pop(jobId)
        return job

    def resetStat(self):
        self.tat.reset()
        t = self.Tnow()
        self.wipAvg.reset(t, self.wip)
        self.equips[5].util.reset(t)
        self.equips[6].util.reset(t)
        # leave produced lots unchanged

    def sendAllMonMsg(self):
        for k, e in self.equips.items():
            e.sendMonEquipState()


    def processEvtMsg(self, e):
        if e.msg == "callOHT":
            job = e.param
            if job.nextTool() is None:
                return
            ct = self.equips[job.currTool()]
            nt = self.equips[job.nextTool()]
            if self.emq.paired() != 0:
                fname = ct.outVertexName()
                tname = nt.inVertexName()
                msg = f"{self.Tnow()} job {fname} {tname} {job.id}"
                self.emq.sendPairMsg(msg)
            else:  # directly schedule OHT delivery (fixed time)
                self.emq.scheduleEvtMsg4(12.0, None, ct, "retr", param=job.id)
                self.emq.scheduleEvtMsg4(25.0, None, nt, "deli", param=job.id)

        # # schedule retrieval & delivery event into partner's EMQ directly
            # if m[1] == 'job':  # time job fv tv id
            #     ct = self.equips[m[2]]
            #     nt = self.equips[m[3]]
            #     jid = int(m[4])
            #     self.partner.scheduleEvtMsg4(1.0, None, ct, "retr", param=jid)
            #     self.partner.scheduleEvtMsg4(2.0, None, nt, "deli", param=jid)

        elif e.msg == 'resetStat':
            self.resetStat()


class ProdEvtMsgQueue(EvtMsgQueue):
    def __init__(self, name):
        super().__init__(name)
        self.clockName = "prodClock"
        self.master = True  # master-slave
        # slave : no sleep, pairing시 connect

    def processPairMsg(self, m):
        t = float(m[0])
        if m[1] == 'retr' or m[1] == 'deli':  # time retr/deli vtx jid
            eq = self.con.equips[m[2]]
            jid = int(m[3])
            ev = EvtMsg(t, None, eq, m[1], param=jid)
            self.scheduleEvtMsg(ev)
        # print(m)

def prepareFabFed(config, mon, sync):
    np.random.seed(100)

    # config = '8bay'
    if config == '8bay':
        numTools = 8
        load = 0.008
    elif config == '20bay':
        numTools = 20
        load = 0.003
    elif config == '24bay':
        numTools = 24
        load = 0.0023

    fabEMQ = ProdEvtMsgQueue('Production')

    fabEMQ.makeZmq(mon=mon, sync=sync) # Prod + Mon(Sync)
    # fabEMQ.makeZmq(mon=mon, sync=False) # Prod + Mon

    fabCon = FabController(fabEMQ)

    fabEMQ.scheduleEvtMsg4(300.0, fabCon, fabCon, "resetStat", extern=True)
    return fabEMQ

if __name__ == "__main__":
    fabEMQ = prepareFabFed(config='8bay', mon=True, sync=False)
    # fabEMQ.runSimulation()
    fabEMQ.runDualFedSimZmq(master=False)