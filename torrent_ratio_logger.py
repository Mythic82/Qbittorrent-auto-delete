import requests
import json
import configparser
import os
import sys
from datetime import datetime
from typing import Dict, List, Any
import logger_utils
from contextlib import contextmanager

# Constants
API_V2_BASE = "/api/v2"
SECONDS_PER_DAY = 24 * 3600
MAX_ENTRIES = 28
PURGE_DAYS = [8, 16, 24]

def load_configuration(script_directory: str) -> configparser.ConfigParser:
    """Load configuration from the config file."""
    config_path = os.path.join(script_directory, 'config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

@contextmanager
def api_session(api_address: str, username: str, password: str):
    """Create and manage an API session."""
    session = requests.Session()
    try:
        login_url = f"{api_address}{API_V2_BASE}/auth/login"
        response = session.post(login_url, data={'username': username, 'password': password})
        if response.text != 'Ok.':
            raise ConnectionError("Login failed")
        yield session
    finally:
        session.close()

def get_torrent_list(api_address: str, session: requests.Session) -> List[Dict[str, Any]]:
    """Fetch the list of torrents from the API."""
    torrent_list_url = f"{api_address}{API_V2_BASE}/torrents/info"
    try:
        response = session.get(torrent_list_url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to fetch torrent list. Error: {e}")
    except json.JSONDecodeError:
        raise ValueError(f"Failed to decode JSON. Status Code: {response.status_code}")

def load_existing_data(file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Load existing data from the log file."""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from {file_path}: {e}")

def save_data(file_path: str, data: Dict[str, List[Dict[str, Any]]], logger: Any) -> None:
    """Save data to the log file."""
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        logger.error(f"Error saving ratio log file: {e}")

def process_torrent_data(torrents: List[Dict[str, Any]], old_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Process torrent data and update the log."""
    new_data = old_data.copy()  # Start with a copy of old data
    current_date = datetime.now().strftime('%Y-%m-%d')

    for torrent in torrents:
        torrent_hash = torrent['hash']
        seed_days = torrent['seeding_time'] // SECONDS_PER_DAY
        ratio_record = {'date': current_date, 'ratio': torrent['ratio']}

        if torrent_hash not in new_data:
            new_data[torrent_hash] = [ratio_record]
        else:
            entries = new_data[torrent_hash]
            if not entries or entries[-1]['date'] != current_date:
                entries.append(ratio_record)
                if seed_days in PURGE_DAYS and len(entries) > 1:
                    entries.pop(0)

            entries = entries[-MAX_ENTRIES:]
            new_data[torrent_hash] = entries

    return new_data

def log_statistics(new_data: Dict[str, List[Dict[str, Any]]], old_data: Dict[str, List[Dict[str, Any]]], logger: Any) -> None:
    """Log statistics about the updated data."""
    total_torrents = len(new_data)
    
    old_torrent_set = set(old_data.keys())
    new_torrent_set = set(new_data.keys())
    
    new_torrents_added = len(new_torrent_set - old_torrent_set)
    torrents_removed = len(old_torrent_set - new_torrent_set)
    
    torrents_with_max_entries = sum(1 for entries in new_data.values() if len(entries) >= MAX_ENTRIES)

    logger.info(f"Total torrents in log: {total_torrents}, "
                f"New torrents added: {new_torrents_added}, "
                f"Torrents removed: {torrents_removed}, "
                f"Torrents with max entries: {torrents_with_max_entries}")

def update_ratio_log(api_address: str, username: str, password: str, log_file_path: str, logger: Any) -> None:
    """Main function to update the ratio log."""
    try:
        with api_session(api_address, username, password) as session:
            torrents = get_torrent_list(api_address, session)
            old_data = load_existing_data(log_file_path)
            new_data = process_torrent_data(torrents, old_data)
            save_data(log_file_path, new_data, logger)
            log_statistics(new_data, old_data, logger)

    except Exception as e:
        logger.error(f"Failed to update ratio log: {e}")
        sys.exit(1)

if __name__ == "__main__":
    script_directory = os.path.dirname(os.path.abspath(__file__))
    config = load_configuration(script_directory)

    logger, log_handler = logger_utils.setup_logger()

    api_address = config.get('login', 'address')
    username = config.get('login', 'username')
    password = config.get('login', 'password')

    log_file_path = os.path.join(script_directory, 'torrent_ratio_log.json')

    logger.info("Running torrent ratio logger script")
    update_ratio_log(api_address, username, password, log_file_path, logger)
    log_handler.write_log_entries()