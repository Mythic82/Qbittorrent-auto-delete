# Qbittorrent-auto-delete

Tired of managing complex seeding rules and manually selecting torrents to remove when your disk space runs low? This script is designed to simplify your life. Once set up, you only need to define seeding rules for each category. Then, as you add new torrents to these categories, they'll be managed automatically.
When your drive starts to fill up, the script takes action. It prioritizes removing the least performing torrents - those with the lowest seeding ratio over the past month. This process continues until it reaches your specified free disk space or torrent count.
With this tool, you can:

Automate torrent management
Maintain optimal disk space
Ensure your best-performing torrents keep seeding

Say goodbye to manual torrent management and hello to a more efficient, hands-off approach!

## Support the Project

If you find this project helpful and want to support its development, you can buy me a coffee!

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-☕-yellow.svg)](https://www.buymeacoffee.com/Mythic82)

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
