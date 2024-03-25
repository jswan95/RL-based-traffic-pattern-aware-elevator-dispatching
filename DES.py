# from queue import *
from ConnectMQ import *
from utils import infinity, MyPQ
import pickle
import sys


class EvtMsg:
    def __init__(self, tt, fm, to, msg, param=None, extern=False):
        self.time = tt
        self.fm = fm
        self.to = to
        self.msg = msg
        self.param = param
        self.extern = extern
        self.canceled = False

    def __lt__(self, other):
        return self.time < other.time


class EvtMsgQueue(MyPQ):  #(PriorityQueue):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.Tsince= 0.0
        self.Tnow = 0.0
        self.timeScale = 3  # 0 for as fast as possible simulation, 1 for real time, 10 for 10x faster
        self.timeSince = time.time()
        self.checkInterval = 4 * self.timeScale
        self.master = True
        self.simZMQ = None
        self.monLog = None
        self.pairMQ = []
        self.partner = None
        self.sendPairMsg = self.sendPairMsgNone
        self.recvPairMsg = self.recvPairMsgNone
        # self.clockName = "simClock"

    # put(e) : enqueue
    # get(e) : dequeue
    # qsize() : # of items in queue
    # empty() : check if empty

    def setMonLog(self, f):
        if self.monLog is not None:
            self.monLog.close()
        self.monLog = f
        if self.paired() == 1:  # internal pairing
            self.partner.monLog = f

    def peepTime(self):
        if self.empty(): return infinity
        return self.heap[0].time   #self.queue[0].time

    def externalNextEvent(self):
        if self.empty(): return True
        return self.heap[0].external  #self.queue[0].external

    def scheduleEvtMsg4(self, dtime, fm, to, msg, param=None, extern=False):
        e = EvtMsg(self.Tnow + dtime, fm, to, msg, param, extern)
        return self.scheduleEvtMsg(e)

    def scheduleEvtMsg(self, e):
        assert e.time >= self.Tnow
        self.put(e)
        if self.timeScale <= 0:
            return 0
        else:
            return (e.time - self.Tnow) / self.timeScale

    @staticmethod
    def equalOrNone(a, b):
        return (a is None) or (a == b)

    def cancelEvtMsg(self, to=None, msg=None, one=True):
        for e in self.heap:  # not time order
            if self.equalOrNone(to, e.to) and self.equalOrNone(msg, e.msg):
                # mark as canceled
                # it won't be processed in runNextEvent
                e.canceled = True
                if one: # cancel the first found event only
                    return
                # if not one: cancel all messages found

    def timeResync(self):
        self.Tsince = self.Tnow
        self.timeSince = time.time()

    # check message back from Monitor
    def checkMonMsg(self):
        if not self.simZMQ.connected: return
        msg = self.simZMQ.check_mon_msg()
        if msg is None: return
        print(msg)
        self.timeResync()
        m = msg.split()
        if m[0] == "timescale":
            self.timeScale = float(m[1])
            self.checkInterval = round(40*self.timeScale)
            if self.checkInterval <= 0: self.checkInterval = 1
        elif m[0] == "stop":  # stop sending messages
            self.simZMQ.setStopSending(True)
        elif m[0] == "restart": # restart sending
            self.simZMQ.setStopSending(False)

    def advanceToNextEvt(self, ne):
        assert ne.time >= self.Tnow
        self.Tnow = ne.time
        if self.master and self.timeScale > 0:  # only master sleeps
            dt = (self.Tnow - self.Tsince) / self.timeScale - (time.time() - self.timeSince)
            if dt > 0:
                if dt > 1:  dt = 1  # max sleep time = 1 sec
                time.sleep(dt)
            # print (self.timeScale, self.Tnow, dt)

    def sendMonMsg(self, msg):
        # print (msg)
        if self.simZMQ is None:
            if msg[:6] == 'widget':
                print(msg)
        else:
            self.simZMQ.send_msg(msg)
        if self.monLog is not None:
            self.monLog.write(f"{self.Tnow:12.3f} {msg}\n")
        # print(msg)

    def paired(self):
        if self.partner is not None:
            return 1  # internal pairing
        elif self.simZMQ is None or self.simZMQ.pairSocket is None:
            return 0  # no pairing
        else:
            return 2  # external pairing

    def solo(self):
        return self.paired() == 0

    # internal pairing
    # self is master, other is slave
    def pairingInternal(self, other):
        self.partner = other
        self.master = True
        other.master = False
        other.partner = self
        other.simZMQ = self.simZMQ
        # if other.simZMQ is None:  # share socket
        #     other.simZMQ = self.simZMQ
        # elif self.simZMQ is None:
        #     self.simZMQ = other.simZMQ
        self.sendPairMsg = self.sendPairMsgInternal
        other.sendPairMsg = other.sendPairMsgInternal
        self.recvPairMsg = self.recvPairMsgInternal
        other.recvPairMsg = other.recvPairMsgInternal

    # external pairing using zmq
    def pairingExternal(self, master):
        self.master = master
        self.simZMQ.connectPair(bind=master) # master binds, slave connects
        self.sendPairMsg = self.sendPairMsgZmq
        self.recvPairMsg = self.recvPairMsgZmq


    def sendPairMsgInternal(self, msg):
        self.partner.pairMQ.append(msg)

    def sendPairMsgZmq(self, msg):
        # print(f"{self.name} sent '{msg}' @ {self.Tnow}")
        self.simZMQ.sendPairZmq(msg)

    def sendPairMsgNone(self, msg):
        # print("Pair msg", msg)
        pass

    def sendPairSimpleMsg(self, m):
        msg = f"{self.peepTime()} {m}"
        self.sendPairMsg(msg)

    def recvPairMsgInternal(self):
        if len(self.pairMQ) > 0:
            return self.pairMQ.pop(0)
        else:
            return None

    def recvPairMsgZmq(self):
        return self.simZMQ.waitPairZmq()

    def recvPairMsgNone(self):
        return None

    def checkPairMsg(self):
        while True:
            msg = self.recvPairMsg()
            if msg is None:
                return
            # print(self.Tnow, self.name, "received", msg)
            m = msg.split()
            self.processPairMsg(m)  # may change event queue

    def processPairMsg(self, m):
        # override this
        pass

    def runNextEvent(self, numEvt):
        ne = self.get()
        if ne.canceled: return  # canceled event

        # print (self.name, "processes @", ne.time, ne.msg)
        self.advanceToNextEvt(ne)
        ne.to.processEvtMsg(ne)
        if numEvt % self.checkInterval == 0:
            self.sendMonMsg(f"widget {self.clockName} text {self.Tnow:.3f}")
            self.checkMonMsg()

    def runSimulation(self):
        if self.paired() == 1:  # internal pairing
            return self.runDualFedSimInternal(self.partner)
        self.sendPairMsg = self.sendPairMsgNone
        numEvt = 0
        while not self.empty():
            numEvt += 1
            self.runNextEvent(numEvt)

    # def waitPartner(self):
    #     while self.peepTime() > self.barrier:
    #         self.sendNull()
    #         msg = self.simZMQ.pairSocket.recv_string()
    #         print (f"{self.name} received '{msg}'")
    #         m = msg.split()
    #         if m[1] == 'null':
    #             self.barrier = float(m[0])
    #         else:
    #             self.processPairMsg(m)  # may change event queue



    # def waitPartner(self):
    #     while self.getPartnerTime() < self.peepTime():
    #         pass

    # def getPartnerTime(self):
    #     self.sendPairSimpleMsg('nullReq')
    #     while True:
    #         msg = self.recvPairMsg()
    #         # print (f"{self.name} received '{msg}', peepTime is {self.peepTime()}")
    #         m = msg.split()
    #         if m[1] == 'null':
    #             return float(m[0])
    #         elif m[1] == 'nullReq':
    #             self.sendPairSimpleMsg('null')
    #         else:
    #             self.processPairMsg(m)  # may change event queue

    def waitPartner(self):
        self.sendPairSimpleMsg('nullReq')
        while True:
            msg = self.recvPairMsg()
            # print (f"{self.name} received '{msg}', peepTime is {self.peepTime()}")
            m = msg.split()
            if m[1] == 'null':
                partnerTime = float(m[0])
                if partnerTime >= self.peepTime(): return
                self.sendPairSimpleMsg('nullReq')
            elif m[1] == 'nullReq':
                self.sendPairSimpleMsg('null')
            else:
                self.processPairMsg(m)  # may change event queue

    # external pairing
    def runDualFedSimZmq(self, master):
        self.pairingExternal(master)

        numEvt = 0
        while not (self.empty()):
            numEvt += 1
            self.waitPartner()
            self.runNextEvent(numEvt)
            if numEvt % self.checkInterval == 0:
                print (self.name, "Tnow =", self.Tnow)


    # internal pairing
    def runDualFedSimInternal(self, other):
        self.pairingInternal(other)
        numEvt = 0
        while not (self.empty() and other.empty()):
            numEvt += 1
            if self.peepTime() <= other.peepTime():
                self.runNextEvent(numEvt)
                other.checkPairMsg()
            else:
                other.runNextEvent(numEvt)
                self.checkPairMsg()

    def makeZmq(self, mon=False, sync=False):
        self.simZMQ = SimulationMQ()
        if mon:
            self.simZMQ.connect(sync=sync)
            self.timeScale = 3
            time.sleep(0.5)  # wait a little
        else:
            self.timeScale = 0


    def saveState(self, fileName):
        sys.setrecursionlimit(10000)
        f = open(fileName, "wb")
        monLog = self.monLog  # file handle can't be pickled
        self.monLog = None
        simZMQ = self.simZMQ
        self.simZMQ = None
        if self.partner is not None:
            monLogPartner = self.partner.monLog
            self.partner.monLog = None
            simZMQPartner = self.partner.simZMQ
            self.partner.simZMQ = None

        pickle.dump(self, f)

        self.monLog = monLog
        self.simZMQ = simZMQ
        if self.partner is not None:
            self.partner.monLog = monLogPartner
            self.partner.simZMQ = simZMQPartner
        f.close()

    def prepareQuit(self):
        pass


def loadState(fileName):
    f = open(fileName, "rb")
    emq = pickle.load(f)
    f.close()
    emq.timeResync()
    return emq


class AModel:
    # def __init__(self):
    #     pass

    # instantEvtMsg : EMQ에 넣지 않고 바로 Processing
    def instantEvtMsg(self, to, msg, param=None):
        e = EvtMsg(None, self, to, msg, param)
        to.processEvtMsg(e)

    def processEvtMsg(self, e):
        print(e.time, e.msg)
