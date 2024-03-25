# import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
# from PyQt5 import uic
import time
import zmq
# import random
import threading
from Graph import *
from StateDef import *
from utils import *

#                 0         1        2        3           4         5            6         7           8         9         10          11
gPalette = [Qt.white, Qt.black, Qt.red, Qt.darkRed, Qt.green, Qt.darkGreen, Qt.blue, Qt.cyan, Qt.magenta, Qt.yellow, Qt.darkYellow, Qt.gray]
gBrushPal = [QBrush(gPalette[s]) for s in range(12)]
gPenPal = [QPen(gPalette[s]) for s in range(12)]


class RootObj(QObject):
    colorSignal = pyqtSignal(int)
    moveSignal = pyqtSignal(float, float)
    animSignal = pyqtSignal(float, float, float)
    textSignal = pyqtSignal(str)

    def __init__(self, name, x=0, y=0):
        super().__init__()
        self.name = name
        self.x = x
        self.y = y
        self.org_x = x
        self.org_y = y
        self.colorSignal.connect(self.colorSignalHandler)
        self.moveSignal.connect(self.moveSignalHandler)
        self.animSignal.connect(self.animSignalHandler)
        self.textSignal.connect(self.textSignalHandler)

    def posInc(self, pos):
        # return pos
        return QPointF(pos.x()-self.org_x, pos.y()-self.org_y)

    @pyqtSlot(QPointF)
    def _set_position(self, pos):
        # self.shape.setPos(self.shape.mapFromScene(pos))
        # incremental position
        self.shape.setPos(self.posInc(pos))
        self.x = pos.x()
        self.y = pos.y()

    position = pyqtProperty(QPointF, fset=_set_position)

    @pyqtSlot(int)
    def colorSignalHandler(self, color):
        self.color = color
        self.shape.setBrush(gBrushPal[color])

    @pyqtSlot(float, float)
    def moveSignalHandler(self, x, y):
        self._set_position(QPointF(x, y))

    @pyqtSlot(float, float, float)
    def animSignalHandler(self, x, y, t):
        self.anim = QPropertyAnimation(self, b"position")
        self.anim.setDuration(t)
        self.anim.setStartValue(QPointF(self.x, self.y))
        self.anim.setEndValue(QPointF(x, y))
        self.anim.start()

    @pyqtSlot(str)
    def textSignalHandler(self, txt):
        self.text.setPlainText(txt)

    def addText(self, txt, size=7):
        self.text = QGraphicsTextItem(txt)
        self.text.setParentItem(self.shape)
        self.text.setPos(self.x, self.y)
        f = QFont()
        f.setPointSize(size)
        self.text.setFont(f)
        return self.text

    def processMsg(self, m):
        if m[0] == 'color':
            self.colorSignal.emit(int(m[2]))
        elif m[0] == 'move':
            self.moveSignal.emit(float(m[2]), float(m[3]))
        elif m[0] == 'anim':
            self.animSignal.emit(float(m[2]), float(m[3]), float(m[4]))
        elif m[0] == 'text':
            if m[2] == 'None':
                self.textSignal.emit('')
            else:
                self.textSignal.emit(m[2])
        else:
            print(m)

#################################################
#  Object creation for label text
#     lo = LabelObj(name, x, y, color, size)
#     book.append(lo)
#           (x,y) : start point
#           color : text color
#  Message commands
#     verb name parameters
#        verb : move, anim, color, text
#################################################
class LabelObj(RootObj):
    def __init__(self, name, x=0, y=0, color=1, size=7):
        super().__init__(name, x, y)
        self.text = QGraphicsTextItem(name)
        self.text.setPos(self.x, self.y)
        self.text.setDefaultTextColor(gPalette[color])
        self.shape = self.text
        f = QFont()
        f.setPointSize(size)
        self.text.setFont(f)

    @pyqtSlot(int)
    def colorSignalHandler(self, color):
        self.text.setDefaultTextColor(gPalette[color])


