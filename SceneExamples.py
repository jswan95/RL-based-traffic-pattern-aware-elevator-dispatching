from SimMonObj import *
from elevator_controller import CarState

#############################################################################
# Elevator GUI
#############################################################################
def makeSingleElevator(go, i, sf):

    go.addToGroup(LineObj('', x=500 + i * 200, y=100, ex=500 + i * 200, ey=3250, c=1, showName=False, head=0, nameSize=10))
    for j in range(1, 21):
        go.addToGroup(LineObj('', x=500 + i * 200 - 3, y=j * 150 + 80, ex=500 + i * 200 + 3, ey=j * 150 + 80, c=1, showName=False, head=0, nameSize=10))

def makeElevatorAll(book, nElevator, x, y, sf=50):
    go = GroupObj('Elevator')
    go.addToGroup(BoxObj(f'Elevator Controller', 600, -50, 16 * sf, 3*sf, c=11, showName=True, nameSize=60))
    for i in range(1, nElevator + 1):
        makeSingleElevator(go, i, sf)
    book.append(go)
    return go

def makeFloorQueue(go, k, x, y, Qup, sf):
    if not Qup:
        upx = x * sf
        downx = x * sf
        upy = y * sf + 50
        downy = y * sf + 70
        updir = '-X'
        downdir = '+X'

    go.addToGroup(LabelObj(f'F{21 - k}', x * sf + 400, y * sf + 35, 1, 40))
    go.addToGroup(SpecialBoxObj(f'cup{21 - k}', x * sf+340, upy - 20, 40, 40, c=0, showName=True, nameSize=30))
    go.addToGroup(BoxObj(f'U', x * sf + 300, upy - 20, 40, 40, c=11, showName=True, nameSize=30))
    go.addToGroup(SpecialBoxObj(f'cdown{21- k}', x * sf+340, downy, 40, 40, c=0, showName=True, nameSize=30))
    go.addToGroup(BoxObj(f'D', x * sf + 300, downy, 40, 40, c=11, showName=True, nameSize=30))
    go.addToGroup(ArrayQueueObj(f'up{21 - k}', upx - 300, upy - 20, w=40, n=15, dir=downdir, cf=4))
    go.addToGroup(ArrayQueueObj(f'down{21 - k}', downx - 300, downy, w=40, n=15, dir=downdir, cf=2))


def makeFloorQueueAll(book, x, y, rindex, sf=50):
    go = GroupObj('Floor')
    for j in range(len(y)):
        for i in range(len(x)):
            if j % 2 == 0:
                k = j*len(x) + i + 1
                Qup = False
            else:
                Qup = False
                if rindex:
                    k = j*len(x) + (len(x) - i)
                else:
                    k = j * len(x) + i + 1
            makeFloorQueue(go, k, x[i], y[j], Qup, sf)

    book.append(go)
    return go


def makeFloors(book, nFloor, sf=50):
    x = [1]
    y = [3 * i for i in range(1, nFloor + 1)]
    rindex = True
    go = makeFloorQueueAll(book, x, y, rindex, sf=50)
    return go

def makeElevators(book, nCars, sf = 50):
    x = [1, 2, 3, 4]
    y = [0, 0, 1500, 1500]
    go = makeElevatorAll(book, nCars, x, y, sf=50)
    return go

def shapeAndLabel(book, boxShape, x, y, wx, wy, c, dx, dy, label):
    if boxShape:
        shape = BoxObj('', x, y, wx, wy, c=c)
    else:
        shape = EllipseObj('', x, y, wx, wy, c=c)
    book.append(shape)
    book.append(LabelObj(label, x+dx, y+dy, size=50))

def makeLegend(book):
    x, y = 1600, 1000
    for s in CarState:
        shapeAndLabel(book, True, x, y, 120, 160, s.value, 150, 50, s.name)
        y += 400

def buildScene_Building(book):
    nElevator = 4
    nFloor = 20
    makeFloors(book, nFloor, GV_factor)
    makeElevators(book, nElevator, GV_factor)
    makeLegend(book)

    # make elevator cars
    for id in range(1, 1 + nElevator):
        v = BoxObj(f'Car{id}', 440 + id * 200, 3000, 3 * 40, 4*40, c=0, showName=True, nameSize=40)
        book.append(v)