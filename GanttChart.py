# Importing the matplotlb.pyplot
import matplotlib.pyplot as plt
import numpy as np

class GanttChart:
    def __init__(self):
        self.fig, self.ax = plt.subplots()
        self.tmin = 0
        self.tmax = 0
        self.row = []
        self.dy = 10
        self.ytick = []
        self.yname = []

    def addRow(self, yname):
        n = len(yname)
        for i in range(n):
            self.row.append([])
            self.ytick.append(self.dy*i)
            self.yname.append("")
            self.ytick.append(self.dy*(i+0.5))
            self.yname.append(yname[i])

    def addBracket(self, r, trng, col):
        self.row[r].append((trng,col))
        x = (trng[0], trng[1]-trng[0])
        y = ((r+0.1)*self.dy, self.dy*0.8)
        self.ax.broken_barh([x], y, facecolors=(col))
        if trng[0] < self.tmin:
            self.tmin = trng[0]
        if trng[1] > self.tmax:
            self.tmax = trng[1]

    def finalize(self, xlabel, ylabel):
        nrow = len(self.row)
        self.ax.set_ylim(0, self.dy*nrow)
        self.ax.set_xlim(self.tmin, self.tmax)

        # Setting labels for x-axis and y-axis
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)

        # Setting ticks on y-axis
        self.ax.set_yticks(self.ytick)
        self.ax.set_yticklabels(self.yname)

        # Setting graph attribute
        self.ax.grid(True)

    def example(self):
        np.random.seed(100)
        self.addRow(['IP-2', 'IP-1', 'Loader', 'Camera'])

        # camera move
        shot = 1
        load = 2
        nFoV = 10
        st = 0
        sumTravel = 0
        sumIP = [0, 0]
        p = [0, 0]

        # marker read
        # shot marker-1 at LL
        et = st + shot
        self.addBracket(3, (st, et), 'yellow')
        st = et + 0.1
        # process marker-1
        pt = et
        ipt = 2.0
        self.addBracket(1, (pt, pt + ipt), 'yellow')
        # travel to UR
        tt = 5.0
        et = st + tt
        sumTravel += tt
        self.addBracket(3, (st, et), 'green')
        st = et+0.1
        # shot marker-2 at UR
        et = st + shot
        self.addBracket(3, (st, et), 'yellow')
        st = et + 0.1
        # process marker-2
        pt = et
        self.addBracket(1, (pt, pt + ipt), 'yellow')

        st = pt+ipt
        ipts = np.random.uniform(3, 12, nFoV)
        ipts = sorted(ipts, reverse=True)

        for i in range(nFoV):
            tt = np.random.uniform(0.5, 5) * 1.05
            et = st + tt
            sumTravel += tt
            self.addBracket(3, (st,et), 'orange')
            st = et+0.1
            et = st+shot
            self.addBracket(3, (st, et), 'blue')
            st = et+0.1

            ipt = ipts[i]
            j = (i+0) % 2
            sumIP[j] += ipt
            pt = st
            if pt<p[j]:
                pt = p[j]
            ct = pt + ipt
            p[j] = ct + 0.1
            self.addBracket(j, (pt, ct), 'red')

        # travel back to LL
        tt = 4.0
        et = st + tt
        sumTravel += tt
        self.addBracket(3, (st, et), 'green')
        ct = max(ct,et)

        # load next PCB
        et = st + 7.0
        self.addBracket(2, (st, et), 'magenta')

        self.finalize('time (ms)', 'Processor')
        print ("이동시간 : ", sumTravel)
        print ("촬영시간 : ", shot*10)
        print ("검사시간 : ", sum(sumIP))
        print ("  IP-1 처리시간 : ", sumIP[0])
        print ("  IP-2 처리시간 : ", sumIP[1])
        print ("Cycle Time : ", ct)
        plt.show()
        # plt.savefig("gantt1.png")


class TravelTime:
    def __init__(self, n, d, t_0F=1):
        self.v_F = 100
        self.t_0F = t_0F
        np.random.seed(300)
        r = np.random.uniform(0, d, n)
        r = np.insert(r, 0, 0)
        r = np.append(r, d)
        r.sort()
        m = len(r)
        self.d = r[1:] - r[:m-1]
        # print(self.d)
        print('Total time = ', self.totalTime())

    def segTime(self, d):
        if d < self.v_F*self.t_0F:
            t = 2*np.sqrt(self.t_0F*d / self.v_F)
        else:
            t = d / self.v_F + self.t_0F
        return t

    def totalTime(self):
        t = 0
        for d in self.d:
            t += self.segTime(d)
        return t

if __name__ == "__main__":
    # tt = TravelTime(50, 567, t_0F=0.1)
    g = GanttChart()
    g.example()


# import plotly.express as px
# import pandas as pd
#
# df = pd.DataFrame([
#     dict(Task="Job A", Start='2009-01-01', Finish='2009-02-28', Resource="Alex"),
#     dict(Task="Job B", Start='2009-03-05', Finish='2009-04-15', Resource="Alex"),
#     dict(Task="Job C", Start='2009-02-20', Finish='2009-05-30', Resource="Max")
# ])
#
# fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Resource")
# fig.update_yaxes(autorange="reversed")
# fig.show()
#
#
# import plotly.figure_factory as ff
#
# df = [dict(Task="Job-1", Start='2017-01-01', Finish='2017-02-02', Resource='Complete'),
#       dict(Task="Job-1", Start='2017-02-15', Finish='2017-03-15', Resource='Incomplete'),
#       dict(Task="Job-2", Start='2017-01-17', Finish='2017-02-17', Resource='Not Started'),
#       dict(Task="Job-2", Start='2017-01-17', Finish='2017-02-17', Resource='Complete'),
#       dict(Task="Job-3", Start='2017-03-10', Finish='2017-03-20', Resource='Not Started'),
#       dict(Task="Job-3", Start='2017-04-01', Finish='2017-04-20', Resource='Not Started'),
#       dict(Task="Job-3", Start='2017-05-18', Finish='2017-06-18', Resource='Not Started'),
#       dict(Task="Job-4", Start='2017-01-14', Finish='2017-03-14', Resource='Complete')]
#
# colors = {'Not Started': 'rgb(220, 0, 0)',
#           'Incomplete': (1, 0.9, 0.16),
#           'Complete': 'rgb(0, 255, 100)'}
#
# fig = ff.create_gantt(df, colors=colors, index_col='Resource', show_colorbar=True,
#                       group_tasks=True)
# fig.show()