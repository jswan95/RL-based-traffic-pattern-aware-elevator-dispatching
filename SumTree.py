import numpy as np


# SumTree
# a binary tree data structure where the parent’s value is the sum of its children
class SumTree:
    def __init__(self, capacity):
        self.write = 0
        self.capacity = capacity
        self.data_start = 2**((self.capacity - 1).bit_length()) - 1  # from which index to store transitions
        self.tree = np.zeros(self.data_start + self.capacity, dtype=np.float64)
        self.data = np.zeros(capacity, dtype=object)  # store experiences
        self.n_entries = 0
        self.priority_max = 1.

    # update to the root node
    def _propagate(self, idx):
        parent = (idx - 1) // 2
        left, right = 2 * parent + 1, 2 * parent + 2
        self.tree[parent] = self.tree[left] + self.tree[right]
        assert self.tree[parent] == self.tree[left] + self.tree[right]
        if parent != 0:
            self._propagate(parent)

    # find transitions on leaf node
    def _retrieve(self, idx, s):
        left = 2 * idx + 1
        right = left + 1

        if left >= len(self.tree):
            return idx

        if s <= self.tree[left]:
            return self._retrieve(left, s)
        else:
            return self._retrieve(right, s - self.tree[left])

    def total(self):
        return self.tree[0]

    # store priority and transitions
    def add(self, data):
        self.data[self.write] = data

        idx = self.write + self.data_start
        self.update(idx, self.priority_max)

        self.write += 1
        self.write %= self.capacity

        if self.n_entries < self.capacity:
            self.n_entries += 1
        assert self.total() == self.tree[self.data_start:].sum()

    # update priority
    def update(self, idx, p):
        self.tree[idx] = p
        if p > self.priority_max:
            self.priority_max = p
        self._propagate(idx)
        assert self.total() == self.tree[self.data_start:].sum()

    # get priority and transition
    def get(self, s):
        idx = self._retrieve(0, s)
        data_idx = idx - self.data_start

        return idx, self.tree[idx], self.data[data_idx]
