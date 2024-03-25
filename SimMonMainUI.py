import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5 import uic
from SceneExamples import *
from ConnectMQ import *
from time import *

class SimAnimWindow(QMainWindow):
    setWidgetSignal = pyqtSignal(list)
    def __init__(self):
        super().__init__()
        # UI Layout
        uic.loadUi('SimMon.ui', self)
        # self.centralWidget : windowd의 main에 있는 widget
        # self.bottomWidgets : 아레쪽에 button들 모아 놓은 widget
        # self.rightWidgets : 오른쪽에 button들 모아 놓은 widget
        self.viewport.initViewport2D(self)

        self.msgThreadRunning = False
        self.logThreadRunning = False
        self.paused = False
        self.dropping = False
        self.pauseLock = threading.Lock()
        self.pauseButton.clicked.connect(self.pauseButtonClicked)
        self.connectButton.clicked.connect(self.connectButtonClicked)
        self.dropButton.clicked.connect(self.dropButtonClicked)
        self.playLogButton.clicked.connect(self.playLogButtonClicked)
        self.speedSlider.valueChanged.connect(self.speedSliderChanged)
        self.setWidgetSignal.connect(self.setWidgetHandler)

        self.monMQ = MonitorMQ(self)
        self.connectURL.setText(self.monMQ.url)

    def getWidget(self, name):
        try:
            return self.__dict__[name]
        except KeyError:
            return None


    def getTimeScale(self):
        v = self.speedSlider.value()
        f = v / 10
        if v == 1000:
            f = 0
        return f

    def speedSliderChanged(self):
        f = self.getTimeScale()
        if f == 0:
            s = 'Speed factor (AFAP)'
        else:
            s = f'Speed factor({f:.1f}x)'
        self.speedLabel.setText(s)

        if self.monMQ.connected:
            msg = f"timescale {f:.1f}"
            self.monMQ.send_back_msg(msg)
        if hasattr(self, "logPlayer"):
            self.logPlayer.changeTimeScale(f)

    def connectButtonClicked(self):
        if self.msgThreadRunning:
            self.statusBar.showMessage ("Message thread is already running")
            return

        url = self.connectURL.text()
        if self.monMQ.bind(url):
            self.statusBar.showMessage("Connected successfully")
        else:
            self.statusBar.showMessage("Connection failed")

    def pauseButtonClicked(self):
        # if not self.msgThreadRunning:
        #     return  # no thread to pause yet

        if self.paused:
            self.paused = False
            self.pauseButton.setText("Pause")
            self.statusBar.showMessage ("Resumed")
            # self.pause_cond.notify()
            self.pauseLock.release()
        else:
            self.pauseLock.acquire()
            self.paused = True
            self.pauseButton.setText("Resume")
            self.statusBar.showMessage("Paused")

    def dropButtonClicked(self):
        if not self.monMQ.connected: return
        if self.dropping :
            self.dropping = False
            self.dropButton.setText("Drop Msg")
            self.statusBar.showMessage("Getting messages")
            self.monMQ.send_back_msg("restart")
        else:
            self.dropping = True
            self.dropButton.setText("Get Msg")
            self.statusBar.showMessage("Dropping messages")
            self.monMQ.send_back_msg("stop")

    def playLogButtonClicked(self):
        res = QFileDialog.getOpenFileName(self)
        fName = res[0]
        if fName != "":
            timeScale = self.getTimeScale()
            self.statusBar.showMessage (f"Playing monitor log file {fName}")
            self.logPlayer = LogPlayer(self, fName, timeScale)
            self.logPlayer.start()


    @pyqtSlot(list)
    def setWidgetHandler(self, param):
        # assumes that param[0] == 'widget'
        w = self.getWidget(param[1])
        if w is None:
            print(f"widget {param[1]} not found")
            return
        if param[2] == 'text':
            w.setText(param[3])
        elif param[2] == 'value':
            w.setValue(float(param[3]))
        elif param[2] == 'table': # table item text
            r = int(param[3])
            c = int(param[4])
            w.item(r,c).setText(param[5])

    def closeEvent(self, event):
        self.msgThreadRunning = False
        self.logThreadRunning = False

class Viewport2D(QGraphicsView):
    def initViewport2D(self, parent):
        self.parent = parent
        self.scene = QGraphicsScene()
        parent.book = ObjBook(parent, self, self.scene)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setCacheMode(QGraphicsView.CacheNone)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def wheelEvent(self, e):
        if e.angleDelta().y() > 0:
            self.scale(1.25, 1.25)
        else:
            self.scale(0.8, 0.8)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Up:
            self.scale(1.25, 1.25)
        elif e.key() == Qt.Key_Down:
            self.scale(0.8, 0.8)

# main program
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SimAnimWindow()
    buildScene_Building(window.book)
    window.showMaximized()
    sys.exit(app.exec_())

