#
#   Weather update server
#   Binds PUB socket to tcp://*:5556
#   Publishes random weather updates
#

import time
from ConnectMQ import *
import random


def queueMsg(name):
    if random.random() < 0.5:
        msg = "enqueue " + name
    else:
        msg = "dequeue " + name
    return msg

def publish_test1(socket):
    mid = 1
    while True:
        obj_id = random.randrange(0,10)
        r = random.random()
        if r < 0.3:  # change color
            color = random.randrange(0,12)
            # msg = "color P%d %d" % (obj_id, color)
            msg = "color P%d %d" % (obj_id, color)
        elif r < 0.7:  # move or animation
            x = obj_id*100 - 35
            y = random.uniform(0, 300)
            if obj_id >= 3: # move ellipse
                msg = "move P%d %d %d" % (obj_id, x, y)
            else:  # animation
                t = 500
                msg = "anim P%d %d %d %d" % (obj_id, x, y, t)
        elif r < 0.8:  # group component color
            port_id = random.randrange(0,5)
            color = random.randrange(0,6)
            if port_id == 0:
                msg = queueMsg("CVD%d.IO0" % obj_id)
            elif port_id > 3:
                msg = "color CVD%d.Equip %d" % (obj_id, color)
            else:
                msg = "color CVD%d.IO%d %d" % (obj_id, port_id, color)
        elif r < 0.83:  # queue
            msg = queueMsg('Queue')
        elif r < 0.85:  # change text
            i = random.randrange(0,4)
            j = random.randrange(0,6)
            msg = "text Job@21 %d/%d" % (i, j)
            # msg = "text M21 %d/%d" % (i, j)
        else:  # ASRS command
            i = random.randrange(0, 5)
            j = random.randrange(0, 100)
            color = random.randrange(0,6)
            # 1D array object : name[%d]
            # 2D array object : name[%d,%d]
            msg = "color ASRS[%d,%d] %d" % (i, j, color)

        MQ_sim_send_msg(msg)
        print(mid, " : ", msg)
        mid += 1

        # time.sleep(0.1)
        time.sleep(0.002)


# main program
if __name__ == '__main__':
    pubSocket = MQ_bindFromSimulation(sync = False)
    publish_test1(pubSocket)