#################################################
#  Object creation for line
#     lo = LineObj(name, x, y, ex, ey, c, showName)
#     book.append(lo)
#           (x,y) : start point
#           ex, ey : end point
#           c : line color
#           showName : show name at start point
#  Message commands
#     verb name parameters
#        verb : move, anim, color, text
#################################################
class LineObj(RootObj):
    def __init__(self, name, x=0, y=0, ex=70, ey=50, c=1, showName=False, head=0, nameSize=7):
        super().__init__(name, x, y)
        self.ex = ex
        self.ey = ey
        self.head = head
        self.pen = gPenPal[c]
        self.shape = QGraphicsLineItem(self.x, self.y, self.ex, self.ey)
        self.shape.setPen(self.pen)
        if showName:
            self.addText(self.name, nameSize)
        if head > 0:
            self.arrowHead(head)

    def arrowHead(self, s):
        dx, dy = self.ex-self.x, self.ey-self.y
        d = self.head
        d2 = d/2
        x1, y1 = rotate(dx, dy, -d, d2, self.ex, self.ey)
        x2, y2 = rotate(dx, dy, -d, -d2, self.ex, self.ey)
        s1 = QGraphicsLineItem(self.ex, self.ey, x1, y1)
        s1.setParentItem(self.shape)
        s2 = QGraphicsLineItem(self.ex, self.ey, x2, y2)
        s2.setParentItem(self.shape)

    @pyqtSlot(int)
    def colorSignalHandler(self, color):
        self.shape.setPen(gPenPal[color])


#################################################
#  Object creation for box
#     bo = BpxObj(name, x, y, wx, wy, c, showName)
#     book.append(bo)
#           (x,y) : location of queue front
#           wx, wy : Box size
#           c : fill color
#           showName : show name in box
#  Message commands
#     verb name parameters
#        verb : move, anim, color, text
#################################################
class BoxObj(RootObj):
    def __init__(self, name, x=0, y=0, wx=70, wy=50, c=0, showName=False, nameSize=7):
        super().__init__(name, x, y)
        self.wx = wx
        self.wy = wy
        self.pen = gPenPal[1]  # black boundary
        self.color = c
        self.brush = gBrushPal[self.color]
        self.shape = self.makeShape(x, y, wx, wy)
        self.shape.setPen(self.pen)
        self.shape.setBrush(self.brush)
        if showName:
            self.addText(self.name, nameSize)

    def makeShape(self, x, y, wx, wy):
        return QGraphicsRectItem(x, y, wx, wy)


class SpecialBoxObj(RootObj):
    def __init__(self, name, x=0, y=0, wx=70, wy=50, c=0, showName=False, nameSize=7):
        super().__init__(name, x, y)
        self.wx = wx
        self.wy = wy
        self.pen = gPenPal[1]  # black boundary
        self.color = c
        self.brush = gBrushPal[self.color]
        self.shape = self.makeShape(x, y, wx, wy)
        self.shape.setPen(self.pen)
        self.shape.setBrush(self.brush)
        if showName:
            self.addText('', nameSize)

    def makeShape(self, x, y, wx, wy):
        return QGraphicsRectItem(x, y, wx, wy)


#################################################
#  Object creation for ellipse
#     eo = EllipseObj(name, x, y, wx, wy, c, showName)
#     book.append(eo)
#           (x,y) : location of queue front
#           wx, wy : Ellipse size
#           c : fill color
#           showName : show name in box
#  Message commands
#     verb name parameters
#        verb : move, anim, color, text
#################################################
class EllipseObj(BoxObj):
    def makeShape(self, x, y, wx, wy):
        return QGraphicsEllipseItem(x, y, wx, wy)

#################################################
#  Object creation
#     go = GroupObj(groupName, x, y)
#           (x,y) : location of group
#     go.addToGroup(BoxObj('IO1', 20, 80, 20, 20, c=2))
#     go.addToGroup(BoxObj('IO2', 40, 80, 20, 20, c=3))
#     book.append(go)
#  Message commands
#     move/anim groupName parameters
#     color/text groupName.compName parameters
#################################################
class GroupObj(RootObj):
    def __init__(self, name, x=0, y=0):
        super().__init__(name, x, y)
        self.group ={}
        self.shape = QGraphicsItemGroup()

    def addToGroup(self, obj):
        self.group[obj.name] = obj
        self.shape.addToGroup(obj.shape)

    def findPart(self, partName):
        try:
            p = self.group[partName]
            return p
        except KeyError:  # not found
            print("Component object not found :", partName)
            return None

    def processMsg(self, m):
        # parse index
        m1 = m[1]
        a = m1.find('.')
        if a < 0:
            super().processMsg(m)
        else:
            pobj = self.findPart(m1[a+1:])
            if pobj is not None:  # found
                pobj.processMsg(m)


