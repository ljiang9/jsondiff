"""Enables `python -m jsondiff`."""

import sys

if __package__:
    from .jsondiff import main
else:  # 直接运行 python __main__.py 的兜底
    from jsondiff import main

if __name__ == "__main__":
    sys.exit(main())
