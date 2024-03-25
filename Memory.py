import random
import numpy as np
from SumTree import SumTree
from collections import deque
import matplotlib.pyplot as plt


class PatternMemory:
    def __init__(self, args, pattern_type):
        self.pattern_type = pattern_type
        self.args = args
        # self.capacity = int(self.args.memory_capacity / self.args.num_task)
        self.capacity = int(self.args.memory_capacity / 4)
        if self.args.prioritized_er:
            self.tree = SumTree(self.capacity)
            self.e = self.args.e
            self.alpha = self.args.per_alpha
            self.beta = self.args.per_beta
            self.beta_increment = self.args.beta_increment
        else:
            self.buffer = deque(maxlen=self.capacity)

    def sample_experience(self, batch_size):
        if self.args.prioritized_er:
            result = self.sample(batch_size)
        else:
            result = zip(*random.sample(self.buffer, batch_size))
        return result

    def sample(self, n):
        batch = []  # to store transitions
        idxs = []  # to store index of transitions in tree
        priorities = []  # to store priorities of transitions

        segment = self.tree.total() / n
        self.beta = np.min([1., self.beta + self.beta_increment])
        i = 0
        while True:
            a = segment * i
            b = segment * (i + 1)
            s = random.uniform(a, b)
            idx, p, data = self.tree.get(s)
            assert data != 0
            priorities.append(p)
            batch.append(data)
            idxs.append(idx)
            i += 1
            if i == n:
                break
        assert len(batch) == n
        sampling_probabilities = priorities / self.tree.total()
        is_weight = (self.tree.n_entries * sampling_probabilities) ** -self.beta
        is_weight /= is_weight.max()

        return batch, idxs, is_weight

    def update(self, idx, error):
        p = self._get_priority(error)
        self.tree.update(idx, p)

    def _get_priority(self, error):
        return (np.abs(error) + self.e) ** self.alpha

    def train_start(self):
        if self.args.prioritized_er:
            return self.tree.n_entries > self.args.batch_size
        else:
            return len(self.buffer) > self.args.batch_size

    def push(self, transition):
        if self.args.prioritized_er:
            self.tree.add(transition)
        else:
            self.buffer.append(transition)


