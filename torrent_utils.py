import os
import sys
from shutil import disk_usage
import requests
import json
import configparser
from typing import Dict, List, Any, Optional
from logging import Logger

# Constants
API_V2_BASE = "/api/v2"
BYTES_TO_GB = 1024**3
SECONDS_PER_WEEK = 7 * 86400

def get_drive_path(file_path: str) -> str:
    """Find the mount point of a given file path."""
    file_path = os.path.abspath(file_path)
    while not os.path.ismount(file_path):
        file_path = os.path.dirname(file_path)
    return file_path

def get_free_space(drive_path: str) -> float:
    """Get free space on a given drive in GB."""
    return disk_usage(drive_path).free / BYTES_TO_GB

def load_configuration(script_directory: str) -> configparser.ConfigParser:
    """Load configuration from the config file."""
    config_path = os.path.join(script_directory, 'config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

def login_to_qbittorrent(session: requests.Session, api_address: str, username: str, password: str, logger: Logger) -> None:
    """Login to qBittorrent API."""
    login_url = f"{api_address}{API_V2_BASE}/auth/login"
    try:
        response = session.post(login_url, data={'username': username, 'password': password})
        response.raise_for_status()
        if response.text != 'Ok.':
            raise ValueError("Login failed: Unexpected response")
    except (requests.RequestException, ValueError) as e:
        logger.error(f"Login failed: {str(e)}")
        sys.exit(1)

def get_torrent_list(session: requests.Session, api_address: str, logger: Logger) -> List[Dict[str, Any]]:
    """Get list of torrents from qBittorrent API."""
    torrent_list_url = f"{api_address}{API_V2_BASE}/torrents/info"
    response = session.get(torrent_list_url)
    response.raise_for_status()  # This will raise an HTTPError for bad responses
    return response.json()

def load_ratio_log(log_file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load ratio log from file."""
    try:
        with open(log_file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {log_file_path}: {str(e)}")
        return {}

def calculate_average_ratio(torrent: Dict[str, Any], log_file_path: str, logger: Logger) -> float:
    """Calculate average ratio for a torrent."""
    ratio_log = load_ratio_log(log_file_path)
    ratio_records = ratio_log.get(torrent['hash'], [])
    
    current_ratio = torrent['ratio']
    ratio_old = ratio_records[0]['ratio'] if ratio_records else None
    weeks_seeded = torrent.get('seeding_time', 0) / SECONDS_PER_WEEK
    num_records_weeks = len(ratio_records) / 7
    
    if ratio_old is not None:
        ratio_change = current_ratio - ratio_old
        ratio_change = max(ratio_change, 0.3) if num_records_weeks <= 3 else ratio_change
        average_ratio_change = ratio_change / num_records_weeks if ratio_change != 0 else 0
    elif current_ratio < 0.3 and weeks_seeded <= 3:
        average_ratio_change = 0.3 / weeks_seeded
    else:
        average_ratio_change = current_ratio / weeks_seeded if current_ratio != 0 else 0

    torrent_size = torrent.get('size', 0)
    torrent_category = torrent.get('category', '')
    
    if torrent_category == 'SB' and weeks_seeded > 1:
        logger.debug(f"SB category adjustments for torrent: {torrent['name']}")
        
        time_multiplier = get_time_multiplier(weeks_seeded)
        size_multiplier = get_size_multiplier(torrent_size)
        extra_multiplier = 1.2 if weeks_seeded >= 4 else 1.0

        average_ratio_change *= time_multiplier * size_multiplier * extra_multiplier

    return average_ratio_change

def get_time_multiplier(weeks_seeded: float) -> float:
    """Get time multiplier based on seeding time."""
    if weeks_seeded >= 56: return 3
    elif weeks_seeded >= 55: return 2.875
    elif weeks_seeded >= 54: return 2.75
    elif weeks_seeded >= 53: return 2.625
    elif weeks_seeded >= 36: return 2.5
    elif weeks_seeded >= 35: return 2.375
    elif weeks_seeded >= 34: return 2.25
    elif weeks_seeded >= 33: return 2.125
    elif weeks_seeded >= 20: return 2
    elif weeks_seeded >= 19: return 1.95
    elif weeks_seeded >= 18: return 1.9
    elif weeks_seeded >= 17: return 1.85
    elif weeks_seeded >= 12: return 1.8
    elif weeks_seeded >= 11: return 1.7
    elif weeks_seeded >= 10: return 1.6
    elif weeks_seeded >= 9: return 1.5
    elif weeks_seeded >= 8: return 1.4
    elif weeks_seeded >= 7: return 1.35
    elif weeks_seeded >= 6: return 1.3
    elif weeks_seeded >= 5: return 1.225
    elif weeks_seeded >= 4: return 1.125
    elif weeks_seeded >= 3: return 1.1
    elif weeks_seeded >= 2: return 1.05
    else: return 1

def get_size_multiplier(torrent_size: int) -> float:
    """Get size multiplier based on torrent size."""
    size_gb = torrent_size / BYTES_TO_GB
    if size_gb >= 20: return 1.3
    elif size_gb >= 10: return 1.2
    elif size_gb >= 4: return 1.1
    else: return 1.0

def get_category_rules(config: configparser.ConfigParser) -> Dict[str, Dict[str, float]]:
    """Get seed time and ratio rules for each category."""
    rules = {}
    for key, value in config['seed_rules'].items():
        parts = key.split('_')
        if len(parts) < 2:
            continue  # Skip invalid keys
        category = parts[0].lower()  # Convert to lowercase
        rule_type = '_'.join(parts[1:])
        
        if category not in rules:
            rules[category] = {}
        rules[category][rule_type] = float(value)
    
    return rules

def filter_torrents_by_rules(torrents: List[Dict[str, Any]], category_rules: Dict[str, Dict[str, float]], logger: Logger) -> List[Dict[str, Any]]:
    filtered_torrents = []
    for torrent in torrents:
        category = torrent.get('category', '').lower()
        if category in category_rules:
            rules = category_rules[category]
            min_seed_time = rules.get('min_seed_time')
            min_ratio = rules.get('min_ratio')
            
            seed_time_met = min_seed_time is not None and torrent['seeding_time'] >= min_seed_time
            ratio_met = min_ratio is not None and torrent['ratio'] >= min_ratio
            
            if seed_time_met or ratio_met:
                filtered_torrents.append(torrent)
                logger.debug(f"Torrent {torrent['name']} eligible for removal: "
                             f"category: {category}, "
                             f"seed time: {torrent['seeding_time']} >= {min_seed_time}, "
                             f"ratio: {torrent['ratio']} >= {min_ratio}")
        else:
            logger.debug(f"No rules for category: {category}")
    
    return filtered_torrents

def remove_torrent(session: requests.Session, api_address: str, torrent_hash: str, delete_files: bool, logger: Logger) -> None:
    """Remove a torrent from qBittorrent."""
    removal_url = f"{api_address}{API_V2_BASE}/torrents/delete"
    data = {'hashes': torrent_hash, 'deleteFiles': str(delete_files).lower()}
    try:
        response = session.post(removal_url, data=data)
        response.raise_for_status()
        logger.debug(f"Torrent {torrent_hash} successfully removed.")
    except requests.RequestException as e:
        logger.error(f"Failed to remove torrent {torrent_hash}: {str(e)}")

def remove_torrents_by_space(torrents: List[Dict[str, Any]], categories_space: List[str], space_needed: float, drive_path: str, 
                             logger: Logger, session: requests.Session, api_address: str, test_mode: bool, log_file_path: str) -> List[Dict[str, Any]]:
    """Remove torrents to free up space."""
    space_freed = 0.0
    torrents_removed_info = []

    torrents_in_categories = [t for t in torrents if t['category'].lower() in categories_space]
    for torrent in torrents_in_categories:
        torrent['average_ratio'] = calculate_average_ratio(torrent, log_file_path, logger)

    torrents_sorted = sorted(torrents_in_categories, key=lambda t: (t['average_ratio'], -t['seeding_time']))

    for torrent in torrents_sorted:
        if space_freed >= space_needed:
            break
        torrent_info = {
            'hash': torrent['hash'],
            'name': torrent['name'],
            'size': torrent['size'],
            'seeding_time': torrent['seeding_time'],
            'ratio': torrent['ratio'],
            'category': torrent['category']
        }
        if not test_mode:
            remove_torrent(session, api_address, torrent['hash'], True, logger)
        space_freed += torrent['size'] / BYTES_TO_GB
        torrents_removed_info.append(torrent_info)

    return torrents_removed_info

def remove_torrents_by_count(torrents: List[Dict[str, Any]], categories_number: List[str], max_torrents: int, 
                             logger: Logger, session: requests.Session, api_address: str, test_mode: bool) -> List[Dict[str, Any]]:
    """Remove torrents to maintain a maximum count per category."""
    torrents_removed_info = []

    for category in categories_number:
        category_torrents = [t for t in torrents if t['category'] == category]
        
        if len(category_torrents) > max_torrents:
            sorted_torrents = sorted(category_torrents, key=lambda x: x['size'], reverse=True)
            torrents_to_remove = sorted_torrents[max_torrents:]
            
            for torrent in torrents_to_remove:
                torrent_info = {
                    'hash': torrent['hash'],
                    'name': torrent['name'],
                    'size': torrent['size'],
                    'seeding_time': torrent['seeding_time'],
                    'ratio': torrent['ratio'],
                    'category': torrent['category']
                }
                torrents_removed_info.append(torrent_info)
        
                if not test_mode:
                    remove_torrent(session, api_address, torrent['hash'], True, logger)
                else:
                    logger.info(f"Test mode enabled, would remove: {torrent['name']} ({torrent['hash']})")
        else:
            logger.debug(f"No need to remove torrents from category '{category}'. Count is within the limit.")

    return torrents_removed_info