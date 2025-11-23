#!/usr/bin/env python3
"""
JellyCli - A command-line interface for Jellyfin
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Optional

import requests


VERSION = "1.0.0"


class JellyfinServer:
    """Handles communication with Jellyfin API"""
    
    def __init__(self, host: str, auth_key: str, user_id: str):
        self.host = host.rstrip('/')
        self.auth_key = auth_key
        self.user_id = user_id
        self.session = requests.Session()
        self.auth_header = (
            f'MediaBrowser Client="JellyCli", Device="Python", '
            f'DeviceId="1", Version="{VERSION}", Token="{auth_key}"'
        )
        self.session.headers.update({
            'X-Emby-Authorization': self.auth_header
        })
    
    def _make_request(self, url: str) -> Dict:
        """Make a GET request to the Jellyfin API"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error making request: {e}", file=sys.stderr)
            sys.exit(1)
    
    def get_collections(self) -> List[Dict]:
        """Get top-level collections"""
        url = f"{self.host}/Items?userId={self.user_id}"
        data = self._make_request(url)
        return data.get('Items', [])
    
    def get_child_items(self, parent_id: str) -> List[Dict]:
        """Get child items for a given parent ID"""
        url = f"{self.host}/Items?parentId={parent_id}"
        data = self._make_request(url)
        items = data.get('Items', [])
        
        # Sort episodes by IndexNumber
        if items and items[0].get('Type') == 'Episode':
            items.sort(key=lambda x: x.get('IndexNumber', 0))
        
        return items
    
    def get_download_url(self, item_id: str) -> str:
        """Get the download URL for an item"""
        return f"{self.host}/Items/{item_id}/Download?api_key={self.auth_key}"


def load_config() -> Dict:
    """Load configuration from ~/.config/jellycli.conf"""
    config_path = Path.home() / ".config" / "jellycli.conf"
    
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        print("Please create a config file with the following format:", file=sys.stderr)
        print('{"Host": "http://your-server:8096", "UserId": "your-user-id", "AuthKey": "your-api-key"}', file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)


def display_items(items: List[Dict], indent: int = 0):
    """Display items in a formatted list"""
    prefix = "  " * indent
    for i, item in enumerate(items, 1):
        item_type = "📁" if item.get('IsFolder') else "🎬"
        name = item.get('Name', 'Unknown')
        item_id = item.get('Id', '')
        print(f"{prefix}{i}. {item_type} {name} (ID: {item_id})")


def browse_interactive(server: JellyfinServer, parent_id: Optional[str] = None, path: List[str] = None):
    """Interactive browsing mode"""
    if path is None:
        path = []
    
    # Get items
    if parent_id is None:
        items = server.get_collections()
        print("\n=== Collections ===")
    else:
        items = server.get_child_items(parent_id)
        print(f"\n=== {' > '.join(path)} ===")
    
    if not items:
        print("No items found.")
        return
    
    display_items(items)
    
    print("\nOptions:")
    print("  - Enter item number to browse/play")
    print("  - 'b' to go back")
    print("  - 'q' to quit")
    
    choice = input("\nYour choice: ").strip().lower()
    
    if choice == 'q':
        return
    elif choice == 'b':
        if len(path) > 0:
            path.pop()
            new_parent = path[-1] if path else None
            browse_interactive(server, new_parent, path)
        return
    
    try:
        index = int(choice) - 1
        if 0 <= index < len(items):
            item = items[index]
            item_id = item.get('Id')
            item_name = item.get('Name', 'Unknown')
            
            if item.get('IsFolder'):
                path.append(item_id)
                browse_interactive(server, item_id, path)
            elif item.get('VideoType') == 'VideoFile':
                play_video(server, item_id, item_name)
                browse_interactive(server, parent_id, path)
            else:
                print(f"Cannot play item: {item_name}")
                browse_interactive(server, parent_id, path)
        else:
            print("Invalid selection.")
            browse_interactive(server, parent_id, path)
    except ValueError:
        print("Invalid input.")
        browse_interactive(server, parent_id, path)


def play_video(server: JellyfinServer, item_id: str, name: str):
    """Play video using VLC"""
    url = server.get_download_url(item_id)
    try:
        subprocess.Popen([
            'vlc', url,
            '--no-video-title-show',
            '--input-title-format', name
        ])
        print(f"Playing: {name}")
    except FileNotFoundError:
        print("VLC not found. Please install VLC media player.", file=sys.stderr)
    except Exception as e:
        print(f"Error playing video: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='JellyCli - A command-line interface for Jellyfin'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'JellyCli {VERSION}'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all collections'
    )
    parser.add_argument(
        '--browse',
        metavar='PARENT_ID',
        help='Browse items under a specific parent ID'
    )
    parser.add_argument(
        '--play',
        metavar='ITEM_ID',
        help='Play a specific item by ID'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Start interactive browsing mode (default)'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    server = JellyfinServer(
        config['Host'],
        config['AuthKey'],
        config['UserId']
    )
    
    # Handle commands
    if args.list:
        collections = server.get_collections()
        print("\n=== Collections ===")
        display_items(collections)
    
    elif args.browse:
        items = server.get_child_items(args.browse)
        print(f"\n=== Items in {args.browse} ===")
        display_items(items)
    
    elif args.play:
        # For play, we need to get item details first
        # This is simplified - you may want to fetch item details
        play_video(server, args.play, "Video")
    
    else:
        # Default to interactive mode
        browse_interactive(server)


if __name__ == '__main__':
    main()
