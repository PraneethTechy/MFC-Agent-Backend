import os, sys, glob

matches = []
for root, dirs, files in os.walk("backend/app"):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    if "IN-TN-01" in content or "seed" in content.lower():
                        matches.append(path)
            except Exception:
                pass

print("Found in:")
for m in matches:
    print(" -", m)
