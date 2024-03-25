from DES import *
from StateDef import CarState
from Agent import DQNAgent
import numpy as np
from Floors import Floor
import math
from scipy.stats import truncnorm
from Passenger import PassengerGenerator
from ElevatorCar import ElevatorCar
from job_stat import JobStat
import torch
from output_handler import OutputHandler
from utils import get_random_seed
from multitask.data_collection import DataCollector


class ElevatorController(AModel):
    def __init__(self, emq, args):
        self.args = args
        self.emq = emq
        emq.con = self
        self.output_handler = OutputHandler(args)
        self.output_handler.con = self
        self.num_floor = args.num_floor
        self.logger = args.logger
        self.capacity = args.car_capacity
        self.num_elevator = args.num_elevator
        self.population = args.population
        self.traffic_pattern = args.traffic_pattern
        self.check_interval = 10000  # not used yet
        self.job_stat = JobStat(self)
        self.request_floor = np.zeros((2, self.num_floor + 1))  # 0: down request; 1: up request
        self.floor_map = {}
        self.create_floors()
        self.arrival_rate = {}
        self.prior_arrival_rate = {}
        self.initialize_arrival_rate()
        self.pg_list = []
        self.create_passenger_generators()
        self.car_map = {}
        self.day_index = -1
        self.update_day_index()
        self.create_elevator_cars()
        self.dispatcher_mode = args.dispatcher_mode  # RL here only
        self.mode = args.mode  # train or test
        self.dispatcher = self.load_dispatcher()
        self.reward = 0.
        self.prev_event_time = 0.
        self.prev_action_time = 0.
        self.first_decision_point = True
        self.prev_action = None
        self.prev_state = None
        self.decision_num_count = 0.
        self.decision_time = 0.
        # self.data_collector = DataCollector(self)

    def update_day_index(self):
        self.day_index += 1
        self.emq.scheduleEvtMsg4(86400, self, self, 'update day index', param=None)

    def initialize_arrival_rate(self):
        # self.prior_arrival_rate['in coming'] = [2.80, 2.9, 3.20, 6.00, 7.80, 11.00, 7.00, 2.90, 1.50, 1.90, 3.20, 4.10,
        #                                         3.00, 2.60, 2.40, 1.60, 1.50, 1.40, 2.50, 4.00, 6.20, 7.00, 5.00, 2.50,
        #                                         3.00, 6.00, 7.00, 3.70, 2.50, 2.20, 2.10, 2.00, 2.00, 2.10, 2.00, 1.90,
        #                                         2.30, 2.40, 3.00, 5.00, 5.50, 2.00, 0.20, 0.10, 0.10, 0.10, 0.10, 0.10]
        #
        # self.prior_arrival_rate['inter floor'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        #
        # self.prior_arrival_rate['out going'] = [0.10, 0.1, 0.10, 0.10, 0.10, 0.60, 1.80, 3.50, 4.00, 3.40, 2.50, 2.40,
        #                                         2.30, 2.20, 2.70, 3.80, 5.60, 5.80, 7.00, 5.00, 2.60, 1.40, 4.00, 6.00,
        #                                         6.60, 5.00, 3.40, 2.50, 2.70, 2.40, 2.50, 2.80, 2.70, 2.90, 2.90, 4.00,
        #                                         5.80, 6.50, 4.00, 2.80, 3.00, 5.60, 15.00, 20.00, 11.00, 2.00, 1.00, 0.10]
        # self.arrival_rate['in coming'] = [2.80, 2.9, 3.20, 6.00, 7.80, 11.00, 7.00, 2.90, 1.50, 1.90, 3.20, 4.10,
        #                                         3.00, 2.60, 2.40, 1.60, 1.50, 1.40, 2.50, 4.00, 6.20, 7.00, 5.00, 2.50,
        #                                         3.00, 6.00, 7.00, 3.70, 2.50, 2.20, 2.10, 2.00, 2.00, 2.10, 2.00, 1.90,
        #                                         2.30, 2.40, 3.00, 5.00, 5.50, 2.00, 0.20, 0.10, 0.10, 0.10, 0.10, 0.10]
        #
        # self.arrival_rate['inter floor'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        #
        # self.arrival_rate['out going'] = [0.10, 0.1, 0.10, 0.10, 0.10, 0.60, 1.80, 3.50, 4.00, 3.40, 2.50, 2.40,
        #                                         2.30, 2.20, 2.70, 3.80, 5.60, 5.80, 7.00, 5.00, 2.60, 1.40, 4.00, 6.00,
        #                                         6.60, 5.00, 3.40, 2.50, 2.70, 2.40, 2.50, 2.80, 2.70, 2.90, 2.90, 4.00,
        #                                         5.80, 6.50, 4.00, 2.80, 3.00, 5.60, 15.00, 20.00, 11.00, 2.00, 1.00, 0.10]

        # self.prior_arrival_rate['in coming'] = [0.60, 0.50, 0.80, 0.60, 1.70, 2.55, 4.40, 5.50, 6.40, 6.10, 4.55, 2.80,
        #                                         2.30, 2.00, 1.55, 1.40, 1.70, 1.20, 1.40, 1.50, 1.80, 2.20, 1.90, 3.85,
        #                                         4.90, 5.30, 6.10, 7.05, 3.90, 3.50, 2.05, 2.00, 1.60, 1.10, 1.60, 1.20,
        #                                         1.50, 1.00, 1.20, 1.30, 1.00, 1.05, 1.00, 0.90, 0.80, 0.55, 0.20, 0.40]
        #
        # self.prior_arrival_rate['inter floor'] = [0.10, 0.05, 0.10, 0.05, 0.20, 0.60, 0.80, 1.45, 2.50, 2.40, 3.15,
        #                                           2.55,
        #                                           2.20, 2.25, 2.00, 1.40, 2.15, 2.25, 1.90, 1.70, 2.00, 1.60, 1.00,
        #                                           0.90,
        #                                           1.05, 1.10, 1.95, 2.00, 1.50, 2.05, 2.50, 1.05, 1.95, 1.60, 1.30,
        #                                           1.60,
        #                                           2.05, 1.50, 1.70, 1.60, 1.20, 1.20, 1.70, 1.00, 1.50, 0.80, 0.80,
        #                                           0.50]
        #
        # self.prior_arrival_rate['out going'] = [0.60, 0.10, 0.50, 0.55, 0.70, 0.65, 1.05, 1.05, 1.40, 1.45, 1.25, 1.35,
        #                                         1.20, 1.30, 1.35, 1.40, 1.10, 1.60, 1.65, 2.60, 5.70, 6.10, 6.55, 6.20,
        #                                         2.65, 2.55, 1.45, 1.40, 1.15, 1.10, 1.15, 1.75, 1.45, 1.40, 1.35, 1.30,
        #                                         2.00, 1.40, 1.00, 1.30, 2.05, 2.90, 4.40, 2.95, 3.00, 2.00, 1.65, 1.50]
        #
        # self.arrival_rate['in coming'] = [0.60, 0.50, 0.80, 0.60, 1.70, 2.55, 4.40, 5.50, 6.40, 6.10, 4.55, 2.80,
        #                                   2.30, 2.00, 1.55, 1.40, 1.70, 1.20, 1.40, 1.50, 1.80, 2.20, 1.90, 3.85,
        #                                   4.90, 5.30, 6.10, 7.05, 3.90, 3.50, 2.05, 2.00, 1.60, 1.10, 1.60, 1.20,
        #                                   1.50, 1.00, 1.20, 1.30, 1.00, 1.05, 1.00, 0.90, 0.80, 0.55, 0.20, 0.40]
        #
        # self.arrival_rate['inter floor'] = [0.10, 0.05, 0.10, 0.05, 0.20, 0.60, 0.80, 1.45, 2.50, 2.40, 3.15, 2.55,
        #                                     2.20, 2.25, 2.00, 1.40, 2.15, 2.25, 1.90, 1.70, 2.00, 1.60, 1.00, 0.90,
        #                                     1.05, 1.10, 1.95, 2.00, 1.50, 2.05, 2.50, 1.05, 1.95, 1.60, 1.30, 1.60,
        #                                     2.05, 1.50, 1.70, 1.60, 1.20, 1.20, 1.70, 1.00, 1.50, 0.80, 0.80, 0.50]
        #
        # self.arrival_rate['out going'] = [0.60, 0.10, 0.50, 0.55, 0.70, 0.65, 1.05, 1.05, 1.40, 1.45, 1.25, 1.35,
        #                                   1.20, 1.30, 1.35, 1.40, 1.10, 1.60, 1.65, 2.60, 5.70, 6.10, 6.55, 6.20,
        #                                   2.65, 2.55, 1.45, 1.40, 1.15, 1.10, 1.15, 1.75, 1.45, 1.40, 1.35, 1.30,
        #                                   2.00, 1.40, 1.00, 1.30, 2.05, 2.90, 4.40, 2.95, 3.00, 2.00, 1.65, 1.50]

        # self.prior_arrival_rate['in coming'] = [0.90, 1.20, 4.00, 14.40, 13.60, 2.80, 2.90, 4.30, 4.80, 3.30, 2.80, 3.00,
        #                                         2.60, 2.70, 2.50, 2.60, 2.60, 2.40, 2.50, 2.60, 3.50, 6.80, 9.10, 6.80,
        #                                         3.00, 3.50, 5.00, 2.00, 1.80, 2.00, 2.80, 2.40, 2.80, 2.90, 3.00, 2.70,
        #                                         2.80, 2.50, 2.70, 2.80, 2.50, 2.60, 2.80, 3.80, 2.50, 2.00, 1.80, 1.20]
        #
        # self.prior_arrival_rate['inter floor'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        #
        # self.prior_arrival_rate['out going'] = [0.10, 0.10, 0.70, 0.80, 1.40, 2.00, 3.50, 4.80, 3.60, 2.90, 2.90, 2.80,
        #                                         2.70, 3.60, 3.50, 3.40, 4.00, 8.00, 9.00, 5.00, 2.60, 3.00, 5.00, 3.10,
        #                                         2.70, 2.40, 1.70, 1.80, 2.00, 2.20, 1.90, 2.40, 2.60, 2.50, 2.70, 2.10,
        #                                         1.90, 2.40, 4.00, 24.50, 16.00, 8.00, 2.00, 1.00, 1.00, 1.10, 0.50, 0.05]
        #
        # self.arrival_rate['in coming'] = [0.90, 1.20, 4.00, 14.40, 13.60, 2.80, 2.90, 4.30, 4.80, 3.30, 2.80, 3.00,
        #                                         2.60, 2.70, 2.50, 2.60, 2.60, 2.40, 2.50, 2.60, 3.50, 6.80, 9.10, 6.80,
        #                                         3.00, 3.50, 5.00, 2.00, 1.80, 2.00, 2.80, 2.40, 2.80, 2.90, 3.00, 2.70,
        #                                         2.80, 2.50, 2.70, 2.80, 2.50, 2.60, 2.80, 3.80, 2.50, 2.00, 1.80, 1.20]
        #
        # self.arrival_rate['inter floor'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #                                         0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        #
        # self.arrival_rate['out going'] = [0.10, 0.10, 0.70, 0.80, 1.40, 2.00, 3.50, 4.80, 3.60, 2.90, 2.90, 2.80,
        #                                         2.70, 3.60, 3.50, 3.40, 4.00, 8.00, 9.00, 5.00, 2.60, 3.00, 5.00, 3.10,
        #                                         2.70, 2.40, 1.70, 1.80, 2.00, 2.20, 1.90, 2.40, 2.60, 2.50, 2.70, 2.10,
        #                                         1.90, 2.40, 4.00, 24.50, 16.00, 8.00, 2.00, 1.00, 1.00, 1.10, 0.50, 0.05]

        self.prior_arrival_rate['in coming'] = [1.8, 1.85, 2.8, 2.9, 3.8, 5.9, 7.3, 7, 7.1, 4.85, 3.9, 3.5,
                                                2.1, 1.6, 1.4, 1.7, 1.6, 1.55, 1.5, 1.45, 1.6, 1.5, 1.65, 1.7,
                                                2.6, 4.1, 3.8, 4.8, 4, 2.8, 1.4, 2.2, 2.1, 1.7, 1.3, 1.6,
                                                1.5, 1.4, 1.0, 1.1, 1.0, 1.1, 0.9, 0.6, 0.6, 0.6, 0.5, 0.4]

        self.prior_arrival_rate['inter floor'] = [0.3, 0.6, 0.6, 0.55, 0.7, 1.2, 2.2, 2.5, 4.5, 3.2, 3.4, 3.95,
                                                  3.5, 3.2, 3, 4.3, 3.3, 2.8, 4, 3.25, 4.2, 5.5, 5.3, 5.4,
                                                  5.6, 4.6, 4.9, 5.8, 6, 3.6, 1.9, 1.9, 2.2, 2.3, 1.9, 2.5,
                                                  2.6, 2.4, 2.3, 1.0, 1.3, 1.5, 1.3, 1.0, 0.7, 0.6, 0.6, 0.6]

        self.prior_arrival_rate['out going'] = [0.4, 0.4, 0.25, 0.55, 0.4, 0.3, 0.6, 0.7, 0.7, 0.8, 1.3, 1.3,
                                                1.6, 1.5, 1.4, 1, 1.4, 1.8, 4, 4.8, 8.2, 5.7, 5.8, 4.2,
                                                3.3, 2.75, 2.4, 1.2, 1.2, 1.1, 1.4, 2.1, 1.5, 1.3, 1.8, 1.4,
                                                1.6, 2.7, 2, 2.5, 3.4, 6.4, 5, 4.6, 3.7, 3.9, 2.85, 2]

        self.arrival_rate['in coming'] = [1.8, 1.85, 2.8, 2.9, 3.8, 5.9, 7.3, 7, 7.1, 4.85, 3.9, 3.5,
                                          2.1, 1.6, 1.4, 1.7, 1.6, 1.55, 1.5, 1.45, 1.6, 1.5, 1.65, 1.7,
                                          2.6, 4.1, 3.8, 4.8, 4, 2.8, 1.4, 2.2, 2.1, 1.7, 1.3, 1.6,
                                          1.5, 1.4, 1.0, 1.1, 1.0, 1.1, 0.9, 0.6, 0.6, 0.6, 0.5, 0.4]

        self.arrival_rate['inter floor'] = [0.3, 0.6, 0.6, 0.55, 0.7, 1.2, 2.2, 2.5, 4.5, 3.2, 3.4, 3.95,
                                                  3.5, 3.2, 3, 4.3, 3.3, 2.8, 4, 3.25, 4.2, 5.5, 5.3, 5.4,
                                                  5.6, 4.6, 4.9, 5.8, 6, 3.6, 1.9, 1.9, 2.2, 2.3, 1.9, 2.5,
                                                  2.6, 2.4, 2.3, 1.0, 1.3, 1.5, 1.3, 1.0, 0.7, 0.6, 0.6, 0.6]

        self.arrival_rate['out going'] = [0.4, 0.4, 0.25, 0.55, 0.4, 0.3, 0.6, 0.7, 0.7, 0.8, 1.3, 1.3,
                                                1.6, 1.5, 1.4, 1, 1.4, 1.8, 4, 4.8, 8.2, 5.7, 5.8, 4.2,
                                                3.3, 2.75, 2.4, 1.2, 1.2, 1.1, 1.4, 2.1, 1.5, 1.3, 1.8, 1.4,
                                                1.6, 2.7, 2, 2.5, 3.4, 6.4, 5, 4.6, 3.7, 3.9, 2.85, 2]

        # self.arrival_rate['in coming'] = [1.4, 4.45, 6.25, 8.25, 9.65, 9.2, 4.55, 3.425, 1.95, 1.75, 1.9, 1.5,
        #                                   1.6, 2.1, 1.6, 1.5, 1.45, 1.7, 1.6, 1.5, 1.55, 1.65, 1.5, 1.6,
        #                                   3.6, 5.9, 4.8, 3, 2.6, 1.8, 1.5, 2.1, 2, 1.8, 1.2, 1.6,
        #                                   1.3, 1.4, 1.3, 1.1, 1.2, 0.9, 0.8, 0.9, 0.5, 0.6, 0.6, 0.3]
        #
        # self.arrival_rate['inter floor'] = [0.3, 0.5, 1.1, 2.5, 4.2, 3.75, 2.25, 2.1, 1.7, 1.975, 1.15, 1.3,
        #                                     3.3, 3.4, 3.3, 4, 3.3, 3, 4.5, 3.5, 4, 5, 5, 5.7,
        #                                     5, 5.2, 5, 5.7, 5, 4.6, 1.9, 2, 2.1, 2.1, 2.4, 2.3,
        #                                     2.5, 2.4, 2.4, 1.2, 1.1, 1.4, 1.2, 0.9, 0.8, 0.7, 0.6, 0.5]
        #
        # self.arrival_rate['out going'] = [0.125, 0.275, 0.95, 0.9, 1.375, 1.625, 0.35, 0.4, 0.65, 0.65, 0.2, 0.2,
        #                                   1.8, 1.4, 1,	1.4, 1.5, 1.6, 3.8, 9.2, 6.7, 5.8, 3.2, 3,
        #                                   2.5, 2, 1.6, 1.4, 1.2, 1.2, 1.5, 2, 1.6, 1.4, 1.7, 1.5,
        #                                   1.5, 2.9, 4, 6.5, 5.5, 5, 3.9, 3.7, 2.8, 2.9, 2.5, 2]

    def get_ar_list(self):
        ar_list = []
        for pg in self.pg_list:
            ar = 1 / pg.get_prior_ar()
            ar_list.append(ar)
        # self.data_collector.append_state(ar_list, self.Tnow())

    def get_arrival_rate(self):
        arm = np.zeros((6, self.num_floor))
        for pg in self.pg_list:  # in coming, inter floor, out going
            ar = 1 / pg.get_prior_ar()
            if pg.type == 'in coming':
                arm[0, 0] = ar  # from
                arm[1, 1:] = np.repeat(ar, self.num_floor - 1) / (self.num_floor - 1)  # to
            elif pg.type == 'inter floor':
                arm[2, 1:] = np.repeat(ar, self.num_floor - 1) / (self.num_floor - 1)  # from
                arm[3, 1:] = np.repeat(ar, self.num_floor - 1) / (self.num_floor - 1)  # to
            else:
                arm[4, 1:] = np.repeat(ar, self.num_floor - 1) / (self.num_floor - 1)  # from
                arm[5, 0] = ar  # to

        arm[0, :] = arm[0, :] + arm[2, :] + arm[4, :]
        arm[1, :] = arm[1, :] + arm[3, :] + arm[5, :]
        # print('arm: ', arm[0:2, :])
        return arm[0:2, :]
        # return arm

    def get_real_arm(self):
        real_arm = np.zeros((2, self.num_floor))
        for i in range(self.num_floor):
            real_arm[0, i], real_arm[1, i] = self.floor_map[i + 1].get_real_rate()
            # real_arm[0, i] = self.floor_map[i + 1].real_fr
            # real_arm[1, i] = self.floor_map[i + 1].real_tr
        # print('real_arm: ', real_arm)
        return real_arm

    def get_env_state(self):
        hm = self.get_hall_info()
        cm = self.get_car_info()
        # pm = self.getPassengerInfoMatrix()
        if self.args.use_arrival_rate:
            arm = self.get_arrival_rate()
            past_data = self.get_real_arm()
            post = self.args.b * arm + (1 - self.args.b) * past_data
            # post = arm
            env_state = np.concatenate([hm, cm, post.transpose()], axis=1)
        else:
            self.get_ar_list()   # just for data collection
            env_state = np.concatenate([hm, cm], axis=1)
        return env_state

    def get_discounted_cost(self, t, cet, pet):
        beta = self.args.beta

        if t > pet:
            pet = t

        if self.args.rr == 'rr0':
            result = math.exp(-beta * (pet - self.prev_action_time)) * (1 / beta) - \
                     math.exp(-beta * (cet - self.prev_action_time)) * (1 / beta)
            normalization = 1
        elif self.args.rr == 'rr1':
            result = math.exp(-beta * (pet - self.prev_action_time)) * ((pet - t) / beta + 1 / (beta ** 2)) \
                     - math.exp(-beta * (cet - self.prev_action_time)) * ((cet - t) / beta + 1 / (beta ** 2))
            normalization = 1e2
        else:
            result = math.exp(-beta * (pet - self.prev_action_time)) * (
                        (pet - t) ** 2 / beta + 2 * (pet - t) / (beta ** 2) + 2 / (beta ** 3)) \
                     - math.exp(-beta * (cet - self.prev_action_time)) * (
                                 (cet - t) ** 2 / beta + 2 * (cet - t) / (beta ** 2) + 2 / (beta ** 3))
            normalization = 1e4

        # assert result >= 0
        return result / normalization

    def get_partial_reward(self):
        cet = self.Tnow()
        partial_reward_wt = 0
        partial_reward_jt = 0
        pet = self.prev_event_time

        for i in range(1, 1 + self.num_floor):
            floor = self.floor_map[i]
            for floor_queue in [floor.up_queue, floor.down_queue]:
                if floor_queue.queue:
                    for p in floor_queue.queue:
                        at = p.gen_at  # arrival time of passenger p
                        if at == cet:
                            wt_cost_p = 0
                        else:
                            wt_cost_p = self.get_discounted_cost(at, cet, pet)
                        partial_reward_wt += wt_cost_p

        if self.args.jt_reward:
            for car in self.car_map.values():
                for i in range(1, 1 + self.num_floor):
                    passengers = car.passenger_in_car[i]
                    if passengers:
                        for p in passengers:
                            bt = p.board_at  # board time of passenger p
                            if bt == cet:
                                jt_cost_p = 0
                            else:
                                jt_cost_p = self.get_discounted_cost(bt, cet, pet)
                            partial_reward_jt += jt_cost_p

        self.prev_event_time = cet  # reset previous event time to current event time
        partial_reward = partial_reward_wt + self.args.reward_weight * partial_reward_jt
        return partial_reward

    # def get_transition_type(self, car):
    #     if self.traffic_pattern != 'AllInOne':
    #         return None, None
    #     else:
    #         if car.state == CarState.IDLE:
    #             type2 = 3
    #         elif car.state == CarState.MOVING_UP:
    #             type2 = 2
    #         else:
    #             type2 = 1
    #         period = 12 * 3600
    #         t = self.Tnow() % period
    #         if t <= 3 * 3600:
    #             type1 = 1  # for transitions at up peak
    #         elif 4.5 * 3600 < t <= 7.5 * 3600:
    #             type1 = 3  # for transitions at lunch peak
    #         elif 9 * 3600 < t <= period:
    #             type1 = 4  # for transitions at down peak
    #         else:
    #             type1 = 2  # for transitions at inter floor
    #     return type1, type2

    def get_transition_type(self, car):
        if self.traffic_pattern != 'AllInOne':
            return None, None
        else:
            if car.state == CarState.IDLE:
                type2 = 3
            elif car.state == CarState.MOVING_UP:
                type2 = 2
            else:
                type2 = 1

            period = 12 * 3600
            t = self.Tnow() % period

            if self.args.num_task == 2:
                if t <= 6 * 3600:
                    type1 = 1
                else:
                    type1 = 2
            elif self.args.num_task == 4:
                if t <= 3 * 3600:
                    type1 = 1
                elif t <= 6 * 3600:
                    type1 = 2
                elif t <= 9 * 3600:
                    type1 = 3
                else:
                    type1 = 4
            elif self.args.num_task == 6:
                if t <= 2 * 3600:
                    type1 = 1
                elif t <= 4 * 3600:
                    type1 = 2
                elif t <= 6 * 3600:
                    type1 = 3
                elif t <= 8 * 3600:
                    type1 = 4
                elif t <= 10 * 3600:
                    type1 = 5
                else:
                    type1 = 6
            elif self.args.num_task == 8:
                if t <= 1.5 * 3600:
                    type1 = 1
                elif t <= 3 * 3600:
                    type1 = 2
                elif t <= 4.5 * 3600:
                    type1 = 3
                elif t <= 6 * 3600:
                    type1 = 4
                elif t <= 7.5 * 3600:
                    type1 = 5
                elif t <= 9 * 3600:
                    type1 = 6
                elif t <= 10.5 * 3600:
                    type1 = 7
                else:
                    type1 = 8
            elif self.args.num_task == 10:
                if t <= 1.2 * 3600:
                    type1 = 1
                elif t <= 2.4 * 3600:
                    type1 = 2
                elif t <= 3.6 * 3600:
                    type1 = 3
                elif t <= 4.8 * 3600:
                    type1 = 4
                elif t <= 6.0 * 3600:
                    type1 = 5
                elif t <= 7.2 * 3600:
                    type1 = 6
                elif t <= 8.4 * 3600:
                    type1 = 7
                elif t <= 9.6 * 3600:
                    type1 = 8
                elif t <= 10.8 * 3600:
                    type1 = 9
                else:
                    type1 = 10

        return type1, type2

    def act_at_decision_point(self, action_config):
        state = self.get_env_state()
        state = torch.tensor(state).float().permute(1, 0).to(self.args.device)
        action = self.dispatcher.get_action(state.unsqueeze(0), action_config)
        if self.mode != 'test':
            car_id = action_config[0] - 1
            t_now = self.Tnow()
            if self.first_decision_point:
                self.first_decision_point = False
            else:
                # accumulate partial reward
                self.reward += self.get_partial_reward()

                # index of available actions 0-20, 5 is the number of actions for each car
                available_actions = np.nonzero(action_config[1])[0] + car_id * 5
                time_interval = t_now - self.prev_action_time

                t_type1, t_type2 = self.get_transition_type(self.car_map[car_id + 1])
                # store experience segments
                self.dispatcher.memory.push(t_now, (self.prev_state, self.prev_action, self.reward,
                                                    state, available_actions, time_interval, t_type1, t_type2))

                if self.dispatcher.memory.train_start() and self.Tnow() > 12 * 3600:
                    loss = self.dispatcher.train_model(self.args.double_dqn)
                    self.output_handler.append_loss(loss)

            self.reward = 0.  # reset reward for a new transition
            self.prev_action = car_id * 5 + action  # update previous action chosen
            self.prev_state = state  # update previous state
            self.prev_action_time = t_now  # update previous action time
            self.prev_event_time = t_now  # update previous event time
        return action

    # def get_action(self, state, action_config):
    #     with torch.no_grad():
    #         if self.mode == 'test':
    #             period = 12 * 3600
    #             t = self.Tnow() % period
    #             if t <= 3 * 3600:
    #                 dispatcher_mode = 'UpPeak'
    #             elif 4.5 * 3600 < t <= 7.5 * 3600:
    #                 dispatcher_mode = 'LunchPeak'
    #             elif 9 * 3600 < t < period:
    #                 dispatcher_mode = 'DownPeak'
    #             else:
    #                 dispatcher_mode = 'InterFloor'
    #             q_value = self.dispatcher[dispatcher_mode].qn(state).squeeze()
    #         else:
    #             q_value = self.dispatcher.qn(state).squeeze()
    #         action = self.epsilon_greedy(q_value, action_config)
    #     return action

    def get_hall_info(self):
        num_passenger_up = np.zeros(self.num_floor)
        num_passenger_down = np.zeros(self.num_floor)
        if self.args.destination_control:
            wt_up = np.zeros(self.num_floor)
            wt_down = np.zeros(self.num_floor)
        else:
            up_elapsed_time = np.zeros(self.num_floor)  # not destination control setting
            down_elapsed_time = np.zeros(self.num_floor)  # not destination control setting

        # upRequestsCount = np.zeros(self.num_floor)
        # downRequestsCount = np.zeros(self.num_floor)
        t_now = self.Tnow()

        for i in range(self.num_floor):
            floor = self.floor_map[i + 1]
            if self.args.destination_control:
                num_passenger_up[i] = len(floor.up_queue.queue)  # number of passenger waiting for going up
                num_passenger_down[i] = len(floor.down_queue.queue)  # number of passenger waiting for going down
                if num_passenger_up[i]:  # if number of passenger waiting for going up is not 0
                    for passenger in floor.up_queue.queue:
                        wt_up[i] += (t_now - passenger.gen_at)
                if num_passenger_down[i]:
                    for passenger in floor.down_queue.queue:
                        wt_down[i] += (t_now - passenger.gen_at)
            else:
                num_passenger_up[i] = float(len(floor.up_queue.queue) != 0)
                num_passenger_down[i] = float(len(floor.down_queue.queue) != 0)
                up_elapsed_time[i] = num_passenger_up[i] * (t_now - floor.up_queue.press_time)
                down_elapsed_time[i] = num_passenger_down[i] * (t_now - floor.down_queue.press_time)

            # upRequestsCount[i] = len(floor.previousRequests['up'])  # not used yet
            # downRequestsCount[i] = len(floor.previousRequests['down'])  # not used yet
        if self.args.destination_control:
            hm = np.stack([num_passenger_up, num_passenger_down, wt_up, wt_down], axis=1)
        else:
            hm = np.stack([num_passenger_up, num_passenger_down, up_elapsed_time, down_elapsed_time], axis=1)
        return hm

    def get_car_info(self):
        cm = []
        for i in range(1, 1 + self.num_elevator):
            car = self.car_map[i]
            cm.append(car.get_self_info())

        cm = np.concatenate(cm, axis=1)
        return cm

    # def getPassengerInfoMatrix(self):  # not used
    #     passengerInHall = np.zeros((2, self.num_floor))
    #     sumOfSquaredWaitingTime = np.zeros((2, self.num_floor))
    #
    #     for i in range(self.num_floor):
    #         floor = self.floorMap[i + 1]
    #         upQueue = floor.upQueue
    #         passengerInHall[0][i - 1] = len(upQueue.queue)
    #         sumOfSquaredWaitingTime[0][i - 1] = upQueue.getSquaredWaitingTimeSum()
    #         downQueue = floor.downQueue
    #         passengerInHall[1][i - 1] = len(downQueue.queue)
    #         sumOfSquaredWaitingTime[1][i - 1] = downQueue.getSquaredWaitingTimeSum()
    #
    #     pm = np.stack([passengerInHall[0], passengerInHall[1], sumOfSquaredWaitingTime[0], sumOfSquaredWaitingTime[1]], axis=1)
    #
    #     return pm

    # def load_dispatcher(self):  # dispatcher_mode, RL only here
    #     if self.args.dispatcher_mode == 'RL':
    #         if self.mode == 'test':
    #             self.logger.info('Agent need to be loaded for test')
    #             dispatcher = {}
    #             dispatcher['UpPeak'] = DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
    #             dispatcher['UpPeak'].qn.load_state_dict(torch.load('saved_agent_uppeak.pt'))
    #             dispatcher['UpPeak'].qn.eval()
    #             dispatcher['InterFloor'] = DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
    #             dispatcher['InterFloor'].qn.load_state_dict(torch.load('saved_agent_interfloor.pt'))
    #             dispatcher['InterFloor'].qn.eval()
    #             dispatcher['LunchPeak'] = DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
    #             dispatcher['LunchPeak'].qn.load_state_dict(torch.load('saved_agent_lunchpeak.pt'))
    #             dispatcher['LunchPeak'].qn.eval()
    #             dispatcher['DownPeak'] = DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
    #             dispatcher['DownPeak'].qn.load_state_dict(torch.load('saved_agent_downpeak.pt'))
    #             dispatcher['DownPeak'].qn.eval()
    #             return dispatcher
    #         elif self.mode == 'train':
    #             self.logger.info('Agent need to be trained')
    #             return DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
    #         else:
    #             self.logger.info('Agent need to be loaded for more training')
    #             dispatcher = DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
    #             dispatcher.qn.load_state_dict(torch.load('saved_agent_lunchpeak.pt'))
    #             return dispatcher

    def load_dispatcher(self):  # dispatcher_mode, RL only here
        if self.mode == 'test':
            self.logger.info('Agent need to be loaded for test')
            dispatcher = DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
            dispatcher.qn.load_state_dict(torch.load('saved_agent_test.pt'))
            dispatcher.qn.eval()
            return dispatcher
        elif self.mode == 'train':
            self.logger.info('Agent need to be trained')
            return DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
        else:
            self.logger.info('Agent need to be loaded for more training')
            dispatcher = DQNAgent(args=self.args, state_dim=[20, 20], action_dim=20, con=self)
            dispatcher.qn.load_state_dict(torch.load('saved_agent.pt'))
            return dispatcher

    def create_floors(self):
        # Create floor objects and store them in a dictionary
        self.floor_map = {floor: Floor(floor, self) for floor in range(1, self.num_floor + 1)}

        # Set the down and up floors for each floor object
        for floor in self.floor_map.values():
            if floor.floor_id - 1 in self.floor_map:
                floor.down_floor = self.floor_map[floor.floor_id - 1]
            if floor.floor_id + 1 in self.floor_map:
                floor.up_floor = self.floor_map[floor.floor_id + 1]

    def create_passenger_generators(self):
        arrival_rate_list = []
        prior_arrival_rate_list = []
        for traffic_type in ['in coming', 'inter floor', 'out going']:
        # for traffic_type in ['in coming', 'out going']:
            if self.traffic_pattern == 'AllInOne':
                arrival_rate_list = self.arrival_rate[traffic_type]
                prior_arrival_rate_list = self.prior_arrival_rate[traffic_type]
            elif self.traffic_pattern == 'UpPeak':
                arrival_rate_list = self.arrival_rate[traffic_type][:12]
                prior_arrival_rate_list = self.prior_arrival_rate[traffic_type][:12]
            elif self.traffic_pattern == 'InterFloor':
                arrival_rate_list = self.arrival_rate[traffic_type][12:18] + self.arrival_rate[traffic_type][30:36]
                prior_arrival_rate_list = self.prior_arrival_rate[traffic_type][12:18] + self.prior_arrival_rate[traffic_type][30:36]
            elif self.traffic_pattern == 'LunchPeak':
                arrival_rate_list = self.arrival_rate[traffic_type][18:30]
                prior_arrival_rate_list = self.prior_arrival_rate[traffic_type][18:30]
            elif self.traffic_pattern == 'DownPeak':
                arrival_rate_list = self.arrival_rate[traffic_type][36:]
                prior_arrival_rate_list = self.prior_arrival_rate[traffic_type][36:]
            self.pg_list.append(PassengerGenerator(self, self.emq, arrival_rate_list,
                                                   prior_arrival_rate_list,
                                                   self.population, traffic_type))

    def create_elevator_cars(self):
        for i in range(1, self.num_elevator + 1):
            pos = [(0, 0)]
            for j in range(self.num_floor + 1, 1, -1):
                x = 440 + i * 200
                y = j * 150 - 150
                pos.append((x, y))
            self.car_map[i] = ElevatorCar(i, self.num_floor, stop_pos=pos, capacity=self.capacity, con=self)

    def Tnow(self):
        return self.emq.Tnow

    def append_job_stat(self, passenger):
        self.job_stat.append(passenger)
        self.output_handler.append_passenger(passenger)
        self.job_stat.send_stat()
        self.avg_util(self.Tnow())

    def get_util(self, t):
        temp_sum = 0.0
        for i in range(1, self.num_elevator + 1):
            temp_sum += self.car_map[i].util.timeAvg(t)
        temp_sum /= self.num_elevator
        return temp_sum

    def avg_util(self, t):
        util = self.get_util(t)
        self.emq.sendMonMsg(f"widget vehUtil text {util * 100:.2f}%")

    def reset_util(self, t):
        for i in range(1, self.num_elevator + 1):
            self.car_map[i].util.reset(t, self.car_map[i].state.working())

    def reset_stat(self):
        self.job_stat.reset()
        self.reset_util(self.Tnow())

    def write_stat(self, file_name):
        with open(file_name, 'a') as fi:
            fi.write(f"t_now = {self.Tnow():.4f}\n")
            wt_avg, wt_max, jt_avg, jt_max, tt_avg, tt_max = self.job_stat.write_stat(fi)
            util = self.get_util(self.Tnow())
            fi.write(f"Elevator utilization: {util * 100:.2f}%\n")
            self.output_handler.append_stats([wt_avg, wt_max, jt_avg, jt_max, tt_avg, tt_max, util])

        if self.args.mode != 'test':
            awt_last_day = wt_avg
            day_index = self.Tnow() // 86400
            new_lr = self.dispatcher.linear_lr_decay(day_index)
            self.args.run.log({'Average Waiting Time(Day)': awt_last_day,
                               'Average Journey Time': jt_avg,
                               'Learning Rate': new_lr,
                               'Day Index': day_index})

            self.logger.info(f'dayIndex: {day_index}, '
                             f'awt_last_day: {awt_last_day}, ajt_last_day: {jt_avg},  lr: {new_lr}')

    def send_mon_qsize(self, floor_queue):
        self.emq.sendMonMsg(f"queue Floor.{floor_queue.type}{floor_queue.floor_id} {len(floor_queue.queue)}")

    def send_mon_car_id(self, floor_queue, car_id=None):
        self.emq.sendMonMsg(f"text Floor.c{floor_queue.type}{floor_queue.floor_id} {car_id}")

    def collect_request(self, e):
        floor_queue = e.param
        floor_queue.press_time = self.Tnow()

        type_id = int(e.msg == 'up')
        request_floor_id = floor_queue.floor_id
        self.request_floor[type_id][request_floor_id] = request_floor_id
        for i in range(1, self.num_elevator + 1):
            car = self.car_map[i]
            if car.state == CarState.IDLE:
                if car.prev_floor.floor_id == request_floor_id and floor_queue.if_car_stopped == 0:
                    if floor_queue.type == 'down':
                        car.set_state(CarState.MOVING_DOWN)
                    else:
                        car.set_state(CarState.MOVING_UP)
                    floor_queue.if_car_stopped = car.id
                    board_time = truncnorm.rvs(0.6, 6, loc=1, scale=1, size=min(len(floor_queue.queue), car.capacity),
                                               random_state=get_random_seed())
                    board_time_sum = board_time.sum()
                    self.emq.scheduleEvtMsg4(board_time_sum + car.door_time, car, floor_queue, 'passenger board',
                                             param=(car, board_time))  # consider door time
                    return  # only awake one car
                else:
                    car.instantEvtMsg(car, 'decide next move', param=car)  # awake all cars
                    # return  # only awake one car

    def processEvtMsg(self, e):  # e.param is a floorQueue, from which the request is generated
        if e.msg == 'down' or e.msg == 'up':  # controller receive request
            self.collect_request(e)
        elif e.msg == 'passenger leave':
            passenger = e.param
            self.append_job_stat(passenger)
        elif e.msg == 'resetStat':
            self.reset_stat()
        elif e.msg == 'writeStat':
            self.write_stat(e.param)
        elif e.msg == 'update day index':
            self.update_day_index()
        elif e.msg == 'saveState':
            self.emq.save_state(e.param)
        elif e.msg == 'checkModel':
            self.output_handler.check_model()
        elif e.msg == 'startMonLog':
            self.emq.setMonLog(open(e.param, "w"))
        elif e.msg == 'endMonLog':
            self.emq.setMonLog(None)
        elif e.msg == 'check':
            self.emq.scheduleEvtMsg4(self.check_interval, self, self, "check")
        elif e.msg == 'quit':
            self.logger.info(f"Quit requested at {self.Tnow()}")
            self.logger.info(f"Simulation time is {self.Tnow()} vs Real time is {time.time() - self.emq.timeSince}")
            self.output_handler.prepare_quit()
            self.emq.prepareQuit()
            exit()
        else:
            super().processEvtMsg(e)


class ElevatorEvtMsgQueue(EvtMsgQueue):
    def __init__(self, name):
        super().__init__(name)
        self.clockName = "elevatorClock"
