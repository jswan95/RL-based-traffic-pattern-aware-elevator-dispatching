import random
import numpy as np
from SumTree import SumTree
from collections import deque


class PatternMemory:
    def __init__(self, args, pattern_type):
        self.pattern_type = pattern_type
        self.args = args
        self.capacity = int(self.args.memory_capacity / self.args.num_task)
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
        self.pattern_memories = self.initialize_buffers()

    def get_beta(self):
        return self.pattern_memories[1].beta

    def initialize_buffers(self):
        pattern_memories = {}
        for i in range(1, 1 + self.args.num_task):
            pattern_memories[i] = PatternMemory(self.args, i)
        return pattern_memories

    def push(self, t_now, transition):
        t_type1, t_type2 = transition[-2], transition[-1]
        self.pattern_memories[t_type1].push(transition)

    def train_start(self):
        if_train_start = True
        for i in range(1, 1 + self.args.num_task):
            if not self.pattern_memories[i].train_start():
                if_train_start = False

        return if_train_start

    def sample_experience(self, batch_size):
        mini_batch_result = []
        idxs_result = []
        is_weights_result = []
        for i in range(1, 1 + self.args.num_task):
            mini_batch, idxs, is_weights = self.pattern_memories[i].sample(batch_size)
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
