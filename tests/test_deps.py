"""Dependency checks: opencv, numpy, mss, Pillow."""

import sys


def check_deps(verbose: bool = True) -> bool:
    """Return True if all required deps are available."""
    missing = []
    for name, pkg in [
        ("opencv-python", "cv2"),
        ("numpy", "numpy"),
        ("mss", "mss"),
        ("Pillow", "PIL"),
    ]:
        try:
            __import__(pkg)
            if verbose:
                print("  OK  {}".format(name))
        except ImportError:
            missing.append(name)
            if verbose:
                print("  MISS {}".format(name))
    if verbose and missing:
        print("\n  Install: pip install -r requirements.txt")
    return len(missing) == 0


def run_deps() -> int:
    """Run dependency test. Returns 0 if all OK, 1 otherwise."""
    print("Checking dependencies:")
    return 0 if check_deps() else 1


if __name__ == "__main__":
    sys.exit(run_deps())
