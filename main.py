import sys
import os
import requests
from typing import List, Dict, Any
from logging import Logger
import logger_utils
import torrent_utils
from configparser import ConfigParser

def check_space_and_remove_torrents(session: requests.Session, logger: Logger, config: ConfigParser, test_mode: bool, bonus_rules: Dict[str, Dict[str, Any]]) -> None:
    api_address = config.get('login', 'address')
    download_minspace_gb = config.getfloat('cleanup', 'download_minspace_gb')
    min_space_gb = config.getfloat('cleanup', 'min_space_gb')
    categories_space = [cat.strip().lower() for cat in config.get('cleanup', 'categories_to_check_for_space').split(',')]
    categories_count = [cat.strip().lower() for cat in config.get('cleanup', 'categories_to_check_for_number').split(',')]

    script_directory = os.path.dirname(os.path.abspath(__file__))
    configured_drive_path = config.get('cleanup', 'drive_path', fallback='').strip()
    drive_path = configured_drive_path if configured_drive_path else torrent_utils.get_drive_path(script_directory)
    free_space = torrent_utils.get_free_space(drive_path)

    try:
        all_torrents = torrent_utils.get_torrent_list(session, api_address, logger)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            torrent_utils.login_to_qbittorrent(session, api_address, 
                                               config.get('login', 'username'), 
                                               config.get('login', 'password'), logger)
            all_torrents = torrent_utils.get_torrent_list(session, api_address, logger)
        else:
            raise

    downloading_torrents = [t for t in all_torrents if t['state'] == 'downloading']
    total_remaining_size_gb = sum((t['size'] * (1 - t['progress'])) for t in downloading_torrents) / (1024 ** 3)

    space_left_after_downloads = free_space - total_remaining_size_gb
    additional_space_needed = max(0, download_minspace_gb - space_left_after_downloads)
    space_needed = max(0, min_space_gb - free_space)

    category_rules = torrent_utils.get_category_rules(config)

    filtered_torrents = torrent_utils.filter_torrents_by_rules(
        all_torrents, 
        category_rules, 
        logger
    )

    torrents_removed_by_space = torrent_utils.remove_torrents_by_space(
        filtered_torrents,
        categories_space,
        max(additional_space_needed, space_needed),
        drive_path,
        logger,
        session,
        api_address,
        test_mode,
        os.path.join(script_directory, 'torrent_ratio_log.json'),
        bonus_rules,
        config
    ) if space_needed > 0 or additional_space_needed > 0 else []

    torrents_removed_by_count = torrent_utils.remove_torrents_by_count(
        filtered_torrents,
        categories_count,
        config.getint('cleanup', 'max_torrents_for_categories'), 
        logger, 
        session, 
        api_address, 
        test_mode,
        os.path.join(script_directory, 'torrent_ratio_log.json'),
        bonus_rules,
        config.getboolean('cleanup', 'sort_count_removal_by_size', fallback=False),
        config
    )

    all_removed_torrents = torrents_removed_by_space + torrents_removed_by_count

    if all_removed_torrents:
        log_removal_info(logger, free_space, total_remaining_size_gb, space_needed, additional_space_needed, all_removed_torrents, test_mode, bonus_rules, config)

def log_removal_info(logger: Logger, free_space: float, total_remaining_size_gb: float, 
                     space_needed: float, additional_space_needed: float, 
                     all_removed_torrents: List[Dict[str, Any]], test_mode: bool,
                     bonus_rules: Dict[str, Dict[str, Any]], config: ConfigParser) -> None:
    """Log information about removed or would-be removed torrents."""
    logger.info(f"{'TEST MODE: ' if test_mode else ''}Free: {free_space:.2f} GB, "
                f"DLremain: {total_remaining_size_gb:.1f} GB, "
                f"Diskneed: {max(space_needed, additional_space_needed):.0f} GB")
    logger_utils.log_torrent_removal_info(all_removed_torrents, logger, test_mode, bonus_rules, config)

def main(test_mode: bool, logger: Logger, handler: Any, config: ConfigParser, session: requests.Session) -> None:
    try:
        bonus_rules = torrent_utils.load_bonus_rules(config)
        check_space_and_remove_torrents(session, logger, config, test_mode, bonus_rules)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        handler.write_log_entries()

if __name__ == "__main__":
    script_directory = os.path.dirname(os.path.abspath(__file__))
    logger, log_handler = logger_utils.setup_logger()
    config = torrent_utils.load_configuration(script_directory)
    session = requests.Session()
    test_mode = '--test' in sys.argv
    main(test_mode, logger, log_handler, config, session)