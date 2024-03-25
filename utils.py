import numpy as np
import math
import heapq


infinity = 9.0e50
np.random.seed(100)


def get_random_seed():
    seed = np.random.randint(10e4)
    return seed


class RndGen:
    def get(self):
        return np.random.random()

class UnifGen(RndGen):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def get(self):
        return np.random.uniform(self.a, self.b)


class ExpGen(RndGen):
    def __init__(self, rate):
        self.rate = rate

    def get(self):
        rng = np.random.RandomState(get_random_seed())
        return rng.exponential(self.rate)


class TriGen(RndGen):
    def __init__(self, low, high, mode):
        self.low = low
        self.high = high
        self.mode = mode

    def get(self):
        # return random.triangular(self.low, self.high, self.mode)
        return np.random.triangular(self.low, self.mode, self.high)


class MyPQ:
    def __init__(self):
        self.heap = []

    def qsize(self):
        return len(self.heap)

    def empty(self):
        return len(self.heap) == 0

    def put(self, obj):
        heapq.heappush(self.heap, obj)

    def get(self):
        return heapq.heappop(self.heap)

    def peep(self):
        return self.heap[0]

class TimeAverage:
    def __init__(self, t, v=0):
        self.reset(t, v)

    def reset(self, t, v=0):
        self.initT = t
        self.prevT = t
        self.prevV = v
        self.sum = 0.0

    def stateChange(self, t, v):
        self.sum += self.prevV*(t - self.prevT)
        self.prevT = t
        self.prevV = v

    def timeAvg(self, t):
        self.stateChange(t, self.prevV)  # maintain current state
        dt = t - self.initT
        if dt == 0.0:  return 0.0
        return self.sum / dt


class Accumulator:
    def __init__(self):
        self.reset()

    def reset(self):
        self.n = 0
        self.X = 0.0
        self.XX = 0.0
        self.min = infinity
        self.max = -infinity

    def append(self, x):
        self.n += 1
        self.X += x
        self.XX += x*x
        if x < self.min:
            self.min = x
        if x > self.max:
            self.max = x

    def avg(self):
        if self.n == 0: return 0.0
        return self.X / self.n

    def std(self):
        if self.n == 0: return 0.0
        var = self.XX / self.n - self.avg()**2
        if var<0: return 0
        return math.sqrt(var)

    def getStr(self):
        return "%f %f" % (self.avg(), self.std())


def rotate(dx, dy, x, y, ox=0, oy=0):
    d = math.sqrt(dx * dx + dy * dy)
    c = dx / d
    s = dy / d
    xp = c*x - s*y + ox
    yp = s*x + c*y + oy
    return xp, yp


