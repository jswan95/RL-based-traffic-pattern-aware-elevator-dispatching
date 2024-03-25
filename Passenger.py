from Graph import *
from utils import *
import random


class Passenger(AModel):
    pid = 0

    @staticmethod
    def get_pid():
        Passenger.pid += 1
        return Passenger.pid

    def __init__(self, ff, tf, gen_time, id_=None):
        super().__init__()
        self.from_floor = ff  # from floor
        self.to_floor = tf  # to floor
        self.gen_at = gen_time  # passenger's generation time
        self.board_at = None  # passenger's boarding time
        self.leave_at = None  # passenger's leaving time
        if self.from_floor.floor_id < self.to_floor.floor_id:
            self.direction = 'up'  # passenger want to go up
        else:
            self.direction = 'down'  # passenger want to go down
        pid = Passenger.get_pid()
        if id_ is None:
            self.id = pid   # passenger's id
        else:
            self.id = id

    def get_waiting_time(self):  # calculate waiting time
        return self.board_at - self.gen_at

    def get_journey_time(self):  # calculate journey time
        return self.leave_at - self.board_at

    def get_trip_time(self):  # calculate trip time
        return self.leave_at - self.gen_at

    def processEvtMsg(self, e):
        if e.msg == 'boarded':
            car, time_to_revise = e.param
            self.board_at = car.con.Tnow() - time_to_revise  # to calculate real board at
        elif e.msg == 'get off':
            car, time_to_revise = e.param
            # to calculate real leave at: the first passenger starts getting off
            self.leave_at = car.con.Tnow() - time_to_revise
            self.instantEvtMsg(car.con, 'passenger leave', param=self)  # need calculate passenger stat


class PassengerGenerator(AModel):
    def __init__(self, con, emq, ar, prior_ar, population, traffic_type):
        self.con = con
        self.emq = emq
        self.period = None
        self.population = population
        self.ar = ar
        self.prior_ar = prior_ar
        self.type = traffic_type  # outgoing, interFloor, incoming
        self.iat = ExpGen(300)  # just initialization
        self.schedule_next_arrival()

    def get_prior_ar(self):
        traffic_pattern = self.con.traffic_pattern
        if traffic_pattern == 'AllInOne':
            self.period = 12 * 3600  # period is 12 hours for 'AllInOne' pattern
        else:
            self.period = 3 * 3600  # period is 3 hours for other patterns

        time_idx = int((self.con.Tnow() % self.period) // (15 * 60))  # which 15 minute interval
        time_shift = self.con.Tnow() % self.period % (15 * 60)  # how many seconds passed during the 15 minute interval
        next_time_idx = time_idx + 1
        if next_time_idx == len(self.prior_ar):
            next_time_idx = 0

        ar = self.prior_ar[time_idx] + (time_shift * (self.prior_ar[next_time_idx] - self.prior_ar[time_idx]) / (15 * 60))
        return 300 / (ar * self.population / 100)  # inter-arrival time

    def get_rate(self):
        traffic_pattern = self.con.traffic_pattern
        if traffic_pattern == 'AllInOne':
            self.period = 12 * 3600  # period is 12 hours for 'AllInOne' pattern
        else:
            self.period = 3 * 3600  # period is 3 hours for other patterns

        time_idx = int((self.con.Tnow() % self.period) // (15 * 60))  # which 15 minute interval
        time_shift = self.con.Tnow() % self.period % (15 * 60)  # how many seconds passed during the 15-minute interval
        next_time_idx = time_idx + 1
        if next_time_idx == len(self.ar):
            next_time_idx = 0

        ar = self.ar[time_idx] + (time_shift * (self.ar[next_time_idx] - self.ar[time_idx]) / (15 * 60))
        if self.con.args.d != 0:
            if traffic_pattern == 'AllInOne':
                t = self.con.Tnow() % self.period
                if t <= 3 * 3600:  # up peak
                    if self.type == 'in coming':
                        ar = (self.con.args.d + 1) * ar
                elif 4.5 * 3600 < t <= 6 * 3600:  # lunch peak, first half
                    if self.type == 'in coming':
                        ar = (self.con.args.d + 1) * ar
                elif 6 * 3600 < t <= 7.5 * 3600:  # lunch peak, second half
                    if self.type == 'out going':
                        ar = (self.con.args.d + 1) * ar
                elif 9 * 3600 < t <= self.period:  # down peak
                    if self.type == 'out going':
                        ar = (self.con.args.d + 1) * ar
        return 300 / (ar * self.population / 100)  # inter-arrival time

    def schedule_next_arrival(self):
        self.iat.rate = self.get_rate()  # arrival rate
        time_to_go = self.iat.get()  # time to go until next arrival
        self.emq.scheduleEvtMsg4(time_to_go, self, self, "next arrival")  # schedule next arrival

    def get_from_to_floor(self):
        random.seed(get_random_seed())
        from_floor_id, to_floor_id = random.sample(range(2, self.con.num_floor + 1), 2)
        if self.type == 'in coming':
            from_floor_id = 1
        elif self.type == 'out going':
            to_floor_id = 1
        assert from_floor_id != to_floor_id
        return self.con.floor_map[from_floor_id], self.con.floor_map[to_floor_id]  # return floor from, floor to

    def processEvtMsg(self, e):
        if e.msg == "next arrival":
            self.schedule_next_arrival()
            from_floor, to_floor = self.get_from_to_floor()
            passenger = Passenger(from_floor, to_floor, e.time)
            if passenger.direction == 'down':
                msg_to = passenger.from_floor.down_queue  # send message to down queue of from floor
            else:
                msg_to = passenger.from_floor.up_queue  # send message to up queue of from floor
            passenger.instantEvtMsg(msg_to, 'passenger arrive', param=passenger)
