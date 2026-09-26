import sys

def foo():
    sys.exit(1)

try:
    foo()
except (Exception, SystemExit) as e:
    print("Caught!", type(e))

print("Continued!")
