import os
import logging
import json
import wandb

import numpy as np
import torch

from options import get_options
from PyDES.elevator_controller import ElevatorController, ElevatorEvtMsgQueue


def prepare_elevator_env(args):
    elevator_emq = ElevatorEvtMsgQueue('Elevator')
    elevator_emq.makeZmq(mon=args.mon, sync=True)
    ElevatorController(elevator_emq, args)
    config = f'{args.num_floor} floors-{args.num_elevator} elevators'
    args.config = config
    schedule_log_events(elevator_emq, args)
    return elevator_emq


def schedule_log_events(elevator_emq, args):
    elevator_con = elevator_emq.con
    elevator_emq.scheduleEvtMsg4(args.offset_time, elevator_con, elevator_con, "resetStat")
    if args.mode == 'test':
        days = args.test_days
    else:
        days = args.training_days
    for i in range(1, days):
        t = i * 3600 * 24 + args.offset_time
        elevator_emq.scheduleEvtMsg4(t, elevator_con,  elevator_con, "writeStat", param=f"result_folder/{args.config}-Stat.csv")
        elevator_emq.scheduleEvtMsg4(t + 0.00001, elevator_con, elevator_con, "resetStat")
        elevator_emq.scheduleEvtMsg4(t + 0.00001, elevator_con, elevator_con, "checkModel")
        # ElevatorEMQ.scheduleEvtMsg4(t, elevatorCon, elevatorCon, "saveState", param=f"{config}-State@{t}")
    elevator_emq.scheduleEvtMsg4(3600 * 24 * (days - 1) + 0.00001 + args.offset_time, elevator_con, elevator_con, "quit")
    # st, et = 15000, 16000
    # ElevatorEMQ.scheduleEvtMsg4(st, elevatorCon, elevatorCon, "startMonLog", param=f"result_folder/{config}-Mon-{st}~{et}.txt")
    # ElevatorEMQ.scheduleEvtMsg4(et, elevatorCon, elevatorCon, "endMonLog")


if __name__ == "__main__":
    args = get_options()
    np.random.seed(args.seed)
    torch.manual_seed(np.random.randint(1, 10000))

    result_folder = os.path.join(os.getcwd(), 'result_folder')  # to store result
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)

    with open(os.path.join(result_folder, 'args.json'), 'w') as f:
        json.dump(vars(args), f, indent=True)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s')

    file_handler = logging.FileHandler('result_folder/elevator_controller.log')
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    args.logger = logger

    if torch.cuda.is_available() and not args.disable_cuda:
        args.device = torch.device('cuda')
        torch.cuda.manual_seed(np.random.randint(1, 10000))
    else:
        args.device = torch.device("cpu")
    args.logger.info(f'Device is using: {args.device}')

    args.run = wandb.init(project=f'Traffic Pattern Aware ({args.traffic_pattern}-{args.population})',
                          name=f'D3QN-{args.beta}_{args.num_task}', config=args, mode='disabled')

    ElevatorEMQ = prepare_elevator_env(args)
    ElevatorEMQ.runSimulation()
    args.run.finish()
