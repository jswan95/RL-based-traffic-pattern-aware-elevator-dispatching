from DES import *
from utils import *


class Vertex:
    def __init__(self, name, x=0, y=0, type=None):
        self.name = name
        self.x = x
        self.y = y
        self.type = type

        self.outEdges = []
        self.inEdges = []
        self.inVertices = []
        self.outVertices = []

    def __lt__(self, other):
        return True

    def getPos(self):
        return self.x, self.y

    def findOutEdge(self, ev):
        for e in self.outEdges:
            if e.ev == ev:
                return e
        return None

    def findInEdge(self, sv):
        for e in self.inEdges:
            if e.sv == sv:
                return e
        return None

    def distTo(self, ev):
        return math.sqrt((ev.x-self.x)**2 + (ev.y-self.y)**2)

    def stepTo(self, ev, t=0.0):
        if t == 0.0:
            return self.getPos()
        t1 = 1 - t
        x = t1*self.x + t*ev.x
        y = t1*self.y + t*ev.y
        return x, y


class Edge:
    def __init__(self, sv, ev, c=None, type=None):
        self.sv = sv
        self.ev = ev
        self.type = type
        sv.outEdges.append(self)
        sv.outVertices.append(ev)
        ev.inEdges.append(self)
        ev.inVertices.append(sv)

        self.length = sv.distTo(ev)
        if c is None:
            c = self.length
        self.cost = c

    def name(self):
        return self.sv.name+'-'+self.ev.name

    def getPos(self, t=0.0):
        return self.sv.stepTo(self.ev)

    def getMid(self):
        return self.getPos(0.5)


class VertexModel(Vertex, AModel):
    def __init__(self, name, x=0, y=0, type=None):
        Vertex.__init__(self, name, x, y, type)
        self.vehicle = None
        self.vehQ = []  # queue for waiting vehicles
        self.jobQ = []  # queue for jobs to be picked up

    def free(self):
        vvv = self.vehicle
        self.vehicle = None
        while len(self.vehQ) > 0:
            veh = self.vehQ.pop(0)
            if veh.location in self.inVertices:
                self.instantEvtMsg(veh, 'resume', param=self)
                return

    def isFree(self):
        return self.vehicle is None

    def isReserved(self, veh):
        return self.vehicle == veh # check reservation

    def wanted(self):
        return len(self.vehQ) > 0

    def occupy(self, vehicle):
        assert self.vehicle==None
        self.vehicle = vehicle
        vehicle.occupy_list.append(self)

    # def cancel_reservation(self, vehicle):
    #     if vehicle in self.reservedBy :
    #         index = self.reservedBy.index(vehicle)
    #         del self.reservedBy[index]
    #     if len(self.vehQ) > 0 and len(self.reservedBy) > 0 and self.vehQ[0] == self.reservedBy[0] :
    #         self.vehQ.pop(0)
    #         self.instantEvtMsg(self.reservedBy[0], 'resume', param=self)

    def waitQ(self, vehicle):
        if vehicle not in self.vehQ:
            self.vehQ.append(vehicle)
            vehicle.addTrace(f"waitQ {self.name}")

    def findPushEdge(self):
        for e in self.outEdges:
            if e.ev.isFree():
                return e
        # no free edge, try push ahead
        for e in self.outEdges:
            if e.ev.vehicle.locationNext == None:
                e.ev.vehicle.goPush()  # try push ahead
            if e.ev.isFree():
                return e
            else:
                e.ev.waitQ(self.vehicle)
        return None

GV_factor = 50
GV_linear = 2 * GV_factor  # m/s
GV_curve = 0.45* GV_factor
GV_h0f = 0.3 * GV_factor


class EdgeModel(Edge):
    def __init__(self, sv, ev, c, type):
        Edge.__init__(self, sv, ev, c, type)
        self.h0f = GV_h0f
        if type == 'L':
            self.vmax = GV_linear
        else:
            self.vmax = GV_curve
        if c is None:
            self.cost = self.length / self.vmax


