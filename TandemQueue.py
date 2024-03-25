from DES import *
from ConnectMQ import *
from utils import *

class Customer:
    cid = 0
    def __init__(self):
        self.id = Customer.cid
        Customer.cid += 1

# Queue selection rule
def selectNextServer(next):
    if isinstance(next, list):
        return min(next)  # select minimum queue
        # return random.choice(next)  # select random
    else:
        return next


class Server(AModel):
    def __init__(self, name, next=None):
        super().__init__()
        self.name = name
        self.Q = Queue()
        self.idle = True
        self.next = next
        self.customer = None
        self.stGen = UnifGen(0,2)

    def nCustomer(self):
        if self.idle:
            return self.Q.qsize()
        else:
            return self.Q.qsize()+1

    def __lt__(self, other):
        return self.nCustomer() < other.nCustomer()

    def doService(self):
        # global GTNow
        if self.idle and not self.Q.empty():
            self.customer = self.Q.get()
            print (G_EMQ.Tnow, 'service start', self.customer.id)
            MQ_sim_send_msg('dequeue ' + self.name + '.Q')
            G_EMQ.scheduleEvtMsg4(self.stGen.get(), self, self, "end", param=self.customer)
            self.idle = False
            MQ_sim_send_msg('color %s.Svr %d' % (self.name, 2))

    def processEvtMsg(self, e):
        if e.msg == 'arrival':
            c = e.param
            self.Q.put(c)
            MQ_sim_send_msg('enqueue ' + self.name + '.Q')
            self.doService()
        else:  # e.msg == 'end'
            c = e.param
            print (e.time, 'serive end', c.id)
            if self.next is None:
                MQ_sim_send_msg('enqueue FinQ')
                print (e.time, "job completed", c.id)
            else:
                ns = selectNextServer(self.next)
                self.instantEvtMsg(ns, "arrival", c)
            self.idle = True
            MQ_sim_send_msg('color %s.Svr %d' % (self.name, 4))
            self.doService()

class ArrivalGenerator(AModel):
    def __init__(self, next=None):
        super().__init__()
        self.next = next
        self.iatGen = RndGen()

    def scheduleInitialArrival(self):
        G_EMQ.scheduleEvtMsg4(self.iatGen.get(), self, self, "next")

    def processEvtMsg(self, e):
        if e.msg == "next":
            c = Customer()
            print (e.time, e.msg, c.id)
            # GEMQ.scheduleEvtMsg4(0.0, self, svr, "arrival")
            self.instantEvtMsg(self.next, "arrival", param=c)
            G_EMQ.scheduleEvtMsg4(self.iatGen.get(), self, self, "next")

if __name__ == "__main__":
    MQ_bindFromSimulation(sync=True)

    # single queue single server model
    svr4 = Server('Server4')
    svr4.stGen = UnifGen(0,2)
    svr3 = Server('Server3', svr4)
    svr3.stGen = TriGen(0,3,1.5)  # mean 1
    svr2 = Server('Server2', svr4)
    svr2.stGen = TriGen(0,6,3)  # mean 3
    svr1 = Server('Server1', [svr2,svr3])
    svr1.stGen = UnifGen(0,2)

    ag = ArrivalGenerator(svr1)
    # ag.iatGen = ExpGen(1.0)
    ag.iatGen = TriGen(0,2,1)
    ag.scheduleInitialArrival()

    G_EMQ.runSimulation()