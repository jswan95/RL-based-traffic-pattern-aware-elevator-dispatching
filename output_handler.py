from job_stat import JobStat

import matplotlib.pyplot as plt
import numpy as np
import csv
import time
import torch


class OutputHandler:
    def __init__(self, args):
        self.con = None
        self.args = args
        self.overall_stat = []
        self.initialize_stats()
        self.job_stat = JobStat(self)

    def append_loss(self, loss):
        t_now = self.con.Tnow()
        time_index_half = int(t_now // 1800)
        time_index_one = int(t_now // 3600)

        self.average_loss_half[time_index_half] += loss
        self.loss_count_half[time_index_half] += 1
        self.average_loss_one[time_index_one] += loss
        self.loss_count_one[time_index_one] += 1

    def append_stats(self, stats):
        self.overall_stat.append(stats)

    def append_passenger(self, passenger):
        wt_p = passenger.get_waiting_time()
        jt_p = passenger.get_journey_time()
        tt_p = passenger.get_trip_time()

        # to show training signal
        time_index_half = int(self.con.Tnow() // 1800)
        time_index_one = int(self.con.Tnow() // 3600)
        self.average_waiting_time_half[time_index_half] += wt_p
        self.average_journey_time_half[time_index_half] += jt_p
        self.average_trip_time_half[time_index_half] += tt_p
        self.passenger_count_half[time_index_half] += 1

        self.average_waiting_time_one[time_index_one] += wt_p
        self.average_journey_time_one[time_index_one] += jt_p
        self.average_trip_time_one[time_index_one] += tt_p
        self.passenger_count_one[time_index_one] += 1

    def initialize_stats(self):
        # stats per half hour
        max_num_record = 20000
        self.average_loss_half = np.zeros(max_num_record)
        self.loss_count_half = np.zeros(max_num_record)
        self.average_waiting_time_half = np.zeros(max_num_record)
        self.average_trip_time_half = np.zeros(max_num_record)
        self.average_journey_time_half = np.zeros(max_num_record)
        self.passenger_count_half = np.zeros(max_num_record)

        # stats per hour
        self.average_loss_one = np.zeros(max_num_record)
        self.loss_count_one = np.zeros(max_num_record)
        self.average_waiting_time_one = np.zeros(max_num_record)
        self.average_trip_time_one = np.zeros(max_num_record)
        self.average_journey_time_one = np.zeros(max_num_record)
        self.passenger_count_one = np.zeros(max_num_record)

    def moving_average(self, x, w):
        return np.convolve(x, np.ones(w), 'valid') / w

    def output_pattern_figure(self, stats):
        data_collections = {}
        count_collections = {}
        for pattern in ['UpPeak', 'InterFloor', 'LunchPeak', 'DownPeak']:
            data_collections[pattern] = []
            count_collections[pattern] = []

        for i in range(len(stats[1])):
            hour = i % 24
            data = stats[1][i]
            count = stats[2][i]
            if hour in [0, 1, 2, 3, 4, 5]:
                data_collections['UpPeak'].append(data)
                count_collections['UpPeak'].append(count)
            elif hour in [6, 7, 8, 15, 16, 17]:
                data_collections['InterFloor'].append(data)
                count_collections['InterFloor'].append(count)
            elif hour in [9, 10, 11, 12, 13, 14]:
                data_collections['LunchPeak'].append(data)
                count_collections['LunchPeak'].append(count)
            else:
                data_collections['DownPeak'].append(data)
                count_collections['DownPeak'].append(count)

        for pattern in ['UpPeak', 'InterFloor', 'LunchPeak', 'DownPeak']:
            data_collections_hour = [sum(data_collections[pattern][i:i + 2])
                                     for i in range(0, len(data_collections[pattern]), 2)]
            count_collections_hour = [sum(count_collections[pattern][i:i + 2])
                                      for i in range(0, len(count_collections[pattern]), 2)]
            avg_data = np.array([data / count for data, count in zip(data_collections_hour, count_collections_hour)])
            np.save(f'result_folder/{pattern}-{stats[0]}.npy', avg_data)

            plt.plot(self.moving_average(avg_data, 12), c='red')
            plt.xlabel('Training Hour')
            plt.ylabel(stats[0])
            plt.title(f'{stats[0]} (AllInOne-{pattern}) v.s. Hours')
            plt.savefig(f'result_folder/AllInOne-{pattern}-{stats[0]}.png')
            plt.close()

    def output_allinone_analysis(self):
        passenger_count_half = self.passenger_count_half[np.nonzero(self.loss_count_half)]
        awt_half = self.average_waiting_time_half[np.nonzero(self.loss_count_half)]
        ajt_half = self.average_journey_time_half[np.nonzero(self.loss_count_half)]
        loss_count_half = self.loss_count_half[np.nonzero(self.loss_count_half)]
        al_half = self.average_loss_half[np.nonzero(self.loss_count_half)]
        for stats in [('Average Waiting Time', awt_half, passenger_count_half),
                      ('Average Journey Time', ajt_half, passenger_count_half),
                      ('Loss', al_half, loss_count_half)]:
            self.output_pattern_figure(stats)

    def output_result(self):
        head = [' ', 'Waiting Time', 'Waiting Time Max', 'Time in Car', 'Time in Car Max', 'Total Time',
                'Total Time Max', 'Elevator Utilization']
        with open(f"result_folder/result_{self.args.dispatcher_mode}.csv", 'w', newline='') as result_file:
            writer = csv.writer(result_file)
            writer.writerow(head)
            overall_stat_array = np.array(self.overall_stat)
            avg_row = np.mean(overall_stat_array, axis=0)
            std_row = np.std(overall_stat_array, axis=0)
            for i in self.overall_stat:
                writer.writerow(['Data Row'] + i)
            writer.writerow(['Avg. Row'] + list(avg_row))
            writer.writerow(['Std. Row'] + list(std_row))
            writer.writerow(
                [f"Simulation time is {self.con.Tnow():.4f} vs Real time is {time.time() - self.con.emq.timeSince:.4f}"])

        print(f'num_decisions: {self.con.decision_num_count}, total time {self.con.decision_time}, average time {self.con.decision_time / self.con.decision_num_count}')

    def output_figure(self):
        if self.args.mode != 'test':
            day_index = self.con.day_index
            passenger_count_one = self.passenger_count_one[np.nonzero(self.loss_count_one)]
            awt_one = self.average_waiting_time_one[np.nonzero(self.loss_count_one)] / passenger_count_one
            ajt_one = self.average_journey_time_one[np.nonzero(self.loss_count_one)] / passenger_count_one
            att_one = self.average_trip_time_one[np.nonzero(self.loss_count_one)] / passenger_count_one
            loss_count_one = self.loss_count_one[np.nonzero(self.loss_count_one)]
            al_one = self.average_loss_one[np.nonzero(self.loss_count_one)] / loss_count_one

            np.save('result_folder/pc.npy', passenger_count_one)
            np.save('result_folder/awt.npy', awt_one)
            np.save('result_folder/ajt.npy', ajt_one)
            np.save('result_folder/att.npy', att_one)
            np.save('result_folder/loss.npy', al_one)

            total_awt = awt_one.copy()
            total_ajt = ajt_one.copy()
            total_att = att_one.copy()
            total_al = al_one.copy()

            moving_average_step = 12
            awt = self.moving_average(total_awt, moving_average_step)
            ajt = self.moving_average(total_ajt, moving_average_step)
            att = self.moving_average(total_att, moving_average_step)
            al = self.moving_average(total_al, moving_average_step)

            # output total average loss
            plt.plot(al, color='r')
            plt.xlabel('# of hours')
            plt.ylabel('Loss')
            plt.title('Average Loss v.s. Hours')
            plt.savefig(f'result_folder/train_loss_{day_index}.png')
            plt.close()

            # output awt
            plt.plot(awt, color='r')
            plt.xlabel('# of hours')
            plt.ylabel('Average Waiting Time')
            plt.title('Average Waiting Time v.s. Hours')
            plt.savefig(f'result_folder/train_awt_{day_index}.png')
            plt.close()

            # output ajt
            plt.plot(ajt, color='y')
            plt.xlabel('# of hours')
            plt.ylabel('Average Journey Time')
            plt.title('Average Journey Time v.s. Hours')
            plt.savefig(f'result_folder/train_ajt_{day_index}.png')
            plt.close()

            # output att
            plt.plot(att, color='b')
            plt.xlabel('# of hours')
            plt.ylabel('Average Trip Time')
            plt.title('Average Trip Time v.s. Hours')
            plt.savefig(f'result_folder/train_att_{day_index}.png')
            plt.close()

            # if self.args.traffic_pattern == 'AllInOne':
            #     self.output_allinone_analysis()  # output different patterns of all in one pattern
            #     self.con.dispatcher.memory.output_stored_ratio()  # output the transitions rate change
            #     self.con.dispatcher.output_sampled_ratio()

    def save_model(self):
        if self.args.mode != 'test':
            torch.save(self.con.dispatcher.qn.state_dict(), f'result_folder/saved_agent_{self.con.day_index}.pt')

    def check_model(self):
        self.output_figure()
        self.save_model()

    def prepare_quit(self):
        self.check_model()
        self.output_result()
