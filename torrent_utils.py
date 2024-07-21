import os
import sys
from shutil import disk_usage
import requests
import json
import configparser
from typing import Dict, List, Any, Optional, Tuple
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

def load_bonus_rules(config: configparser.ConfigParser) -> Dict[str, Dict[str, Any]]:
    """Load bonus rules from config."""
    bonus_rules = {}
    categories = [cat.strip() for cat in config.get('bonus_rules', 'categories').split(',')]
    
    for category in categories:
        section = f'{category}_bonus'
        if config.has_section(section):
            bonus_rules[category] = {
                'min_weeks': config.getfloat(section, 'min_weeks'),
                'time_multipliers': parse_multipliers(config.get(section, 'time_multipliers')),
                'size_multipliers': parse_multipliers(config.get(section, 'size_multipliers')),
                'extra_multiplier_weeks': config.getfloat(section, 'extra_multiplier_weeks'),
                'extra_multiplier_value': config.getfloat(section, 'extra_multiplier_value')
            }
    return bonus_rules

def parse_multipliers(multiplier_string: str) -> List[Tuple[float, float]]:
    """Parse multiplier string into a list of tuples."""
    return [(float(pair.split(':')[0]), float(pair.split(':')[1])) 
            for pair in multiplier_string.split(',')]

def get_multiplier(value: float, multipliers: List[Tuple[float, float]]) -> float:
    """Get the appropriate multiplier based on the value."""
    for threshold, multiplier in reversed(multipliers):
        if value >= threshold:
            return multiplier
    return 1.0

def apply_bonus_rules(torrent: Dict[str, Any], bonus_rules: Dict[str, Dict[str, Any]], logger: Logger) -> float:
    """Apply bonus rules to calculate the average ratio change."""
    torrent_category = torrent.get('category', '')
    weeks_seeded = torrent.get('seeding_time', 0) / SECONDS_PER_WEEK
    torrent_size = torrent.get('size', 0)
    
    if torrent_category in bonus_rules and weeks_seeded > bonus_rules[torrent_category]['min_weeks']:
        logger.debug(f"{torrent_category} category adjustments for torrent: {torrent['name']}")
        
        time_multiplier = get_multiplier(weeks_seeded, bonus_rules[torrent_category]['time_multipliers'])
        size_multiplier = get_multiplier(torrent_size / BYTES_TO_GB, bonus_rules[torrent_category]['size_multipliers'])
        extra_multiplier = (bonus_rules[torrent_category]['extra_multiplier_value'] 
                            if weeks_seeded >= bonus_rules[torrent_category]['extra_multiplier_weeks'] else 1.0)
        
        return time_multiplier * size_multiplier * extra_multiplier
    
    return 1.0

def calculate_average_ratio(torrent: Dict[str, Any], log_file_path: str, logger: Logger, bonus_rules: Dict[str, Dict[str, Any]]) -> float:
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

    bonus_multiplier = apply_bonus_rules(torrent, bonus_rules, logger)
    average_ratio_change *= bonus_multiplier

    return average_ratio_change

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
                             logger: Logger, session: requests.Session, api_address: str, test_mode: bool, log_file_path: str,
                             bonus_rules: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove torrents to free up space."""
    space_freed = 0.0
    torrents_removed_info = []

    torrents_in_categories = [t for t in torrents if t['category'].lower() in categories_space]
    for torrent in torrents_in_categories:
        torrent['average_ratio'] = calculate_average_ratio(torrent, log_file_path, logger, bonus_rules)

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