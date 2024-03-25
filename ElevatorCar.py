from scipy.stats import truncnorm
from Graph import *
from StateDef import *
import time


class ElevatorCar(AModel):
    def __init__(self, id_, num_floor, stop_pos, capacity, con):
        super().__init__()
        self.id = id_  # id of the car, integer
        self.num_floor = num_floor
        self.stop_pos = stop_pos
        self.con = con  # controller
        self.logger = self.con.logger
        self.capacity = capacity
        self.decision_point = False
        self.cur_num = 0  # current number of people in car
        self.prev_floor = None
        self.next_floor = None
        self.state = CarState.IDLE
        self.change_direction = False
        self.door_time = 1.
        self.passenger_in_car = {}
        self.initial_passenger_in_car()
        self.initial_floor()
        self.stop_at = np.zeros((3, self.num_floor + 1))  # 0:down, 1:up, 2: getOff (only 2 used here)
        self.stop_at_prev_floor = True
        self.stop_at_next_floor = False
        self.get_on_at_next_floor = -1  # -1: no get on, 0: down get on, 1: up get on
        self.get_off_at_next_floor = False
        self.util = TimeAverage(self.con.Tnow())  # vehicle utilization
        self.initial_travel_time()  # initialize travel time between floors
        # self.resetPassengerCount()  # not used yet

    def get_current_location(self):
        location_vector = np.zeros((2, self.num_floor))

        if self.next_floor is not None:  # next floor is already scheduled
            location_id = self.next_floor.floor_id
        else:
            location_id = self.prev_floor.floor_id

        if self.state == CarState.MOVING_DOWN:
            location_vector[0, location_id - 1] = 1
        elif self.state == CarState.MOVING_UP:
            location_vector[1, location_id - 1] = 1
        else:
            assert self.state == CarState.IDLE
            location_vector[:, location_id - 1] = 1

        return location_vector

    def get_passenger_in_car(self):
        passenger_in_car = np.zeros(self.num_floor)
        for i in range(self.num_floor):
            if self.passenger_in_car[i + 1]:
                if self.con.args.destination_control:
                    # num of passenger will get off at floor i + 1
                    passenger_in_car[i] = len(self.passenger_in_car[i + 1])
                else:
                    # if there is passenger getting off at floor i + 1
                    passenger_in_car[i] = 1
        return passenger_in_car

    def get_self_info(self):
        # Get the current location of the car
        location_vector = self.get_current_location()

        # Get the number of passengers getting off at each floor
        passenger_in_car = self.get_passenger_in_car()  # num of passengers gonna get off at each floor
        self_info = np.concatenate([location_vector.transpose(), passenger_in_car.reshape(-1, 1)], axis=1)
        return self_info

    def initial_passenger_in_car(self):
        for i in range(1, 1 + self.num_floor):
            self.passenger_in_car[i] = []

    def initial_travel_time(self, h=3, v_f=3):
        self.t00 = 2 * np.sqrt(2) * h / v_f
        self.t0f = 2 * h / v_f
        self.tf0 = 2 * h / v_f
        self.tff = h / v_f

    def initial_floor(self):  # initialize the position of cars
        self.set_location(self.con.floor_map[1])
        self.set_location_anim(self.con.floor_map[1], 0)

    def update_after_boarded(self, boarded_list, board_time):
        # update elevator's attribute after boarding:stop_at, passenger_in_car, cur_num
        for i in range(len(boarded_list)):
            passenger = boarded_list[i]
            if i == len(boarded_list) - 1:
                time_to_revise = 0  # no need to revise for the last passenger
            else:
                time_to_revise = board_time[i + 1:].sum()  # to calculate the real board time
            self.instantEvtMsg(passenger, 'boarded', param=(self, time_to_revise))
            to_floor_id = passenger.to_floor.floor_id
            self.passenger_in_car[to_floor_id].append(passenger)  # add passenger to the car
            self.stop_at[2][to_floor_id] = to_floor_id  # the car should stop at to_floor_id
        self.cur_num += len(boarded_list)  # update current number of passenger
        assert self.cur_num <= self.capacity
        # self.passengerCount[1, self.prev_floor.floor_id - 1] = len(boardedList)  # not used yet

    def passenger_get_off(self, get_off_time):
        current_floor_id = self.prev_floor.floor_id
        assert self.stop_at[2][current_floor_id] != 0

        get_off_list = self.passenger_in_car[current_floor_id]
        for i in range(len(get_off_list)):
            passenger = get_off_list[i]
            # we take the time that the car arrives at the to floor as the leave at of the passengers
            time_to_revise = get_off_time[:].sum()
            self.instantEvtMsg(passenger, 'get off', param=(self, time_to_revise))

        # update after getting off
        self.stop_at[2][current_floor_id] = 0  # no need to stop at this floor now
        self.logger.debug(f'passenger get off from Car{self.id} at floor {current_floor_id}')
        self.cur_num -= len(get_off_list)  # update the current number of passenger
        self.passenger_in_car[current_floor_id] = []

    def get_board_time(self):
        assert self.get_on_at_next_floor != -1  # make sure there are passenger boarding
        if self.get_on_at_next_floor == 0:  # 0: down queue, 1: up queue, -1: no get on
            board_from = self.prev_floor.down_queue
        else:
            board_from = self.prev_floor.up_queue

        assert board_from is not None
        assert len(board_from.queue) > 0
        assert self.cur_num < self.capacity
        board_num = min(len(board_from.queue), self.capacity - self.cur_num)  # how many passengers can board
        board_time = truncnorm.rvs(0.6, 6, loc=1, scale=1, size=board_num, random_state=get_random_seed())
        return board_from, board_time

    def if_get_off(self, floor):
        return self.stop_at[2, floor.floor_id] != 0  # if passenger want to get off at floor

    def if_get_on(self, floor):
        passenger_get_on = -1  # -1: no get on, 0: down get on, 1: up get on
        floor_id = floor.floor_id
        con = self.con
        # how many passengers can get on
        available_capacity = self.capacity - self.cur_num + len(self.passenger_in_car[floor_id])  
        if available_capacity > 0 and con.request_floor[:, floor_id].sum():  # this floor has request
            if self.state == CarState.MOVING_DOWN:
                # down request down queue + no car stopped
                if con.request_floor[0, floor_id] and floor.down_queue.if_car_stopped == 0:
                    passenger_get_on = 0  # down will get on
                    floor.down_queue.if_car_stopped = self.id  # this car will pick up the passengers going down
                    self.con.send_mon_car_id(floor.down_queue, self.id)
                # up request up queue +  no car stopped
                elif con.request_floor[1, floor_id] and floor.up_queue.if_car_stopped == 0:
                    # ( no people in car and decided by agent (stop at 'floor') ) or rule
                    if (self.cur_num == 0 and self.decision_point) \
                            or (not self.decision_point and ((self.cur_num == 0 or (self.cur_num != 0 and self.stop_at[2, 1:floor_id].sum() == 0)) and (floor_id == min(con.request_floor[1, 1:floor_id + 1][np.nonzero(con.request_floor[1, 1:floor_id + 1])])))):
                        passenger_get_on = 1  # up get on
                        floor.up_queue.if_car_stopped = self.id  # this car will pick up the passengers going up
                        self.con.send_mon_car_id(floor.up_queue, self.id)

            elif self.state == CarState.MOVING_UP:
                if con.request_floor[1, floor_id] and floor.up_queue.if_car_stopped == 0:
                    passenger_get_on = 1  # up get on
                    floor.up_queue.if_car_stopped = self.id
                    self.con.send_mon_car_id(floor.up_queue, self.id)
                elif con.request_floor[0, floor_id] and floor.down_queue.if_car_stopped == 0:
                    if (self.cur_num == 0 and self.decision_point) or \
                            (not self.decision_point and ((self.cur_num == 0 or (self.cur_num != 0 and self.stop_at[2, floor_id + 1:].sum() == 0)) and (floor_id == max(con.request_floor[0, floor_id:][np.nonzero(con.request_floor[0, floor_id:])])))):
                        passenger_get_on = 0  # down get on
                        floor.down_queue.if_car_stopped = self.id
                        self.con.send_mon_car_id(floor.down_queue, self.id)

        return passenger_get_on

    def arrive_floor(self, floor):
        self.logger.debug(f'Car {self.id} arrived at floor {floor.floor_id}')
        self.stop_at_prev_floor = self.stop_at_next_floor
        self.set_location(floor)
        current_floor_id = floor.floor_id
        self.next_floor = None

        if current_floor_id == self.num_floor:
            self.set_state(CarState.MOVING_DOWN)  # change to move down
        elif current_floor_id == 1:
            self.set_state(CarState.MOVING_UP)  # change to move up

        if self.stop_at_prev_floor:  # if stopped at this floor
            if self.get_off_at_next_floor:  # if passenger get off
                get_off_list = self.passenger_in_car[current_floor_id]
                # self.passengerCount[0, current_floor_id - 1] = len(getOffList)  # not used yet
                get_off_time = truncnorm.rvs(0.6, 6, loc=1, scale=1,
                                             size=len(get_off_list),
                                             random_state=get_random_seed())
                get_off_time_sum = get_off_time.sum()
                self.con.emq.scheduleEvtMsg4(get_off_time_sum + self.door_time, self,
                                             self, 'get off', param=(self.get_on_at_next_floor, get_off_time))
            elif self.get_on_at_next_floor != -1:  # passenger get on without any passenger getting off
                self.logger.debug('passenger get on')
                board_from, board_time = self.get_board_time()
                assert board_from.if_car_stopped != 0  # make sure that no other car stopped for the queue
                board_time_sum = board_time.sum()
                self.con.emq.scheduleEvtMsg4(board_time_sum + self.door_time, self, board_from,
                                             'passenger board', param=(self, board_time))
            else:
                # car stopped maybe just want to change direction, e.g., arrive at top floor => change to move down
                self.instantEvtMsg(self, 'decide next move', param=self)
        else:
            self.logger.debug(f'{self.id} pass floor{current_floor_id}')
            self.instantEvtMsg(self, 'decide next move', param=self)  # no stop => move directly

    def set_location_anim(self, floor, t):
        x, y = self.get_pos(floor)
        self.con.emq.sendMonMsg(f"anim Car{self.id} {x:.1f} {y:.1f} {t * 400:.2f}")

    def set_location(self, floor):
        if self.prev_floor:
            assert self.prev_floor != floor
        self.prev_floor = floor

    def get_pos(self, floor):
        return self.stop_pos[floor.floor_id]

    def set_state(self, s):
        self.state = s
        self.util.stateChange(self.con.Tnow(), self.state.working())
        self.con.emq.sendMonMsg(f"color Car{self.id} {self.state.value}")

    # def resetPassengerCount(self):  # not used yet
    #     self.passengerCount = np.zeros((2, self.num_floor))  # 0: get off, 1: get on

    def get_next_floor(self):  # not used yet
        assert self.decision_point is False
        current_floor_id = self.prev_floor.floor_id
        if self.state == CarState.MOVING_DOWN:
            if current_floor_id != self.num_floor and \
                    (self.stop_at[2, :self.prev_floor.floor_id].sum() + self.con.request_floor[:, :self.prev_floor.floor_id].sum() == 0):
                assert self.stop_at.sum() == 0  # no passenger in the car, otherwise can not reverse
                if self.stop_at_prev_floor:
                    self.set_state(CarState.MOVING_UP)
                # self.resetPassengerCount()  # not used yet
        else:
            assert self.state == CarState.MOVING_UP
            if current_floor_id != 1 and \
                    (self.stop_at[2, self.prev_floor.floor_id + 1:].sum() + self.con.request_floor[:, self.prev_floor.floor_id + 1:].sum() == 0):
                assert self.stop_at.sum() == 0  # no passenger in the car, otherwise can not reverse
                if self.stop_at_prev_floor:  # can only change direction when stop at this floor
                    self.set_state(CarState.MOVING_DOWN)  # state change
                # self.resetPassengerCount()  # not used yet

        if self.state == CarState.MOVING_UP:
            floor = self.prev_floor.up_floor
        else:
            assert self.state == CarState.MOVING_DOWN
            floor = self.prev_floor.down_floor

        return floor

    def up_floor_up_queue_available(self):
        condition1 = (self.con.request_floor[1, self.prev_floor.up_floor.floor_id] != 0)
        condition2 = (self.prev_floor.up_floor.up_queue.if_car_stopped == 0)
        return condition1 and condition2

    def up_floor_down_queue_available(self):
        condition1 = (self.con.request_floor[0, self.prev_floor.up_floor.floor_id] != 0)
        condition2 = (self.prev_floor.up_floor.down_queue.if_car_stopped == 0)
        return condition1 and condition2

    def down_floor_up_queue_available(self):
        condition1 = (self.con.request_floor[1, self.prev_floor.down_floor.floor_id] != 0)
        condition2 = (self.prev_floor.down_floor.up_queue.if_car_stopped == 0)
        return condition1 and condition2

    def down_floor_down_queue_available(self):
        condition1 = (self.con.request_floor[0, self.prev_floor.down_floor.floor_id] != 0)
        condition2 = (self.prev_floor.down_floor.down_queue.if_car_stopped == 0)
        return condition1 and condition2

    def get_action_config(self):
        # 0: stop at up floor; 1: stop at down floor; 2: pass up floor; 3: pass down floor; 4: stay
        available_actions = np.ones(5)
        current_floor_id = self.prev_floor.floor_id

        # if there are still passenger in car or waiting in the hall or did not stop at the prev floor => do not stay
        if self.stop_at.sum() + self.con.request_floor.sum() != 0 or self.stop_at_prev_floor is False:
            available_actions[CarAction.STAY.value] = 0

        # no stop at prev floor or passenger in the car => can not change direction
        if (not self.stop_at_prev_floor) or (self.stop_at.sum() != 0):
            if self.state == CarState.MOVING_DOWN:
                available_actions[CarAction.STOP_UP.value] = 0  # can not stop at up floor
                available_actions[CarAction.PASS_UP.value] = 0  # can not pass up floor
                if self.stop_at[2, self.prev_floor.down_floor.floor_id] != 0:  # passenger get off at down floor
                    available_actions[CarAction.PASS_DOWN.value] = 0  # can not pass down floor
                    assert available_actions.sum() == 1
                    # print('hehe: ', self.id, available_actions)
                    return [self.id, available_actions]
                elif self.cur_num == self.capacity:  # should always pass down floor before passenger get off
                    # can not stop at down floor if no passenger get off at down floor
                    available_actions[CarAction.STOP_DOWN.value] = 0
                    assert available_actions.sum() == 1
                    # print('hehe: ', self.id, available_actions)
                    return [self.id, available_actions]
            elif self.state == CarState.MOVING_UP:
                available_actions[CarAction.STOP_DOWN.value] = 0  # can not stop at down floor
                available_actions[CarAction.PASS_DOWN.value] = 0  # can not pass at down floor
                if self.stop_at[2, self.prev_floor.up_floor.floor_id] != 0:  # passenger get off at up floor
                    available_actions[CarAction.PASS_UP.value] = 0  # can not pass up floor because passenger get off
                    assert available_actions.sum() == 1
                    # print('hehe: ', self.id, available_actions)
                    return [self.id, available_actions]
                elif self.cur_num == self.capacity:
                    # can not stop at up since there is no available space
                    available_actions[CarAction.STOP_UP.value] = 0
                    assert available_actions.sum() == 1
                    # print('hehe: ', self.id, available_actions)
                    return [self.id, available_actions]

        if current_floor_id == 1:
            available_actions[CarAction.STOP_DOWN.value] = 0  # can not stop at down floor
            available_actions[CarAction.PASS_DOWN.value] = 0  # can not pass at down floor
        elif current_floor_id == 2:
            available_actions[CarAction.PASS_DOWN.value] = 0  # can not pass down floor
        elif current_floor_id == self.num_floor:
            available_actions[CarAction.STOP_UP.value] = 0  # can not stop at up floor
            available_actions[CarAction.PASS_UP.value] = 0  # can not pass up floor
        elif current_floor_id == self.num_floor - 1:
            available_actions[CarAction.PASS_UP.value] = 0  # can not pass up floor

        # up floor passenger case
        if current_floor_id != self.num_floor and current_floor_id != self.num_floor - 1:
            if self.stop_at.sum() == 0:  # no passenger in the car
                if not self.up_floor_up_queue_available() and not self.up_floor_down_queue_available():
                    available_actions[CarAction.STOP_UP.value] = 0
                    if self.con.request_floor[:, self.prev_floor.up_floor.floor_id + 1:].sum() == 0 \
                            and self.con.request_floor[:, :self.prev_floor.floor_id].sum() != 0:
                        if self.state == CarState.MOVING_UP and self.stop_at_prev_floor is False:
                            available_actions[CarAction.STOP_UP.value] = 1  # to change direction
                            # self.change_direction = True
                            # # print('hehe: ', self.id, np.array([1., 0., 0., 0., 0.]))
                            # return [self.id, np.array([1., 0., 0., 0., 0.])]
            else:
                assert self.stop_at.sum() != 0  # passenger in the car
                if not self.up_floor_up_queue_available():
                    available_actions[CarAction.STOP_UP.value] = 0  # should not stop

        # down floor passenger case
        if current_floor_id != 1 and current_floor_id != 2:
            if self.stop_at.sum() == 0:  # no passenger in the car
                if not self.down_floor_up_queue_available() and not self.down_floor_down_queue_available():
                    available_actions[CarAction.STOP_DOWN.value] = 0
                    if self.con.request_floor[:, :self.prev_floor.down_floor.floor_id].sum() == 0 \
                            and self.con.request_floor[:, self.prev_floor.floor_id + 1:].sum() != 0:
                        if self.state == CarState.MOVING_DOWN and self.stop_at_prev_floor is False:
                            available_actions[CarAction.STOP_DOWN.value] = 1
                            # self.change_direction = True
                            # # print('hehe: ', np.array([0., 1., 0., 0., 0.]))
                            # return [self.id, np.array([0., 1., 0., 0., 0.])]
            if self.stop_at.sum() != 0:  # passenger in the car
                if not self.down_floor_down_queue_available():
                    available_actions[CarAction.STOP_DOWN.value] = 0

        assert available_actions.sum() >= 1
        # print('hehe: ', self.id, available_actions)
        return [self.id, available_actions]

    def move(self):
        if self.stop_at_prev_floor:
            if self.stop_at_next_floor:
                t = self.t00
            else:
                t = self.t0f
        else:
            if self.stop_at_next_floor:
                t = self.tf0
            else:
                t = self.tff

        assert self.next_floor
        self.set_location_anim(self.next_floor, t)
        self.con.emq.scheduleEvtMsg4(t, self, self, 'arrive floor', param=self.next_floor)

    def act_after_get_off(self, e):
        passenger_get_on, get_off_time = e.param
        self.passenger_get_off(get_off_time)

        if passenger_get_on != -1:  # passenger get on
            board_from, board_time = self.get_board_time()
            assert board_from.if_car_stopped == self.id
            board_time_sum = board_time.sum()
            self.con.emq.scheduleEvtMsg4(board_time_sum, self, board_from, 'passenger board', param=(self, board_time))
        else:  # no passenger board
            # close the door and decide next move
            self.con.emq.scheduleEvtMsg4(self.door_time, self, self, 'decide next move', param=self)

    def act_after_boarded(self, e):
        boarded_list, board_time = e.param
        self.update_after_boarded(boarded_list, board_time)

        # after passenger boarded, close the door and decide next move
        self.con.emq.scheduleEvtMsg4(self.door_time, self, self, 'decide next move', param=self)

    def decide_next_move(self):
        self.stop_at_next_floor = False
        self.get_on_at_next_floor = -1  # -1: no get on, 0: down get on, 1: up get on
        self.get_off_at_next_floor = False
        self.decision_point = False

        if self.change_direction:
            if self.state == CarState.MOVING_DOWN:
                self.next_floor = self.prev_floor.up_floor
                self.set_state(CarState.MOVING_UP)
            else:
                assert self.state == CarState.MOVING_UP
                self.next_floor = self.prev_floor.down_floor
                self.set_state(CarState.MOVING_DOWN)
            self.change_direction = False
        else:
            action_config = self.get_action_config()
            available_actions = action_config[1]  # actionConfig[0] is car's id
            if available_actions.sum() > 1:
                self.decision_point = True
                self.con.decision_num_count += 1
                start = time.time()
                action = self.con.act_at_decision_point(action_config)
                end = time.time()
                self.con.decision_time += (end - start)
                assert available_actions[action] == 1
            else:
                action = np.nonzero(available_actions)[0]

            if action in [0, 1]:
                self.stop_at_next_floor = True
            if action in [0, 2]:  # moving up
                self.next_floor = self.prev_floor.up_floor
                self.set_state(CarState.MOVING_UP)
            elif action in [1, 3]:  # moving down
                self.next_floor = self.prev_floor.down_floor
                self.set_state(CarState.MOVING_DOWN)
            else:
                assert action == 4
                self.set_state(CarState.IDLE)
                self.logger.debug(f'Car {self.id} becomes idle at floor {self.prev_floor.floor_id}')
                return

        if self.decision_point and self.stop_at_next_floor:
            self.get_on_at_next_floor = self.if_get_on(self.next_floor)
        if not self.decision_point:
            self.get_off_at_next_floor = self.if_get_off(self.next_floor)
            self.get_on_at_next_floor = self.if_get_on(self.next_floor)
            if self.get_off_at_next_floor or self.get_on_at_next_floor != -1 or \
                    self.next_floor.floor_id == self.num_floor or self.next_floor.floor_id == 1:
                self.stop_at_next_floor = True

        assert self.next_floor is not None
        self.instantEvtMsg(self, 'move', param=self)

    def processEvtMsg(self, e):
        if e.msg == 'arrive floor':
            self.arrive_floor(e.param)
        elif e.msg == 'move':
            self.move()
        elif e.msg == 'get off':
            self.act_after_get_off(e)
            self.con.reward += self.con.get_partial_reward()  # calculate partial reward
        elif e.msg == 'boarded':
            self.act_after_boarded(e)
            self.con.reward += self.con.get_partial_reward()  # calculate partial reward
        elif e.msg == 'decide next move':
            self.decide_next_move()
