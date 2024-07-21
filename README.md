## Support the Project

If you find this project helpful and want to support its development, you can buy me a coffee!

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-☕-yellow.svg)](https://www.buymeacoffee.com/Mythic82)

# Qbittorrent-auto-delete

A Python script that automatically manages torrents in qBittorrent based on specified seeding rules, available disk space, and number of seeding torrents.

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

The script uses a `config.ini` file for its settings. (Example configuration details should be added here)

## Logging

- The script creates a log file named `deletelog.txt` in the same directory.
- Uses a rotating file handler (max 3 backup files, 1 MB each).
- To customize the log file name, modify the `logger_utils.setup_logger()` call in `main.py`.

## Torrent Ratio Logger

A separate module (`torrent_ratio_logger.py`) manages the `torrent_ratio_log.json` file, tracking ratio history of torrents over time.

### Key Features

1. API Session Management
2. Data Processing (daily updates, entry management)
3. Statistics Logging

## Recommended Usage

1. Run `torrent_ratio_logger.py` once daily.
2. Run `main.py` once every hour.

### Automating with Cron Jobs (Unix-based systems)

Add to your crontab:
0 0 * * * /usr/bin/python /path/to/your/torrent_ratio_logger.py
0 * * * * /usr/bin/python /path/to/your/main.py
Copy
For Windows, use Task Scheduler for similar automation.

## Test Mode

Run with `--test` flag to see potential actions without making changes:
python main.py --test
