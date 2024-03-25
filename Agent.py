import torch
import torch.nn as nn
import math
from Memory_task import Memory
import numpy as np
import matplotlib.pyplot as plt
from utils import get_random_seed
from pcgrad import PCGrad
import time


class QNet_Conv1d(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(QNet_Conv1d, self).__init__()
        self.conv1 = nn.Sequential(nn.Conv1d(16, 32, kernel_size=5, stride=1, padding=2),
                                   nn.ReLU())  # output shape: 32 * 20
        self.pooling1 = nn.MaxPool1d(kernel_size=2)  # output shape: 32 * 10
        self.conv2 = nn.Sequential(nn.Conv1d(32, 64, kernel_size=5, stride=1, padding=2),
                                   nn.ReLU())  # output shape: 64 * 10
        self.pooling2 = nn.MaxPool1d(kernel_size=2)  # output shape: 64 * 5
        self.conv3 = nn.Sequential(nn.Conv1d(64, 128, kernel_size=5, stride=1), nn.ReLU())  # output shape: 128 * 1
        self.fc_rate = nn.Sequential(nn.Linear(40, 128), nn.ReLU())
        self.fc = nn.Sequential(nn.Linear(256, 128), nn.ReLU(), nn.Linear(128, action_dim))

    # def forward(self, x):
    #     out = self.conv1(x)
    #     out = self.pooling1(out)
    #     out = self.conv2(out)
    #     out = self.pooling2(out)
    #     out = self.conv3(out)
    #     out = self.fc(out.reshape(out.size(0), -1))
    #     return out

    def forward(self, x):
        x_features = x[:, :16, :]
        x_rates = x[:, 16:, :]
        x_rates = x_rates.reshape(x.size(0), -1)
        x_rates = self.fc_rate(x_rates)
        out = self.conv1(x_features)
        out = self.pooling1(out)
        out = self.conv2(out)
        out = self.pooling2(out)
        out = self.conv3(out)
        out = out.reshape(out.size(0), -1)
        out = torch.cat((out, x_rates), 1)
        out = self.fc(out)
        return out


class DuelingQNet(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(DuelingQNet, self).__init__()
        self.conv1 = nn.Sequential(nn.Conv1d(18, 64, kernel_size=5, stride=1, padding=2), nn.ReLU())
        self.pooling1 = nn.MaxPool1d(kernel_size=2)
        self.conv2 = nn.Sequential(nn.Conv1d(64, 128, kernel_size=5, stride=1, padding=2), nn.ReLU())
        self.pooling2 = nn.MaxPool1d(kernel_size=2)
        self.conv3 = nn.Sequential(nn.Conv1d(128, 256, kernel_size=5, stride=1), nn.ReLU())
        self.fc_adv = nn.Sequential(nn.Linear(256, 32), nn.ReLU(), nn.Linear(32, action_dim))
        self.fc_val = nn.Sequential(nn.Linear(256, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):
        out = self.conv1(x)
        out = self.pooling1(out)
        out = self.conv2(out)
        out = self.pooling2(out)
        out = self.conv3(out)
        out = out.reshape(out.size(0), -1)
        val = self.fc_val(out)
        adv = self.fc_adv(out)
        result = val + adv - adv.mean(dim=1, keepdim=True)  # important to set dim=1 and keepdim=True
        return result


class DQNAgent(object):
    def __init__(self, args, state_dim, action_dim, con):
        self.con = con
        self.args = args
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.batch_size = args.batch_size
        self.memory = Memory(self.args)
        self.initialize_nets()
        self.initial_learning_rate = args.lr
        self.optimizer = PCGrad(torch.optim.Adam(self.qn.parameters(), lr=self.initial_learning_rate))
        self.MSELoss = nn.MSELoss()
        # self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(self.optimizer, factor=self.args.df_lr,
        #                                                             mode='min', patience=args.patience,
        #                                                             cooldown=args.cool_down, min_lr=args.min_lr)
        self.target_update_step = args.target_update_step
        self.beta = args.beta
        self.train_count = 0
        self.tau = args.tau
        self.epsilon = args.epsilon
        self.decay_rate = args.decay_rate  # epsilon decay rate
        self.epsilon_min = args.epsilon_min

        self.sampled_up = np.zeros(20000)
        self.sampled_inter = np.zeros(20000)
        self.sampled_lunch = np.zeros(20000)
        self.sampled_down = np.zeros(20000)

        self.sampled_car_up = np.zeros(20000)
        self.sampled_car_down = np.zeros(20000)
        self.sampled_car_idle = np.zeros(20000)

        self.total_sampled = np.zeros(20000)

        self.time_gc = 0.
        self.time_proj = 0.
        self.time_gs = 0.

    def forward(self, x):
        return self.qn(x)

    def initialize_nets(self):
        if self.args.dueling:
            self.qn = DuelingQNet(self.state_dim, self.action_dim).to(self.args.device)
            self.target_qn = DuelingQNet(self.state_dim, self.action_dim).to(self.args.device)
        else:
            self.qn = QNet_Conv1d(self.state_dim, self.action_dim).to(self.args.device)
            self.target_qn = QNet_Conv1d(self.state_dim, self.action_dim).to(self.args.device)
        self.hard_update(self.target_qn, self.qn)
        self.target_qn.eval()

    def linear_lr_decay(self, current_day):
        training_days = self.args.training_days

        initial_lr = self.args.lr
        min_lr = self.args.min_lr

        new_lr = initial_lr - (initial_lr - min_lr) * (current_day / training_days)

        for param_group in self.optimizer._optim.param_groups:
            param_group['lr'] = new_lr

        return new_lr

    def hard_update(self, target, source):
        for target_param, source_param in zip(target.parameters(), source.parameters()):
            target_param.data.copy_(source_param.data)

    def soft_update(self, target, source):
        for target_param, source_param in zip(target.parameters(), source.parameters()):
            target_param.data.copy_(target_param.data * (1.0 - self.tau) + source_param.data * self.tau)

    def output_sampled_ratio(self):
        nonzero_element = np.nonzero(self.total_sampled)
        total_sampled = self.total_sampled[nonzero_element]
        plt.stackplot(range(1, 1 + np.count_nonzero(self.total_sampled)),
                      self.sampled_up[nonzero_element] / total_sampled,
                      self.sampled_inter[nonzero_element] / total_sampled,
                      self.sampled_lunch[nonzero_element] / total_sampled,
                      self.sampled_down[nonzero_element] / total_sampled,
                      labels=['Up Peak', 'InterFloor', 'Lunch Peak', 'Down Peak'])

        plt.title('Ratio of Transitions Sampled (By traffic pattern) v.s. Hours')
        plt.xlabel('# of hours')
        plt.ylabel('Ratio')
        plt.legend(loc='upper left')
        plt.savefig(f'result_folder/transition sampled (By traffic pattern).png')
        plt.close()

        plt.stackplot(range(1, 1 + np.count_nonzero(self.total_sampled)),
                      self.sampled_car_up[nonzero_element] / total_sampled,
                      self.sampled_car_down[nonzero_element] / total_sampled,
                      self.sampled_car_idle[nonzero_element] / total_sampled,
                      labels=['Up', 'Down', 'Idle'])

        plt.title('Ratio of Transitions Sampled (By car state) v.s. Hours')
        plt.xlabel('# of hours')
        plt.ylabel('Ratio')
        plt.legend(loc='upper left')
        plt.savefig(f'result_folder/transition sampled (By car state).png')
        plt.close()

    def store_sampled_types(self, types1, types2):
        time_idx = int(self.con.Tnow() // 3600)
        for t_type in types1:
            if t_type == 1:
                self.sampled_up[time_idx] += 1
            elif t_type == 2:
                self.sampled_inter[time_idx] += 1
            elif t_type == 3:
                self.sampled_lunch[time_idx] += 1
            else:
                self.sampled_down[time_idx] += 1
        for t_type in types2:
            if t_type == 1:
                self.sampled_car_down[time_idx] += 1
            elif t_type == 2:
                self.sampled_car_up[time_idx] += 1
            else:
                self.sampled_car_idle[time_idx] += 1
        self.total_sampled[time_idx] += self.batch_size

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon * self.decay_rate, self.epsilon_min)

    # def train_model(self, double_dqn):
    #     losses = []
    #     self.train_count += 1
    #     for pattern in range(1, 1 + self.args.num_task):
    #         mini_batch = self.memory.pattern_memories[pattern].sample_experience(int(self.batch_size / self.args.num_task))
    #         state, action, reward, next_state, next_available_actions, time_interval, types1, types2 = mini_batch
    #
    #         state = torch.stack(state, dim=0).to(self.args.device)
    #         next_state = torch.stack(next_state, dim=0).to(self.args.device)
    #         reward = torch.tensor(reward, dtype=torch.float32).to(self.args.device)
    #         action = torch.tensor(action, dtype=torch.long).to(self.args.device)
    #
    #         q_values = self.qn(state).gather(1, action.unsqueeze(1))
    #         target_next_q_values = self.target_qn(next_state)
    #         if double_dqn:
    #             next_q_values = self.qn(next_state)  # double DQN
    #         else:
    #             next_q_values = target_next_q_values  # just DQN
    #
    #         expected_q_value = []
    #         for i in range(int(self.batch_size / self.args.num_task)):
    #             assert len(next_available_actions[i]) > 1
    #             next_action = next_available_actions[i][torch.argmin(next_q_values[i][next_available_actions[i]])]
    #             expected_q_value.append(
    #                 reward[i] + math.exp(-self.beta * time_interval[i]) * target_next_q_values[i][next_action])
    #         expected_q_values = (torch.stack(expected_q_value, dim=0)).unsqueeze(1)
    #
    #         loss = ((q_values - expected_q_values.detach()).squeeze().pow(2)).mean()
    #         losses.append(loss)
    #
    #     self.optimizer.zero_grad()
    #     # loss.backward()
    #     before_gs = time.time()
    #     gradient_ct, gs_t = self.optimizer.pc_backward(losses)
    #     gs_time = time.time() - before_gs
    #     self.time_gc += gradient_ct
    #     self.time_proj += gs_t
    #     self.time_gs += gs_time
    #     if self.train_count == 1000:
    #         print(f'Gradient surgery time: {self.time_gs} \n'
    #               f'Gradient computation time: {self.time_gc} \n'
    #               f'Gradient projection time: {self.time_proj} \n')
    #         exit()
    #     self.optimizer.step()
    #
    #     if self.args.soft_update:
    #         self.soft_update(self.target_qn, self.qn)
    #     else:
    #         if self.train_count % self.target_update_step == 0:
    #             self.hard_update(self.target_qn, self.qn)
    #
    #     self.decay_epsilon()
    #     return sum(losses).item()

    def train_model(self, double_dqn):
        self.train_count += 1
        state_list = []
        next_state_list = []
        reward_list = []
        action_list = []
        next_action_list = []
        time_interval_list = []
        for pattern in range(1, 1 + self.args.num_task):
            mini_batch = self.memory.pattern_memories[pattern].sample_experience(int(self.batch_size/self.args.num_task))
            state, action, reward, next_state, next_available_actions, time_interval, types1, types2 = mini_batch
            state_list.append(state)
            next_state_list.append(next_state)
            reward_list.append(reward)
            action_list.append(action)
            next_action_list.extend(next_available_actions)
            time_interval_list.extend(time_interval)

        state = torch.concat([torch.stack(t, dim=0) for t in state_list], dim=0).to(self.args.device)
        next_state = torch.concat([torch.stack(t, dim=0) for t in next_state_list], dim=0).to(self.args.device)
        reward = torch.tensor([item for tup in reward_list for item in tup], dtype=torch.float32).to(self.args.device)
        action = torch.tensor([item for tup in action_list for item in tup], dtype=torch.long).to(self.args.device)

        q_values = self.qn(state).gather(1, action.unsqueeze(1))
        target_next_q_values = self.target_qn(next_state)
        if double_dqn:
            next_q_values = self.qn(next_state)  # double DQN
        else:
            next_q_values = target_next_q_values  # just DQN

        expected_q_value = []
        for i in range(int(self.batch_size)):
            assert len(next_action_list[i]) > 1
            next_action = next_action_list[i][torch.argmin(next_q_values[i][next_action_list[i]])]
            expected_q_value.append(
                reward[i] + math.exp(-self.beta * time_interval_list[i]) * target_next_q_values[i][next_action])
        expected_q_values = (torch.stack(expected_q_value, dim=0)).unsqueeze(1)

        loss = ((q_values - expected_q_values.detach()).squeeze().pow(2))

        losses = []
        num_per_task = int(self.batch_size / self.args.num_task)
        for i in range(self.args.num_task):
            losses.append((loss[i * num_per_task: i*num_per_task + num_per_task]).mean())
        # for i in range(self.args.batch_size):
        #     losses.append(loss[i])

        self.optimizer.zero_grad()
        # loss.backward()
        # before_gs = time.time()
        gradient_ct, gs_t = self.optimizer.pc_backward(losses)
        self.optimizer.pc_backward(losses)
        # gs_time = time.time() - before_gs
        # self.time_gc += gradient_ct
        # self.time_proj += gs_t
        # self.time_gs += gs_time
        # if self.train_count == 1000:
        #     print(f'Gradient surgery time: {self.time_gs} \n'
        #           f'Gradient computation time: {self.time_gc} \n'
        #           f'Gradient projection time: {self.time_proj} \n')
        #     exit()
        self.optimizer.step()
        loss = sum(losses).item()

        if self.args.soft_update:
            self.soft_update(self.target_qn, self.qn)
        else:
            if self.train_count % self.target_update_step == 0:
                self.hard_update(self.target_qn, self.qn)

        self.decay_epsilon()

        # print(f'# of training: {self.train_count}; '
        #       f'training loss: {loss}; '
        #       f'epsilon: {self.epsilon}; '
        #       f'beta: {self.memory.get_beta() if self.args.prioritized_er else None}')

        return loss

    # def train_model(self, double_dqn):
    #     self.train_count += 1
    #
    #     if self.args.prioritized_er:
    #         mini_batch, idxs, is_weights = self.memory.sample_experience(self.batch_size)
    #         state, action, reward, next_state, next_available_actions, time_interval, types1, types2 = zip(*mini_batch)
    #     else:
    #         state, action, reward, next_state, next_available_actions, time_interval, types1, types2 \
    #             = self.memory.sample_experience(self.batch_size)
    #     self.store_sampled_types(types1, types2)
    #
    #     state = torch.stack(state, dim=0).to(self.args.device)
    #     next_state = torch.stack(next_state, dim=0).to(self.args.device)
    #     reward = torch.tensor(reward, dtype=torch.float32).to(self.args.device)
    #     action = torch.tensor(action, dtype=torch.long).to(self.args.device)
    #
    #     # state = torch.stack(state, dim=0)
    #     # next_state = torch.stack(next_state, dim=0)
    #     # reward = torch.tensor(reward, dtype=torch.float32)
    #     # action = torch.tensor(action, dtype=torch.long)
    #
    #     q_values = self.qn(state).gather(1, action.unsqueeze(1))
    #     target_next_q_values = self.target_qn(next_state)
    #     if double_dqn:
    #         next_q_values = self.qn(next_state)  # double DQN
    #     else:
    #         next_q_values = target_next_q_values  # just DQN
    #
    #     expected_q_value = []
    #     for i in range(self.batch_size):
    #         assert len(next_available_actions[i]) > 1
    #         next_action = next_available_actions[i][torch.argmin(next_q_values[i][next_available_actions[i]])]
    #         expected_q_value.append(
    #             reward[i] + math.exp(-self.beta * time_interval[i]) * target_next_q_values[i][next_action])
    #     expected_q_values = (torch.stack(expected_q_value, dim=0)).unsqueeze(1)
    #
    #     if self.args.prioritized_er:
    #         errors = torch.abs(q_values - expected_q_values.detach()).cpu().data.numpy()
    #         # update priority
    #         # for i in range(self.batch_size):
    #         #     idx = idxs[i]
    #         #     self.memory.update(idx, errors[i])
    #         self.memory.update(idxs, errors)
    #         is_weights = torch.FloatTensor(is_weights).to(self.args.device)
    #         loss = ((q_values - expected_q_values.detach()).squeeze().pow(2) * is_weights).mean()
    #     else:
    #         loss = self.MSELoss(q_values, expected_q_values.detach())
    #
    #     self.optimizer.zero_grad()
    #     # loss.backward()
    #     self.optimizer.pc_backward(loss)
    #     self.optimizer.step()
    #     loss = loss.item()
    #
    #     if self.args.soft_update:
    #         self.soft_update(self.target_qn, self.qn)
    #     else:
    #         if self.train_count % self.target_update_step == 0:
    #             self.hard_update(self.target_qn, self.qn)
    #
    #     self.decay_epsilon()
    #
    #     print(f'# of training: {self.train_count}; '
    #           f'training loss: {loss}; '
    #           f'epsilon: {self.epsilon}; '
    #           f'beta: {self.memory.get_beta() if self.args.prioritized_er else None}')
    #
    #     return loss

    def epsilon_greedy(self, q_value, action_config):
        available_actions = action_config[1]

        if self.args.mode == 'test':
            epsilon = 0  # greedily select when test
        else:  # train, continue train ...
            epsilon = self.epsilon

        rng = np.random.RandomState(get_random_seed())
        p = rng.rand()
        if p < epsilon:
            rng = np.random.RandomState(get_random_seed())
            action = int(rng.choice([0, 1, 2, 3, 4], 1, p=available_actions / available_actions.sum()))
        else:
            car_id = action_config[0] - 1
            q_value = q_value[car_id * 5: car_id * 5 + 5]
            action = np.nonzero(available_actions)[0][torch.argmin(q_value[np.nonzero(available_actions)])]

        # 0: stop at up floor; 1: stop at down floor; 2: pass up floor; 3: pass down floor; 4: stay
        # Return the chosen action
        return action

    def get_action(self, state, action_config):
        with torch.no_grad():
            q_value = self.qn(state).squeeze()
            action = self.epsilon_greedy(q_value, action_config)
        return action
