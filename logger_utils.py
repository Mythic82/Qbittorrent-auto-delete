import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Tuple, List, Dict, Any
import torrent_utils

# Constants
MAX_BYTES = 1 * 1024 * 1024  # 1 MB
BACKUP_COUNT = 3
SEPARATOR_LENGTH = 127
MAX_NAME_LENGTH = 69
BYTES_TO_GB = 1024 ** 3
SECONDS_PER_WEEK = 7 * 86400

class PrependingRotatingFileHandler(RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super(PrependingRotatingFileHandler, self).__init__(*args, **kwargs)
        self.log_entries: List[str] = []
        self.first_entry = True

    def emit(self, record: logging.LogRecord) -> None:
        if self.shouldRollover(record):
            self.doRollover()

        if self.first_entry:
            log_entry = "-" * SEPARATOR_LENGTH + "\n" + self.format(record)
            self.first_entry = False
        else:
            log_entry = record.getMessage()

        self.log_entries.append(log_entry)

    def write_log_entries(self) -> None:
        if self.log_entries:
            try:
                with open(self.baseFilename, 'r+') as file:
                    existing_content = file.read()
                    file.seek(0, 0)
                    file.write('\n'.join(self.log_entries) + '\n' + existing_content)
            except IOError as e:
                print(f"Error writing log entries: {e}")
            finally:
                self.log_entries = []
                self.first_entry = True

def setup_logger(log_file_name: str = '/mnt/ssd/Download/deletelog.txt') -> Tuple[logging.Logger, PrependingRotatingFileHandler]:
    handler = PrependingRotatingFileHandler(log_file_name, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(log_formatter)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # Change this to DEBUG
    return logger, handler

def log_torrent_removal_info(torrents_info: List[Dict[str, Any]], logger: logging.Logger, test_mode: bool, bonus_rules: Dict[str, Dict[str, Any]]) -> None:
    if not torrents_info:
        logger.info("No torrents to remove based on current rules.")
        return

    logger.info(f"Total torrents to remove: {len(torrents_info)}")

    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'torrent_ratio_log.json')

    for torrent_info in torrents_info:
        size_gb = torrent_info['size'] / BYTES_TO_GB
        seeding_time_week = torrent_info['seeding_time'] / SECONDS_PER_WEEK
        category = torrent_info.get('category', 'Unknown')

        average_ratio_per_week = torrent_utils.calculate_average_ratio(torrent_info, log_file_path, logger, bonus_rules)

        truncated_name = (torrent_info['name'][:MAX_NAME_LENGTH - 3] + '...') if len(torrent_info['name']) > MAX_NAME_LENGTH else torrent_info['name']

        size_str = f"{size_gb:.2f} GB".rjust(10)
        seeding_time_str = f"{seeding_time_week:.1f} Weeks".rjust(11)
        ratio_week_str = f"{average_ratio_per_week:.3f} R/W".rjust(11)

        logger.info(f"{truncated_name:<69}  \t{category} \t{size_str} \t{seeding_time_str} \t{ratio_week_str}")