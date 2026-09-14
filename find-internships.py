#!/usr/bin/env python3
"""Run the internship finder on your own machine. No GitHub, no accounts.

    python find-internships.py

Fetches every tracked employer job board, filters to mechanical engineering
internships, and opens the results in your browser. Run it again whenever you
want fresh results — once a day is plenty.
"""

import os
import subprocess
import sys
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))


def check_dependencies() -> bool:
    """Make sure the two libraries we need are installed."""
    missing = []
    for module, package in (("httpx", "httpx"), ("requests", "requests")):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if not missing:
        return True

    print("Missing required libraries:", ", ".join(missing))
    print()
    answer = input("Install them now? [Y/n] ").strip().lower()
    if answer and not answer.startswith("y"):
        print(f"\nNo problem. Install manually with:\n"
              f"  {sys.executable} -m pip install {' '.join(missing)}")
        return False

    print("\nInstalling...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", *missing],
        cwd=HERE,
    )
    if result.returncode != 0:
        print(f"\nInstall failed. Try manually:\n"
              f"  {sys.executable} -m pip install {' '.join(missing)}")
        return False
    print("Installed.\n")
    return True


def main() -> int:
    print("=" * 62)
    print("  Mechanical Engineering Internship Finder")
    print("=" * 62)
    print()

    if not check_dependencies():
        return 1

    print("Checking ~4,500 employer job boards. This takes a few minutes —")
    print("it is polling real career sites, not a cached list.")
    print()

    result = subprocess.run([sys.executable, "run.py", "update"], cwd=HERE)
    if result.returncode != 0:
        print("\nThe run did not finish cleanly. The output above says why.")
        print("A few boards timing out is normal and not fatal; a total")
        print("failure usually means no internet connection.")
        return result.returncode

    dashboard = os.path.join(HERE, "docs", "index.html")
    readme = os.path.join(HERE, "README.md")
    csv = os.path.join(HERE, "data", "internships.csv")

    print()
    print("=" * 62)
    print("  Done. Your results:")
    print("=" * 62)
    print(f"  Dashboard (search + filters) : {dashboard}")
    print(f"  Plain table                  : {readme}")
    print(f"  Spreadsheet (Excel/Sheets)   : {csv}")
    print()

    if os.path.exists(dashboard):
        print("Opening the dashboard...")
        webbrowser.open(f"file://{dashboard}")
    else:
        print("No dashboard was generated — the run may have found no roles yet.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