#################################################
#  Object creation
#     bao = BoxArrayObj(name, x, y, dx, nx, dy, ny, wx, wy, c)
#     book.append(bqo)
#           (x,y) : location of UL corner
#           dx, dy : spacing
#           nx, ny : # of columns & rows
#           wx, wy : box size
#           c : fill color
#  Message commands
#     verb name[index] parameters
#################################################
class BoxArrayObj(GroupObj):
    def __init__(self, name, x=0, y=0, dx=0, nx=1, dy=0, ny=1, wx=10, wy=10, c=5):
        super().__init__(name, x, y)
        self.nx = nx
        self.ny = ny
        self.n = nx * ny
        self.array = []
        for i in range(ny):
            yi = y + i*dy
            for j in range(nx):
                xj = x + j*dx
                k = self.idx(i,j)
                namek = "%s%i" % (name,k)
                bok = BoxObj(namek, xj, yi, wx, wy, c)
                self.array.append(bok)
                self.addToGroup(bok)

    def idx(self, i, j):
        return i*self.nx + j

    def processMsg(self, m):
        # parse index
        m1 = m[1]
        a = m1.find('[')+1
        b = m1.find(']')
        assert a > 0 and b > 0, "array must be name[i] or name[i,j]"
        c = m1.find(',')
        if c >= 0:  # 2D array
            i = int(m1[a:c])
            j = int(m1[c+1:b])
            k = self.idx(i,j)
        else:
            k = int(m1[a:b])
        bok = self.array[k]
        # bok.stateSignal.emit(int(m[4]))
        bok.processMsg(m)

#################################################
#  Object creation for numeric queue
#     nqo = NumQObj(name, x, y, wx, wy, c)
#     book.append(nqo)
#           (x,y) : location of queue front
#           wx, wy : Ellipse size
#           c : fill color
#  Message commands
#     enqueue name
#     dequeue name
#     queue name len
#################################################
class NumQEllObj(EllipseObj):
    def __init__(self, name, x=0, y=0, wx=70, wy=50, c=0):
        nameSize = wy/5
        super().__init__(name, x, y, wx, wy, c, True, nameSize)
        self.setCount(0)
        self.text.setPos(x+wx/4, y+wy/4)

    def setCount(self, qs):
        self.qCount = qs
        self.textSignal.emit(str(self.qCount))

    def processMsg(self, m):
        if m[0] == 'queue':
            self.setCount(int(m[2]))
        elif m[0] == 'enqueue':
            self.changeCount(self.qCount+1)
        elif m[0] == 'dequeue':
            self.changeCount(self.qCount-1)
        else:
            super().processMsg(m)

class NumQBoxObj(BoxObj):
    def __init__(self, name, x=0, y=0, wx=70, wy=50, c=0):
        nameSize = wy/5
        super().__init__(name, x, y, wx, wy, c, True, nameSize)
        self.setCount(0)
        self.text.setPos(x + wx / 4, y + wy / 4)

    def setCount(self, qs):
        self.qCount = qs
        self.textSignal.emit(str(self.qCount))

    def processMsg(self, m):
        if m[0] == 'queue':
            self.setCount(int(m[2]))
        elif m[0] == 'enqueue':
            self.changeCount(self.qCount + 1)
        elif m[0] == 'dequeue':
            self.changeCount(self.qCount - 1)
        else:
            super().processMsg(m)


