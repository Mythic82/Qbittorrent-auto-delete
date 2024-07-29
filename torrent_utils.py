import os
import sys
import platform
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
    if 'bonus_rules' in config:
        for category, rule_string in config['bonus_rules'].items():
            category_rules = {}
            for rule in rule_string.split(', '):
                key, value = rule.split(':', 1)
                if key in ['min_weeks', 'extra_multiplier_weeks', 'extra_multiplier_value']:
                    category_rules[key] = float(value)
                elif key in ['time_multipliers', 'size_multipliers']:
                    category_rules[key] = parse_multipliers(value)
            if category_rules:  # Only add the category if it has any bonus rules
                bonus_rules[category] = category_rules
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
    
    if torrent_category in bonus_rules:
        category_rules = bonus_rules[torrent_category]
        logger.debug(f"{torrent_category} category adjustments for torrent: {torrent['name']}")
        
        multiplier = 1.0
        if 'time_multipliers' in category_rules:
            time_multiplier = get_multiplier(weeks_seeded, category_rules['time_multipliers'])
            multiplier *= time_multiplier
        if 'size_multipliers' in category_rules:
            size_multiplier = get_multiplier(torrent_size / BYTES_TO_GB, category_rules['size_multipliers'])
            multiplier *= size_multiplier
        if 'extra_multiplier_weeks' in category_rules and 'extra_multiplier_value' in category_rules:
            if weeks_seeded >= category_rules['extra_multiplier_weeks']:
                multiplier *= category_rules['extra_multiplier_value']
        
        return multiplier
    
    return 1.0

def calculate_average_ratio(torrent: Dict[str, Any], log_file_path: str, logger: Logger, bonus_rules: Dict[str, Dict[str, Any]], config: configparser.ConfigParser) -> float:
    ratio_log = load_ratio_log(log_file_path)
    ratio_records = ratio_log.get(torrent['hash'], [])
    
    current_ratio = torrent['ratio']
    ratio_old = ratio_records[0]['ratio'] if ratio_records else None
    weeks_seeded = torrent.get('seeding_time', 0) / SECONDS_PER_WEEK
    num_records_weeks = len(ratio_records) / 7
    
    min_ratio_change = config.getfloat('ratio_calculation', 'min_ratio_change', fallback=0.3)
    min_weeks_seeded = config.getfloat('ratio_calculation', 'min_weeks_seeded', fallback=3)

    if ratio_old is not None:
        ratio_change = current_ratio - ratio_old
        if min_weeks_seeded > 0:
            ratio_change = max(ratio_change, min_ratio_change) if num_records_weeks <= min_weeks_seeded else ratio_change
        average_ratio_change = ratio_change / num_records_weeks if ratio_change != 0 and num_records_weeks > 0 else 0
    elif min_ratio_change > 0 and min_weeks_seeded > 0 and current_ratio < min_ratio_change and weeks_seeded <= min_weeks_seeded:
        average_ratio_change = min_ratio_change / weeks_seeded if weeks_seeded > 0 else 0
    else:
        average_ratio_change = current_ratio / weeks_seeded if weeks_seeded > 0 else 0

    bonus_multiplier = apply_bonus_rules(torrent, bonus_rules, logger)
    average_ratio_change *= bonus_multiplier

    return average_ratio_change

def get_category_rules(config: configparser.ConfigParser) -> Dict[str, Dict[str, float]]:
    """Get seed time and ratio rules for each category."""
    rules = {}
    for category, rule_string in config['seed_rules'].items():
        category_rules = {}
        for rule in rule_string.split(', '):
            key, value = rule.split(':')
            if key in ['min_seed_time', 'min_ratio']:
                category_rules[key] = float(value)
        if category_rules:  # Only add the category if it has any rules
            rules[category.lower()] = category_rules
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
                             f"seed time: {torrent['seeding_time']} >= {min_seed_time if min_seed_time is not None else 'N/A'}, "
                             f"ratio: {torrent['ratio']} >= {min_ratio if min_ratio is not None else 'N/A'}")
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
                             bonus_rules: Dict[str, Dict[str, Any]], config: configparser.ConfigParser) -> List[Dict[str, Any]]:
    """Remove torrents to free up space."""
    space_freed = 0.0
    torrents_removed_info = []

    torrents_in_categories = [t for t in torrents if t['category'].lower() in categories_space]
    for torrent in torrents_in_categories:
        torrent['average_ratio'] = calculate_average_ratio(torrent, log_file_path, logger, bonus_rules, config)

    torrents_sorted = sorted(torrents_in_categories, key=lambda t: (t['average_ratio'], -t['seeding_time'], -t['size'], t['name']))

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
                             logger: Logger, session: requests.Session, api_address: str, test_mode: bool,
                             log_file_path: str, bonus_rules: Dict[str, Dict[str, Any]], 
                             sort_by_size: bool, config: configparser.ConfigParser) -> List[Dict[str, Any]]:
    """Remove torrents to maintain a maximum count per category."""
    torrents_removed_info = []

    for category in categories_number:
        category_torrents = [t for t in torrents if t['category'].lower() == category.lower()]
        
        if len(category_torrents) > max_torrents:
            logger.info(f"Category '{category}' has {len(category_torrents)} torrents, exceeding the limit of {max_torrents}")
            
            if sort_by_size:
                sorted_torrents = sorted(category_torrents, key=lambda t: t['size'], reverse=True)
            else:
                for torrent in category_torrents:
                    torrent['average_ratio'] = calculate_average_ratio(torrent, log_file_path, logger, bonus_rules, config)
                sorted_torrents = sorted(category_torrents, key=lambda t: (t['average_ratio'], -t['seeding_time'], -t['size'], t['name']))
            
            torrents_to_remove = sorted_torrents[:len(category_torrents) - max_torrents]
            
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
            logger.debug(f"No need to remove torrents from category '{category}'. Count ({len(category_torrents)}) is within the limit ({max_torrents}).")

    return torrents_removed_info