class Graph:
    def __init__(self, aModel=False):
        self.Vmap = {}
        self.Vlist = []
        self.Elist = []
        self.aModel = aModel

    def addVertex(self, name="", x=0, y=0, type=None):
        if self.aModel:
            v = VertexModel(name, x, y, type)
        else:
            v = Vertex(name, x, y, type)
        if name != "" or name != ".":
            self.Vmap[name] = v
        self.Vlist.append(v)
        return v

    @staticmethod
    def modifyPos(type, sv, ev, mv, i):
        if type is None or type == 'L':
            return
        dx = ev.x - sv.x
        dy = ev.y - sv.y
        d = math.sqrt(dx*dx + dy*dy)
        if type == 'C':
            d /= 4
        elif type == 'D':
            d /= -4
        else:  # type == 'S'
            d /= 10
            sign = (dx * dy) * (i - 0.5)
            if sign > 0:
                d = -d
        mx, my = 0, -d
        mv.x, mv.y = rotate(dx, dy, mx, my, mv.x, mv.y)

    def addEdge(self, sv, ev, c=None, type=None, directed=True, nsplit=0):
        vlist = [sv]
        if nsplit > 0:
            d = sv.distTo(ev)
            for i in range(nsplit):
                t = (i+1)/(nsplit+1)
                x,y = sv.stepTo(ev, t)
                iname = sv.name+'_'+str(i) + "_" + ev.name
                # iname = "."
                mv = self.addVertex(iname, x, y, "I")
                self.modifyPos(type, sv, ev, mv, i)
                vlist.append(mv)
        vlist.append(ev)
        n = len(vlist)
        for i in range(1, n):
            av = vlist[i-1]
            bv = vlist[i]
            if c is not None:  # divide edge cost
                c /= (n-1)
            if self.aModel:
                e = EdgeModel(av, bv, c, type)
            else:
                e = Edge(av, bv, c, type)
            self.Elist.append(e)
        if not directed:  # add reverse edge
            self.addEdge(ev, sv, c, directed=True, nsplit=nsplit)
        return e

    def getVertex(self, name):
        try:
            v = self.Vmap[name]
        except KeyError:
            v = self.addVertex(name)
        return v

    def readGraph(self, vFileName, eFileName, split=False):
        vFile = open(vFileName, 'r')
        eFile = open(eFileName, 'r')

        for line in vFile:
            tk = line.split()
            if len(tk) > 3:
                type = tk[3]
            else:
                type = None
            v = self.addVertex(tk[0], float(tk[1])*GV_factor, float(tk[2])*GV_factor, type)

        for line in eFile:
            tk = line.split()
            sv = self.getVertex(tk[0])
            ev = self.getVertex(tk[1])
            if len(tk) > 2:
                if tk[2].isdecimal():
                    c = float(tk[2])
                    type = None
                else:
                    c = None
                    type = tk[2]
            if split or type != 'L':
                nsplit = int(tk[3])
            else:
                nsplit = 0
            self.addEdge(sv, ev, c, type, nsplit=nsplit)

    def reset(self):
        for v in self.Vlist:
            v.dist = infinity
            v.flag = False
            v.prev = None

    def sanityCheck(self, sv, dv, route):
        assert sv == route[-1]
        assert dv == route[0]
        pv = dv
        # each vertex should appear only once
        self.reset()
        for v in route:
            assert v.flag == False
            v.flag = True
            assert pv.distTo(v) < 100
            pv = v

    def vlist2elist(self, vlist):
        n = len(vlist)
        elist = []
        for i in range(1,n):
            sv = vlist[i-1]
            ev = vlist[i]
            e = sv.findOutEdge(ev)
            if e is not None:
                elist.append(e)
        return elist

    def backtrack(self, sv, dv, route):
        # sv, dv: source & destination Vertex
        route.append(dv)
        if sv != dv:
            self.backtrack(sv, dv.prev, route)

    def Dijkstra(self, sv, dv=None):
        # sName, eName: string (name of source & destination Vertex)
        # sv, ev = graph.getVertex(sName), graph.getVertex(dName)
        # print (sv.name)
        self.reset()
        sv.dist = 0
        pq = MyPQ()  # PriorityQueue()
        pq.put((sv.dist,sv))
        while not pq.empty():
            v = pq.get()[1]
            if v == dv: break  # desitination reached
            if v.flag: continue  # v is already processed
            v.flag = True
            # print (v.dist)

            for e in v.outEdges:
                w = e.ev
                temp = v.dist + e.cost
                if w.dist > temp:
                    w.dist = temp
                    w.prev = v
                    pq.put((w.dist,w))

        if dv is not None:
            route = []
            self.backtrack(sv, dv, route) # reversed sequence of vertices
            # self.sanityCheck(sv, dv, route)
            route.pop()  # remove the last, which is equal to sv
            return route, dv.dist

    def getDistMap(self):
        dmap = {}
        for ev in self.Vlist:
            dmap[ev] = ev.dist
        return dmap

    def DijkstraAllPair(self):
        print ("Start: Computing reference distance map")
        self.Dmat = {}
        for sv in self.Vlist:
            self.Dijkstra(sv)
            dm = self.getDistMap()
            self.Dmat[sv] = dm
        print ("End: Computing reference distance map")

    # # Bellman-Ford alg. using v.dist and v.prev
    # def BellmanFord(self, sv):
    #     self.reset()
    #     sv.dist = 0
    #     for k in range(len(self.Vlist)):
    #         for e in self.Elist:
    #             newDist = e.sv.dist + e.cost
    #             if newDist < e.ev.dist:
    #                 e.ev.dist = newDist
    #                 e.ev.prev = e.sv
    #         # print("k = ", k, "dist = ", vt.dist)
    #
    #     # check negative cycle
    #     for e in self.Elist:
    #         if e.sv.dist + e.cost < e.ev.dist:
    #             print("Negative cycle found.")
    #             return False
    #     # backtrack : use Backtrack(sv, ev) function above
    #     return True


    # # for a sparse graph, repeated use of Dijkstra is more efficient than FLoyd-Warshall
    # def FloydWarshall (self):
    #     NV = len(self.Vmap)
    #     NVxNV = (NV, NV)
    #     rNV = range(NV)
    #     dist = np.full(NVxNV, infinite)
    #     prev = np.full(NVxNV, -1, dtype='int')
    #
    #     # dist from vertex to itself is set to 0
    #     # initialize the path matrix
    #     for i in rNV:
    #         dist[i][i] = 0
    #         prev[i][i] = i
    #
    #     for e in self.Elist :
    #         i = e.sv.id
    #         j = e.ev.id
    #         if i >= NV or j >= NV: continue
    #         dist[i][j] = e.cost
    #         prev[i][j] = i
    #
    #     # Floyd-Warshall main loop
    #     for k in rNV:
    #         # print('k = ', k)
    #         for i in rNV:
    #             if dist[i][k] == infinite: continue
    #             for j in rNV:
    #                 if dist[k][j] == infinite: continue
    #                 newdist = dist[i][k] + dist[k][j]
    #                 if newdist < dist[i][j]:
    #                     dist[i][j] = newdist
    #                     prev[i][j] = prev[k][j]
    #
    #     # display shortest paths
    #     def backtrackFW(i, j):
    #         if dist[i][j] == infinite:
    #             return " no path to "
    #         if prev[i][j] == i:
    #             return " "
    #         else:
    #             pij = prev[i][j]
    #             pv = self.V[pij]
    #             return backtrackFW(i, pij) + pv.name + backtrackFW(pij, j)


    def print(self):
        print ("Vertex list")
        for v in self.Vlist:
            print(v.name, v.x, v.y)

        print ("Vertex name map")
        for k, v in self.Vmap.items():
            print (k, v.name)

        print ("Edge list")
        for e in self.Elist:
            print (e.sv.name, e.ev.name, e.cost)

if __name__ == "__main__":
    g = Graph(aModel=True)
    g.readGraph("Small_V_8bay.txt","Small_E_8bay.txt")
    g.DijkstraAllPair()
    for sv in g.Vlist:
        for ev in g.Vlist:
            print (sv.name, ev.name, g.Dmat[sv][ev])
    # print(g.Vmap)