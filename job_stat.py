from utils import Accumulator
from Passenger import Passenger


class JobStat:  # passenger 처리 통계 수집
    def __init__(self, con):
        self.con = con
        self.waiting_time = Accumulator()
        self.journey_time = Accumulator()
        self.trip_time = Accumulator()
        self.before_reset = 0  # to solve the issue that passenger generated did not reset

    def append(self, passenger):
        wt_p = passenger.get_waiting_time()
        jt_p = passenger.get_journey_time()
        tt_p = passenger.get_trip_time()

        self.waiting_time.append(wt_p)
        self.journey_time.append(jt_p)
        self.trip_time.append(tt_p)

    def send_stat_row(self, r, accumulator):
        self.con.emq.sendMonMsg(f"widget jobStat table {r} 0 {accumulator.avg():.3f}")
        self.con.emq.sendMonMsg(f"widget jobStat table {r} 1 {accumulator.std():.3f}")
        self.con.emq.sendMonMsg(f"widget jobStat table {r} 2 {accumulator.max:.3f}")

    def send_stat(self):
        for i, accumulator in enumerate([self.waiting_time, self.journey_time, self.trip_time]):
            self.send_stat_row(i, accumulator)
        self.con.emq.sendMonMsg(f"widget jobsGen text {Passenger.pid - self.before_reset}")
        self.con.emq.sendMonMsg(f"widget jobsDone text {self.trip_time.n}")

    def write_stat_row(self, fi, header, ac):
        fi.write(f"{header}(avg), {ac.avg():.3f}\n")
        fi.write(f"{header}(std), {ac.std():.3f}\n")
        fi.write(f"{header}(max), {ac.max:.3f}\n")

    def write_stat(self, fi):
        self.write_stat_row(fi, "Time to Wait", self.waiting_time)
        self.write_stat_row(fi, "Time in Car", self.journey_time)
        self.write_stat_row(fi, "Total Time", self.trip_time)
        fi.write(f"Total passengers, {Passenger.pid}\n")
        fi.write(f"Transported passengers, {self.trip_time.n}\n")
        return (self.waiting_time.avg(), self.waiting_time.max,
                self.journey_time.avg(), self.journey_time.max,
                self.trip_time.avg(), self.trip_time.max)

    def reset(self):
        self.before_reset = Passenger.pid
        self.waiting_time.reset()
        self.journey_time.reset()
        self.trip_time.reset()
