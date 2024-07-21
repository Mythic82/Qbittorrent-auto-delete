Qbittorrent-auto-delete

A Python script that automatically manages torrents in qBittorrent based on specified seeding rules, available disk space, and number of seeding torrents.

Overview

This script automates the process of maintaining your qBittorrent instance by:

1. Deleting torrents that have fulfilled specified seeding rules.
2. Freeing up disk space when a set minimum free space threshold is reached.
3. Limiting the number of seeding torrents in specified categories.

Torrents are prioritized for deletion based on their seeding ratio over the last month, with those having the lowest ratio being removed first.

Features

- Configurable seeding rules per torrent category
- Minimum free space threshold for disk management
- Maximum torrent count limit per category
- Bonus multipliers for long-term seeding and large torrents
- Test mode for safe execution without actual deletions
- Detailed logging of actions and decisions

Requirements

- Python 3.6+
- qBittorrent with Web UI enabled
- 'requests' library (pip install requests)

Configuration

The script uses a 'config.ini' file for its settings. Here's an example configuration:

Usage

1. Clone this repository
2. Install the required Python packages: pip install -r requirements.txt
3. Configure your 'config.ini' file
4. Run the script: python main.py

To run in test mode (no actual deletions), use: python main.py --test

Logging

The script creates a log file named 'deletelog.txt' in the same directory as the script. This log file contains detailed information about the script's operations, including which torrents were considered for deletion and why.

The log file uses a rotating file handler, which means:
- The main log file is named 'deletelog.txt'
- When this file reaches a size of 1 MB, it will be renamed to 'deletelog.txt.1'
- A new 'deletelog.txt' file will be created for new log entries
- This process repeats, with older logs being named 'deletelog.txt.2', 'deletelog.txt.3', etc.
- A maximum of 3 backup log files are kept

Customizing the Log File Name

If you want to use a different name for the log file:

1. Open the 'main.py' file.
2. Find the line that calls 'logger_utils.setup_logger()'.
3. Modify it to include your preferred log file name.

For example:

logger, log_handler = logger_utils.setup_logger('my_custom_log.txt')

Torrent Ratio Logger

The script includes a separate module, 'torrent_ratio_logger.py', which manages the 'torrent_ratio_log.json' file. This module is responsible for tracking the ratio history of torrents over time.

Functionality

- Connects to the qBittorrent API to fetch current torrent data.
- Maintains a JSON file ('torrent_ratio_log.json') with historical ratio data for each torrent.
- Updates the log daily with new ratio information.
- Manages the size of the log by keeping a maximum of 28 entries per torrent.
- Implements a purge mechanism at specific intervals (8, 16, and 24 days) to remove older entries.

Key Features

1. API Session Management: Safely manages connections to the qBittorrent API.
2. Data Processing: 
   - Adds new ratio data daily.
   - Maintains a maximum of 28 entries per torrent.
   - Purges older entries at specific intervals to keep the log manageable.
3. Statistics Logging: Provides summary statistics about the update process, including:
   - Total number of torrents in the log
   - Number of new torrents added
   - Number of torrents removed
   - Number of torrents with maximum entries

Usage

python torrent_ratio_logger.py

Configuration

The module uses the same 'config.ini' file as the main script for API connection details.

Log File

The 'torrent_ratio_log.json' file is structured as follows:

{
  "torrent_hash_1": [
    {"date": "2023-07-21", "ratio": 1.5},
    {"date": "2023-07-22", "ratio": 1.6},
    ...
  ],
  "torrent_hash_2": [
    {"date": "2023-07-21", "ratio": 2.0},
    {"date": "2023-07-22", "ratio": 2.1},
    ...
  ]
}

This file is crucial for the main script's decision-making process when determining which torrents to remove based on their seeding performance over time.

Note: The log file is automatically managed by the script. Manual modifications are not recommended.

Test Mode

The script includes a test mode that allows you to see what actions would be taken without actually deleting any torrents. This is useful for verifying your configuration and understanding how the script would behave in a real scenario.

To run the script in test mode, use the '--test' flag:

python main.py --test

In test mode:
- The script will log all actions it would take, including which torrents it would delete.
- No actual changes will be made to your qBittorrent instance.
- The log file will be updated with the test results, prefixed with "TEST MODE:".

This mode is highly recommended when setting up the script for the first time or after making changes to your configuration.

Recommended Usage

For optimal performance and accurate torrent management, it's recommended to run the scripts as follows:

Torrent Ratio Logger

Run 'torrent_ratio_logger.py' once daily to update the JSON file with the latest ratio changes:

python torrent_ratio_logger.py

This ensures that you have up-to-date information on torrent ratios, which is crucial for making informed decisions about which torrents to keep or remove.

Main Script

Run 'main.py' once every hour:

python main.py

This frequency allows the script to regularly check and manage your torrents based on the latest data and your specified rules.

Automating with Cron Jobs

You can easily automate these tasks using cron jobs on Unix-based systems. Here's an example of how to set up your crontab:

1. Open your crontab file:
   crontab -e

2. Add the following lines:
   0 0 * * * /usr/bin/python /path/to/your/torrent_ratio_logger.py
   0 * * * * /usr/bin/python /path/to/your/main.py

   This sets up:
   - The Torrent Ratio Logger to run daily at midnight
   - The main script to run at the start of every hour

Make sure to replace '/path/to/your/' with the actual path to your script files.

For Windows systems, you can use Task Scheduler to set up similar automated tasks.

Note: Adjust these frequencies as needed based on your specific use case and system resources. More frequent updates may provide more accurate management but will also use more system resources.