import sys
from .service import main as _main

def main() -> int:
    return _main(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
