import time
import zmq
import threading

G_URL = "tcp://127.0.0.1:5555"


def syncConnect(context, url, bind=True):
    print("Waiting for connection")
    if bind:
        sync_socket = context.socket(zmq.REP)
        sync_socket.bind(url + "1")
        sync_socket.recv()
        sync_socket.send(b'')
    else:
        sync_socket = context.socket(zmq.REQ)
        sync_socket.connect(url + "1")
        sync_socket.send(b'')
        sync_socket.recv()
    sync_socket.close()
    print("Connection synced")

################################################################################
# connect to zmq from Simulation (server) side
################################################################################


class SimulationMQ:
    def __init__(self):
        self.pubSocket = None
        self.subSocket = None
        self.pairSocket = None
        self.url = G_URL
        self.stopped = False
        self.connected = False
        self.context = zmq.Context()

    @staticmethod
    def purgeSocket(socket):
        try:
            n = 0
            while True:
                msg = socket.recv_string(flags=zmq.NOBLOCK)
                print (msg)
                n += 1
        except zmq.Again:
            return n

    def setStopSending(self, s):
        self.stopped = s

    def send_msg_raw(self, msg):
        if self.connected:
            self.pubSocket.send_string(msg)
        # print(msg)
        # pass

    def send_msg(self, msg):
        if self.connected and not self.stopped:
            self.pubSocket.send_string(msg)
        # print(msg)
        # pass

    def check_mon_msg(self):
        try:
            msg = self.subSocket.recv_string(flags=zmq.NOBLOCK)
            return msg
        except zmq.Again:
            return None


    def connect(self, url=None, hwm=1100000, sync=True):
        if url is not None:
            self.url = url
        self.pubSocket = self.context.socket(zmq.PUB)
        self.pubSocket.sndhwm = hwm  # set high water mark
        # self.pubSocket.bind(self.url)
        self.pubSocket.connect(self.url)

        # exchange sync messages
        if sync:
            syncConnect(self.context, self.url, bind=True)

        self.subSocket = self.context.socket(zmq.SUB)
        self.subSocket.connect(self.url + "2")

        filter = ""  # get every message
        self.subSocket.setsockopt_string(zmq.SUBSCRIBE, filter)

        print("Connected successfully")
        self.connected = True


    def connectPair(self, url=None, bind=True):
        if url is not None:
            self.url = url
        self.pairSocket = self.context.socket(zmq.PAIR)
        url = self.url + "3"
        if bind:
            self.pairSocket.bind(url)
        else:
            self.pairSocket.connect(url)
        print("Connected to pair socket.  Waiting for partner")

    def sendPairZmq(self, msg):
        self.pairSocket.send_string(msg)

    def checkPairZmq(self):
        try:
            return self.pairSocket.recv_string(flags=zmq.NOBLOCK)
        except zmq.Again:
            return None

    def waitPairZmq(self):
        return self.pairSocket.recv_string()


class MonitorMQ(threading.Thread):
    def __init__(self, mainWnd):
        super().__init__()
        self.subSocket = None
        self.pubSocket = None
        self.url = G_URL
        self.connected = False
        self.mainWnd = mainWnd
        self.book = mainWnd.book
        self.context = zmq.Context()

    def send_back_msg(self, msg):
        print("Message to simulator : ", msg)
        self.pubSocket.send_string(msg)

    ################################################################################
    # mainWnd : main window of monitor
    # mainWnd.book : object book
    # mainWnd.msgThreadRunning : False if mainWnd is closed, True otherwise
    # mainWnd.paused : True if pause button is pressed
    ################################################################################
    def run(self):
        print("Message thread started")
        mid = 0
        objBook = self.mainWnd.book
        while self.mainWnd.msgThreadRunning:
            mid += 1
            msg = self.subSocket.recv_string()
            # print(msg)
            objBook.processMsg(msg)  # process each message
            if mid == 100:
                mid = 0
                time.sleep(0.0001)
                if self.mainWnd.paused:
                    self.mainWnd.pauseLock.acquire()
                    self.mainWnd.pauseLock.release()


    ################################################################################
    # mainWnd : main window of monitor
    # connect simulation server and run message thread
    ################################################################################
    def bind(self, url=None):
        if url is None:
            self.url = url
        # self.subSocket = self.context.socket(zmq.SUB)
        # self.subSocket.connect(url)
        self.subSocket = self.context.socket(zmq.SUB)
        self.subSocket.sndhwm = 1100000  # set high water mark
        self.subSocket.bind(url)

        # filter = "color"  # get messages starting with 'P'
        filter = ""  # get every message
        self.subSocket.setsockopt_string(zmq.SUBSCRIBE, filter)

        self.mainWnd.msgThreadRunning = True
        self.connected = True
        self.start()

        # exchange sync messages
        if self.mainWnd.syncServer.isChecked():
            self.mainWnd.statusBar.showMessage("Waiting for server to connect at "+url)
            syncConnect(self.context, self.url, bind=False)

        self.pubSocket = self.context.socket(zmq.PUB)
        self.pubSocket.bind(url + "2")

        return True