#################################################
#  Object creation
#     bqo = ArrayQueueObj(name, x, y, w, n, dir, cf)
#     book.append(bqo)
#           (x,y) : location of queue front
#           w : cell size
#           n : # of cells (queue capacity)
#           dir = '+X' : (rear) left-right (front)
#               = '-X' : (rear) right-left (front)
#               = '+Y' : (rear) top-bottom (front)
#               = '-Y' : (rear) bottom-top (front)
#  Message commands
#     enqueue name [color]
#     dequeue name
#################################################
class ArrayQueueObj(BoxArrayObj):
    def __init__(self, name, x, y, w=10, n=15, dir='+X', cf=5):
        wx, wy = w, w
        if dir[1] =='X': # horizontal
            nx = n
            ny = 1
            if dir == '+X' : # Left->Right, front at Right
                wx = -w
                x += (n-1)*w
        else: # vertical
            nx = 1
            ny = n
            if dir == '+Y' : # Top->Botton, front at Bottom
                wy = -w
                y += (n - 1) * w
        dx, dy = wx, wy
        super().__init__(name, x, y, dx, nx, dy, ny, w, w, c=0)
        self.qMax = n
        self.fullColor = cf
        self.qCount = 0
        self.setCount(0)

    @staticmethod
    def clamp(x, a, b):
        if x < a: return a
        elif x >= b: return b
        return x

    def setCount(self, qs):
        qold = self.clamp(self.qCount, 0, self.qMax) - 1
        qnew = self.clamp(qs, 0, self.qMax) - 1
        self.qCount = qs
        if qnew > qold:  # increasing
            for i in range(qold+1, qnew+1):
                self.array[i].colorSignal.emit(self.fullColor)
        elif qnew < qold: # decreasing
            for i in range(qold, qnew, -1):
                self.array[i].colorSignal.emit(0)

    def processMsg(self, m):
        if m[0] == 'queue':
            self.setCount(int(m[2]))
        elif m[0] == 'enqueue':
            if self.qCount>=0 and self.qCount<self.qMax:
                if len(m) > 2:
                    c = int(m[2])
                else:
                    c = self.fullColor
                self.array[self.qCount].colorSignal.emit(c)
            self.qCount += 1
        elif m[0] == 'dequeue':
            if self.qCount>0: self.qCount -= 1
            if self.qCount>=0 and self.qCount<self.qMax:
                self.array[self.qCount].colorSignal.emit(0)
        else:
            super().processMsg(m)


class ObjBook:
    def __init__(self, mainWnd, view, scene):
        self.list = []
        self.dict = {}
        self.mainWnd = mainWnd
        self.view = view
        self.scene = scene

    def append(self, obj):
        self.list.append(obj)
        self.dict[obj.name] = obj
        self.scene.addItem(obj.shape)

    def widgetMsg(self, m):
        if m[0] != 'widget': return False
        # print(m)
        self.mainWnd.setWidgetSignal.emit(m)
        return True

    def processMsg(self, msg):
        try:
            #print(msg)
            m = msg.split()
            if self.widgetMsg(m): return
            k = m[1].find('[')
            if k >= 0: # object array
                obj = self.dict[m[1][:k]]
            else:
                k = m[1].find('.')
                if k >= 0:
                    obj = self.dict[m[1][:k]]
                else:
                    obj = self.dict[m[1]]
            obj.processMsg(m)
        except KeyError:
            print(msg)
            # pass


class LogPlayer(threading.Thread):
    def __init__(self, mainWnd, logFile, timeScale):
        super().__init__()
        self.mainWnd = mainWnd
        self.book = mainWnd.book
        self.logFileName = logFile
        self.timeScale = timeScale
        self.Tsince = -1

    def changeTimeScale(self, timeScale):
        self.timeScale = timeScale
        self.Tsince = self.Tnow
        self.timeSince = time.time()

    def run(self):
        self.mainWnd.logThreadRunning = True
        f = open(self.logFileName, 'r')

        self.timeSince = time.time()
        for line in f:
            # print(line)
            self.Tnow = float(line[:12])
            if self.timeScale > 0:
                if self.Tsince < 0:
                    self.Tsince = self.Tnow
                else:
                    dt = (self.Tnow - self.Tsince) / self.timeScale - (time.time() - self.timeSince)
                    if dt > 0:
                        if dt > 1: dt = 1
                        time.sleep(dt)
            self.book.processMsg(line[13:])
            if self.mainWnd.paused:
                self.mainWnd.pauseLock.acquire()
                self.changeTimeScale(self.timeScale)
                self.mainWnd.pauseLock.release()
            if not self.mainWnd.logThreadRunning:
                break
        f.close()
