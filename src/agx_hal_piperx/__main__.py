"""HAL command entry point."""

from agx_hal.cli import main as _main


def main(argv=None):
    return _main("piperx", argv)


if __name__ == "__main__":
    raise SystemExit(main())
