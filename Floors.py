from Graph import *
from StateDef import *


class Floor:
    def __init__(self, floor_id, con):
        self.floor_id = floor_id
        self.con = con
        self.up_floor = None  # up floor of this floor
        self.down_floor = None  # down floor of this floor
        self.up_queue = FloorQueue(self.floor_id, 'up', self.con)  # queue for passenger going up
        self.down_queue = FloorQueue(self.floor_id, 'down', self.con)  # queue for passenger going down
        self.prev_from = 0.
        self.real_fr = 0.
        self.prev_to = 0.
        self.real_tr = 0.
        self.from_count = []
        self.to_count = []
        self.count_interval = 5 * 60
        # self.request_count_interval = 5 * 60  # not used yet
        # self.prev_requests = {'down': [], 'up': []}  # not used yet

    def get_real_rate(self):
        t_now = self.con.Tnow()
        for i in self.from_count:
            if i + self.count_interval < t_now:
                self.from_count.pop()
        for j in self.to_count:
            if j + self.count_interval < t_now:
                self.to_count.pop()
        # print(len(self.from_count) / self.count_interval, len(self.to_count) / self.count_interval)
        return len(self.from_count) / self.count_interval, len(self.to_count) / self.count_interval

    # def updatePreviousRequests(self, direction):  # not used yet
    #     Tnow = self.con.Tnow()
    #     self.previousRequests[direction].append(Tnow)
    #     c1 = True
    #     c2 = True
    #     while c1 and c2:
    #         for i in ['up', 'down']:
    #             if self.previousRequests[i] and self.previousRequests[i][0] + self.requestCountInterval < Tnow:
    #                 self.previousRequests[i].pop()
    #             else:
    #                 if i == 'up':
    #                     c1 = False
    #                 else:
    #                     c2 = False


class FloorQueue(AModel):
    def __init__(self, floor_id, queue_type, con):
        self.floor_id = floor_id
        self.con = con
        self.logger = self.con.logger
        self.type = queue_type
        self.type_id = int(queue_type == 'up')  # up: 1, down:0
        self.queue = []
        self.press_time = 0.  # not used yet
        self.if_car_stopped = 0.  # if there is car stopping at this floor

    # def getSquaredWaitingTimeSum(self):  # not used yet
    #     swtSum = 0.
    #     Tnow = self.con.Tnow()
    #     for p in self.queue:
    #         swtSum += (p.genAt - Tnow) ** 2
    #
    #     return swtSum

    def passenger_arrive(self, passenger):
        assert self.floor_id == passenger.from_floor.floor_id
        passenger.from_floor.from_count.append(passenger.gen_at)
        passenger.to_floor.to_count.append(passenger.gen_at)
        # passenger.from_floor.real_fr = self.con.args.c * passenger.from_floor.real_fr + \
        #                                (1 - self.con.args.c) * 1 / (self.con.Tnow() - passenger.from_floor.prev_from)
        # passenger.from_floor.prev_from = self.con.Tnow()
        # passenger.to_floor.real_tr = self.con.args.c * passenger.to_floor.real_tr + \
        #                              (1 - self.con.args.c) * 1 / (self.con.Tnow() - passenger.to_floor.prev_to)
        # passenger.to_floor.prev_to = self.con.Tnow()
        self.queue.append(passenger)  # add new passenger into the queue
        self.con.send_mon_qsize(self)  # send to monitor
        if len(self.queue) == 1:  # first passenger
            # self.con.floorMap[self.floorID].updatePreviousRequests(passenger.direction)  # not used yet

            # send request to elevator controller to call a car
            self.instantEvtMsg(self.con, passenger.direction, param=self)

    def passenger_board(self, param):
        car, board_time = param
        if_remain = False  # if there are still passengers not boarded
        assert car.cur_num < car.capacity
        self.logger.debug(f'Floor {self.floor_id} passenger starting board into {car.id}')
        self.con.request_floor[self.type_id][self.floor_id] = 0
        if car.cur_num == 0:
            if self.type == 'down':
                # if there is no passenger in the car, car's direction will be passengers' direction
                car.set_state(CarState.MOVING_DOWN)
            else:
                car.set_state(CarState.MOVING_UP)

        boarded_queue = []
        if len(self.queue) + car.cur_num <= car.capacity:  # all can board
            boarded_queue = self.queue
            self.queue = []
            self.logger.debug(f'Floor {self.floor_id} passenger all boarded into car {car.id}')
            assert len(boarded_queue) != 0
            # self.con.send_mon_car_id(self)
        else:
            num_board = car.capacity - car.cur_num  # partially board
            for i in range(num_board):
                boarded_queue.append(self.queue.pop(0))
            self.logger.debug(f'Floor {self.floor_id} passenger partially boarded into car {car.id}')
            if_remain = True
        self.instantEvtMsg(car, 'boarded', param=(boarded_queue, board_time))
        assert self.if_car_stopped == car.id
        self.if_car_stopped = 0  # now no car stopped this floor
        self.con.send_mon_car_id(self)
        if if_remain:
            car.instantEvtMsg(self.con, self.type, param=self)  # again send request to elevator controller
        self.con.send_mon_qsize(self)

    def processEvtMsg(self, e):
        if e.msg == 'passenger arrive':
            self.con.reward += self.con.get_partial_reward()  # passenger arrival event
            self.passenger_arrive(e.param)
        elif e.msg == 'passenger board':
            self.passenger_board(e.param)