class Memory:
    def __init__(self, args):
        self.args = args
        self.capacity = self.args.memory_capacity
        self.transition_count = 0.
        self.transition_count_hour = np.zeros(20000)
        self.transition_type1 = np.zeros(self.capacity)  # to track transition type
        self.transition_type2 = np.zeros(self.capacity)
        self.up_count = np.zeros(20000)
        self.lunch_count = np.zeros(20000)
        self.inter_count = np.zeros(20000)
        self.down_count = np.zeros(20000)
        self.car_up_transition = np.zeros(20000)
        self.car_down_transition = np.zeros(20000)
        self.car_idle_transition = np.zeros(20000)
        self.pattern_memories = self.initialize_buffers()

    def get_beta(self):
        return self.pattern_memories['UpPeak'].beta

    def initialize_buffers(self):
        pattern_memories = {}
        for pattern in ['UpPeak', 'InterFloor', 'LunchPeak', 'DownPeak']:
            pattern_memories[pattern] = PatternMemory(self.args, pattern)
        return pattern_memories

    def push(self, t_now, transition):
        t_type1, t_type2 = transition[-2], transition[-1]
        if t_type1:
            time_idx = int(t_now // 3600)
            transition_idx = int(self.transition_count) % self.capacity
            self.transition_type1[transition_idx] = t_type1
            self.transition_type2[transition_idx] = t_type2
            self.transition_count += 1
            self.transition_count_hour[time_idx] = min(self.capacity, self.transition_count)

            nonzero_elements1 = self.transition_type1[np.nonzero(self.transition_type1)]
            self.up_count[time_idx] = np.count_nonzero(nonzero_elements1 == 1)
            self.inter_count[time_idx] = np.count_nonzero(nonzero_elements1 == 2)
            self.lunch_count[time_idx] = np.count_nonzero(nonzero_elements1 == 3)
            self.down_count[time_idx] = np.count_nonzero(nonzero_elements1 == 4)

            nonzero_elements2 = self.transition_type2[np.nonzero(self.transition_type2)]
            self.car_down_transition[time_idx] = np.count_nonzero(nonzero_elements2 == 1)
            self.car_up_transition[time_idx] = np.count_nonzero(nonzero_elements2 == 2)
            self.car_idle_transition[time_idx] = np.count_nonzero(nonzero_elements2 == 3)
        patterns = ['UpPeak', 'InterFloor', 'LunchPeak', 'DownPeak']
        self.pattern_memories[patterns[t_type1 - 1]].push(transition)

    def train_start(self):
        return self.pattern_memories['UpPeak'].train_start() \
               and self.pattern_memories['InterFloor'].train_start() \
               and self.pattern_memories['LunchPeak'].train_start() \
               and self.pattern_memories['DownPeak'].train_start()

    def sample_experience(self, batch_size):
        mini_batch_result = []
        idxs_result = []
        is_weights_result = []
        for pattern in ['UpPeak', 'InterFloor', 'LunchPeak', 'DownPeak']:
            mini_batch, idxs, is_weights = self.pattern_memories[pattern].sample(batch_size / 4)
            mini_batch_result.extend(mini_batch)
            idxs_result.extend(idxs)
            is_weights_result.extend(is_weights)
        return mini_batch_result, idxs_result, is_weights_result

    def update(self, idxs, errors, pattern):
        for i, idx in enumerate(idxs):
            # if i < self.args.batch_size / 4:
            #     pattern = 'UpPeak'
            # elif self.args.batch_size / 4 <= i < self.args.batch_size * 2 / 4:
            #     pattern = 'InterFloor'
            # elif self.args.batch_size * 2 / 4 <= i < self.args.batch_size * 3 / 4:
            #     pattern = 'LunchPeak'
            # else:
            #     pattern = 'DownPeak'
            self.pattern_memories[pattern].update(idx, errors[i])

    def output_stored_ratio(self):
        nonzero_element = np.nonzero(self.up_count)
        # plt.plot(self.up_count[nonzero_element] / total_transition, label='Up Peak')
        # plt.plot(self.inter_count[nonzero_element] / total_transition, label='InterFloor')
        # plt.plot(self.lunch_count[nonzero_element] / total_transition, label='Lunch Peak')
        # plt.plot(self.down_count[nonzero_element] / total_transition, label='Down Peak')
        plt.stackplot(range(1, 1 + np.count_nonzero(self.up_count)),
                      self.up_count[nonzero_element] / self.transition_count_hour[nonzero_element],
                      self.inter_count[nonzero_element] / self.transition_count_hour[nonzero_element],
                      self.lunch_count[nonzero_element] / self.transition_count_hour[nonzero_element],
                      self.down_count[nonzero_element] / self.transition_count_hour[nonzero_element],
                      labels=['Up Peak', 'InterFloor', 'Lunch Peak', 'Down Peak'])

        plt.title('Ratios of Transitions Stored in Replay Buffer (By traffic pattern) v.s. Hours')
        plt.xlabel('# of hours')
        plt.ylabel('Ratio')
        plt.legend(loc='upper left')
        plt.savefig(f'result_folder/transition stored (By traffic pattern).png')
        plt.close()

        nonzero_element = np.nonzero(self.car_down_transition)
        plt.stackplot(range(1, 1 + np.count_nonzero(self.car_down_transition)),
                      self.car_up_transition[nonzero_element] / self.transition_count_hour[nonzero_element],
                      self.car_down_transition[nonzero_element] / self.transition_count_hour[nonzero_element],
                      self.car_idle_transition[nonzero_element] / self.transition_count_hour[nonzero_element],
                      labels=['Up', 'Down', 'Idle'])

        plt.title('Ratios of Transitions Stored in Replay Buffer (By car state) v.s. Hours')
        plt.xlabel('# of hours')
        plt.ylabel('Ratio')
        plt.legend(loc='upper left')
        plt.savefig(f'result_folder/transition stored (By car state).png')
        plt.close()
