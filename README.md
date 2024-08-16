# Qbittorrent-auto-delete

Tired of managing complex seeding rules and manually selecting torrents to remove when your disk space runs low? This script is designed to simplify your life. Once set up, you only need to define seeding rules for each category. Then, as you add new torrents to these categories, they'll be managed automatically.
When your drive starts to fill up, the script takes action. It prioritizes removing the least performing torrents - those with the lowest seeding ratio over the past month. This process continues until it reaches your specified free disk space or torrent count.
With this tool, you can:

Automate torrent management
Maintain optimal disk space
Ensure your best-performing torrents keep seeding

Say goodbye to manual torrent management and hello to a more efficient, hands-off approach!

If you found this script useful, you can [![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-☕-yellow.svg)](https://www.buymeacoffee.com/Mythic82)

## Overview

This script automates the process of maintaining your qBittorrent instance by:

1. Deleting torrents that have fulfilled specified seeding rules.
2. Freeing up disk space when a set minimum free space threshold is reached.
3. Limiting the number of seeding torrents in specified categories.

Torrents are prioritized for deletion based on their seeding ratio over the last month, with those having the lowest ratio being removed first.

## Features

- Configurable seeding rules per torrent category
- Minimum free space threshold for disk management
- Maximum torrent count limit per category
- Bonus multipliers for long-term seeding and large torrents
- Test mode for safe execution without actual deletions
- Detailed logging of actions and decisions

## Requirements

- Python 3.6+
- qBittorrent with Web UI enabled
- 'requests' library (`pip install requests`)

## Installation and Usage

1. Clone this repository
2. Install the required Python packages: `pip install -r requirements.txt`
3. Configure your `config.ini` file
4. Run the script: `python main.py`

To run in test mode (no actual deletions), use: `python main.py --test`

## Configuration

The script uses a `config.ini` file for its settings.

## Logging

- The script creates a log file named `deletelog.txt` in the same directory.
- Uses a rotating file handler (max 3 backup files, 1 MB each).
- To customize the log file name, modify the `logger_utils.setup_logger()` call in `main.py`.

## Torrent Ratio Logger

A separate module (`torrent_ratio_logger.py`) manages the `torrent_ratio_log.json` file, tracking ratio history of torrents over time.

## Recommended Usage

1. Run `torrent_ratio_logger.py` once daily.
2. Run `main.py` once every hour.

### Automating

Add to your crontab in linux / User scripts in Unraid / Task Scheduler in windows:
- 0 0 * * * /usr/bin/python /path/to/your/torrent_ratio_logger.py
- 0 * * * * /usr/bin/python /path/to/your/main.py
- @reboot pip install -r /path/to/your/requirements.txt

## Test Mode

Run with `--test` flag to see potential actions without making changes:
python main.py --test

---

# Unraid Setup Guide

This guide will help you set up and manage Python scripts on Unraid. Follow the steps below to install Python, configure your scripts, and set up automated tasks.

### Prerequisites 
Before starting, ensure you have the following installed on your Unraid system:

- Nerd Tools Addon (for Python 3 installation) 
- User Scripts Addon (for managing your scripts)

### Step 1: Edit Your Configuration 
Edit your config.ini file to customize it according to your preferences.

### Step 2: Install Python and Required Packages at Startup 
To install Python packages automatically at array startup, use the following script:

    #!/bin/bash
    # This script installs pip and required Python packages at boot
    
    # Check if pip is already installed
    if ! command -v pip3 &> /dev/null
    then
        echo "pip not found, installing..."
        # Download get-pip.py
        curl -s https://bootstrap.pypa.io/get-pip.py -o /boot/config/get-pip.py
        # Install pip
        python3 /boot/config/get-pip.py
    else
        echo "pip already installed"
    fi
    
    # Install required Python packages
    python3 -m pip install --quiet requests configparser
    
    echo "Python environment setup complete."

Save this script and configure it to run at array startup using the User Scripts addon.

### Step 3: Set Up Logging 
To log torrent ratios daily, use the following script. Schedule it to run daily at 00:01:

    #!/bin/bash
    python3 /mnt/scrptpath/torrent_ratio_logger.py

Set up a cron job with the following timing:

    1 0 * * *

This configuration runs the script every day at 00:01 AM.

### Step 4: Run the Main Script Hourly 
To run the main script every hour (e.g., at 15 minutes past the hour), use the following script:

    #!/bin/bash
    python3 /mnt/scrptpath/main.py

Set up a cron job with the following timing:

    15 * * * *

This configuration runs the script every hour at 15 minutes past.

### Step 5: Test Mode 
To test changes without making actual deletions, add the --test flag:

    python3 /mnt/scrptpath/main.py --test

This simulates the actions, and deletelog.txt will show what the script would have done without making any real changes.
