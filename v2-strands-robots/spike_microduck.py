import time
from strands_robots import Policy, Robot
t0 = time.time()
duck = Robot("microduck")
print("loaded in %.1fs; start pose:" % (time.time() - t0), [round(float(x), 3) for x in duck.pose.position])
t1 = time.time()
duck.run(Policy("microduck?vx=0.3"), seconds=5)
print("ran 5 sim-seconds in %.1fs wall; pose:" % (time.time() - t1), [round(float(x), 3) for x in duck.pose.position])
