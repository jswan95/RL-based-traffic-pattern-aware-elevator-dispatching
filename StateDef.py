import enum


class DesState(enum.Enum):
    def __eq__(self, other):
        return self.value == other.value

#  CarState.IDLE.name : 'IDLE'
#  CarState.IDLE.value : 0


class CarAction(DesState):
    STOP_UP = 0
    STOP_DOWN = 1
    PASS_UP = 2
    PASS_DOWN = 3
    STAY = 4


class CarState(DesState):
    IDLE = 0
    MOVING_UP = 4   # green
    # R_STOP = 5  # dar green
    #LOADING = 2
    MOVING_DOWN = 2   # cyan
    # D_STOP = 6    # blue
    #UNLOADING = 3
    # PUSHING = 11
    # PD_MOVING = 8

    def idle(self):
        return self == CarState.IDLE

    def working(self):
        if self != CarState.IDLE:
            return 1
        else:
            return 0

    # def idle(self):
    #     return self == CarState.IDLE
    #
    # def (self):
    #     return self == CarState.MOVING_DOWN
    #
    # def moving_up(self):
    #     return self == CarState.MOVING_UP

# class JobState(DesState):
#     UNASSIGNED = enum.auto()
#     RETRIEVING = enum.auto()
#     LOADING = enum.auto()
#     DELIVERING = enum.auto()
#     UNLOADING = enum.auto()
#     FINISHED = enum.auto()

