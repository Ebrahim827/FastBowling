"""
FIX ALL SIBLING IMPORTS AT ONCE.

Run this from inside backend/app/:
    python fix_imports.py

What it does: finds every .py file in the current folder, builds the
set of local module names (every filename minus .py), then rewrites
any "from X import ..." or "import X" line - where X is one of those
local modules - into a proper relative import ("from .X import ...").
This is exactly what Vercel needs (it imports your code as a real
Python package, so bare sibling imports break with
"ModuleNotFoundError: No module named 'database'" etc.) but your local
`uvicorn main:app` never showed the problem, since running a file
directly doesn't require relative imports.

Safe to run more than once - already-relative imports are left alone.
"""

import os
import re

folder = os.path.dirname(os.path.abspath(__file__))
local_modules = {
    f[:-3] for f in os.listdir(folder)
    if f.endswith(".py") and f != os.path.basename(__file__)
}

print(f"Local modules detected: {sorted(local_modules)}\n")

changed_files = []

for fname in sorted(os.listdir(folder)):
    if not fname.endswith(".py") or fname == os.path.basename(__file__):
        continue
    path = os.path.join(folder, fname)
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    file_changed = False
    for line in lines:
        stripped = line.rstrip("\n")

        # "from X import ..." -> "from .X import ..."
        m = re.match(r"^from (\w+) import (.+)$", stripped)
        if m and m.group(1) in local_modules:
            new_line = f"from .{m.group(1)} import {m.group(2)}\n"
            new_lines.append(new_line)
            if new_line != line:
                file_changed = True
                print(f"  {fname}: {stripped}  ->  {new_line.rstrip()}")
            continue

        # "import X" or "import X as y" -> "from . import X" / "from . import X as y"
        m = re.match(r"^import (\w+)( as \w+)?$", stripped)
        if m and m.group(1) in local_modules:
            alias = m.group(2) or ""
            new_line = f"from . import {m.group(1)}{alias}\n"
            new_lines.append(new_line)
            file_changed = True
            print(f"  {fname}: {stripped}  ->  {new_line.rstrip()}")
            continue

        new_lines.append(line)

    if file_changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        changed_files.append(fname)

print(f"\nDone. Changed {len(changed_files)} file(s): {changed_files}")
print("Also make sure backend/app/ has an __init__.py file (even an empty one) -")
print("required for Python to treat it as a real package.")