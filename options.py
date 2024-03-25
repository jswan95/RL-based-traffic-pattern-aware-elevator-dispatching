import argparse


def get_options():
    parser = argparse.ArgumentParser(description='Elevator Control')
    parser.add_argument('--num-floor', type=int, default=20, help='Number of floors')
    parser.add_argument('--num-elevator', type=int, default=4, help='Number of Elevators')
    parser.add_argument('--population', type=int, default=1200, help='Number of population')
    parser.add_argument('--mon', type=bool, default=False, help='If run with animation')
    parser.add_argument('--double-dqn', type=bool, default=True, help='If train with double DQN')
    parser.add_argument('--dueling', type=bool, default=True, help='If train with dueling')
    parser.add_argument('--dispatcher-mode', type=str, default='RL', help='Dispatching algorithm')
    parser.add_argument('--mode', type=str, default='test', choices=['train', 'test', 'train more'],
                        help='train, test, or continue training agent')
    parser.add_argument('--car-capacity', type=int, default=20, help='Capacity of elevator car')
    parser.add_argument('--memory-capacity', type=int, default=100000, help='Capacity of replay buffer')
    parser.add_argument('--lr', type=float, default=5e-5, help='Learning rate')
    parser.add_argument('--min-lr', type=float, default=1e-6, help='Minimum learning rate')
    parser.add_argument('--df-lr', type=float, default=0.8, help='Decay factor of learning rate')
    parser.add_argument('--beta', type=float, default=0.01, help='discount rate')
    parser.add_argument('--batch-size', type=int, default=128, help='Batch size')
    parser.add_argument('--patience', type=int, default=5, help='Patience for learning rate scheduler')
    parser.add_argument('--cool-down', type=int, default=5, help='cool down for learning rate scheduler')
    parser.add_argument('--training-days', type=int, default=320, help='Number of days to train')
    parser.add_argument('--test-days', type=int, default=6, help='Number of days to test')
    parser.add_argument('--traffic-pattern', type=str, default='AllInOne',
                        choices=['AllInOne', 'UpPeak', 'InterFloor', 'LunchPeak', 'DownPeak'], help='Traffic pattern')
    parser.add_argument('--offset-time', type=int, default=43200, help='Warming up time')
    parser.add_argument('--seed', type=int, default=101, help='Random seed')
    parser.add_argument('--disable-cuda', type=bool, default=True, help='Disable CUDA')
    parser.add_argument('--beta-increment', type=float, default=1e-5, help='increment per sampling for beta')
    parser.add_argument('--per-beta', type=float, default=0.4, help='initial beta for PER')
    parser.add_argument('--per-alpha', type=float, default=0.6, help='initial alpha for PER')
    parser.add_argument('--prioritized-er', type=bool, default=False, help='if use prioritized experience replay')
    parser.add_argument('--e', type=float, default=0.01, help='constant to prevent priority being 0')
    parser.add_argument('--rr', type=str, default='rr1', choices=['rr0, rr1, rr2'], help='reward rate')
    parser.add_argument('--soft-update', type=bool, default=True, help='if use prioritized experience replay')
    parser.add_argument('--jt-reward', type=bool, default=False, help='if include journey time reward')
    parser.add_argument('--reward-weight', type=float, default=0, help='weight between wt reward and jt reward')
    parser.add_argument('--target-update-step', type=int, default=20, help='Num of step to update target q net')
    parser.add_argument('--tau', type=float, default=0.01, help='Learning rate for soft update')
    parser.add_argument('--epsilon', type=float, default=1, help='initial epsilon')
    parser.add_argument('--decay-rate', type=float, default=1 - 5e-5, help='Decay rate for epsilon')
    # parser.add_argument('--c', type=float, default=0.8, help='exponential smoothing constant')
    parser.add_argument('--d', type=float, default=0, help='add to real arrival rate')
    parser.add_argument('--b', type=float, default=0, help='balance between prior and data')
    parser.add_argument('--epsilon-min', type=float, default=0.005, help='Minimum value for epsilon')
    parser.add_argument('--use-arrival-rate', type=bool, default=True, help='If use arrival rate information')
    parser.add_argument('--destination-control', type=bool, default=True,
                        help='If train under destination control setting')

    parser.add_argument('--num-task', type=int, default=8, help='Num of tasks to divide')
    return parser.parse_args()


if __name__ == "__main__":
    opts = get_options()
