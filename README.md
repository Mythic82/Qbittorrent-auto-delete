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
- `requests` library (`pip install requests`)

## Configuration

The script uses a `config.ini` file for its settings. Here's an example configuration:

```ini
[login]
address = http://localhost:8080
username = your_username
password = your_password

[cleanup]
categories_to_check_for_space = Category1,Category2,Category3
min_space_gb = 350
download_minspace_gb = 35
categories_to_check_for_number = Category4
max_torrents_for_categories = 100

[seed_rules]
Category1_min_seed_time = 540000
Category1_min_ratio = 1.1
Category2_min_seed_time = 180000
Category2_min_ratio = 1.2

[bonus_rules]
categories = Category1

[Category1_bonus]
min_weeks = 1
time_multipliers = 2:1.05, 3:1.1, 4:1.125
size_multipliers = 4:1.1, 10:1.2, 20:1.3
extra_multiplier_weeks = 4
extra_multiplier_value = 1.2
