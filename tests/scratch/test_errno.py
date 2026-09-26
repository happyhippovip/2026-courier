import errno
import os
try:
    os.kill(1, 0)
except OSError as e:
    print(type(e), e.errno == errno.EPERM)
