import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        from courier_core.status_cmd import main as status_main
        return status_main(sys.argv[2:])
    from .serve import main as serve_main
    return serve_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
