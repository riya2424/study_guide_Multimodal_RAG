# Troubleshooting: macOS pip PermissionError

**Error:** `PermissionError: [Errno 1] Operation not permitted` (usually failing on `os.getcwd()`)

## Root Cause
This is a macOS privacy and security block, not a bug in Python or `pip`. Your Mac is actively blocking your terminal application (e.g., Terminal, iTerm2) from reading the directory you are currently working in (typically restricted folders like Desktop, Documents, or Downloads).

## How to Fix It

### Step 1: Grant macOS Folder Permissions
1. Open your Mac's **System Settings**.
2. Go to **Privacy & Security**.
3. Scroll down and click on **Files and Folders** (or **Full Disk Access**).
4. Find your terminal application in the list (e.g., **Terminal**).
5. Toggle the switch **ON** for the restricted folders (e.g., *Downloads*, *Documents*, *Desktop*).

### Step 2: Restart Your Terminal
For the new permissions to take effect, you must completely quit the terminal application. 
* Press `Cmd + Q` to quit.
* Reopen your terminal application.

### Step 3: Reactivate Your Environment & Retry
Navigate back to your project folder, reactivate your Python virtual environment, and run the `pip` command again:

```bash
# Navigate to your project
cd path/to/your/project

# Reactivate the virtual environment
source venv/bin/activate

# Retry the installation
pip install -U duckduckgo-search ddgs
```
