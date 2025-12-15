import os
import re

VERSION_FILE = 'version.py'

def increment_build_number():
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'w') as f:
            f.write("BUILD_NUMBER = 100\n")
        print("Created version.py with BUILD_NUMBER = 100")
        return

    with open(VERSION_FILE, 'r') as f:
        content = f.read()

    match = re.search(r'BUILD_NUMBER\s*=\s*(\d+)', content)
    if match:
        current_build = int(match.group(1))
        new_build = current_build + 1
        new_content = re.sub(r'BUILD_NUMBER\s*=\s*\d+', f'BUILD_NUMBER = {new_build}', content)
        
        with open(VERSION_FILE, 'w') as f:
            f.write(new_content)
        print(f"Build number incremented to {new_build}")
    else:
        print("Could not find BUILD_NUMBER in version.py")

if __name__ == "__main__":
    increment_build_number()
