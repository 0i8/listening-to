import time
import json
import base64
import pickle
import requests
from typing import List, Dict
from pypresence import Presence
from cmyui.logging import Ansi, log

# constants
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={user}&api_key={key}&format=json"
DISCORD_API_POST_URL = "https://discord.com/api/v8/oauth2/applications/{client_id}/assets"

def load_album_cache(file_path: str) -> List[str]:
    """load the album cache from a pickle file."""
    try:
        with open(file_path, "rb") as f:
            return pickle.load(f)
        log("opened album cache successfully!", Ansi.GREEN)
    except FileNotFoundError:
        save_album_cache([], file_path)
        return []

def load_replace_file(file_path: str) -> Dict[str, str]:
    """load the replace file containing character replacements for album names"""
    try:
        with open(file_path) as f:
            return json.load(f)
        log("opened replace file successfully!", Ansi.GREEN)
    except FileNotFoundError:
        return {}

def save_album_cache(album_cache: List[str], file_path: str) -> None:
    """save the album cache to a pickle file."""
    try:
        with open(file_path, "wb") as f:
            pickle.dump(album_cache, f)
        log("saved album cache successfully!", Ansi.GREEN)
    except Exception as e:
        log(f"we failed to save the album cache.. {e}", Ansi.RED)

def post_discord_asset(client_id: str, discord_token: str, asset_data: Dict[str, str]) -> None:
    """post an asset (our album image) to discord using its' API."""
    headers = {"Authorization": discord_token, "Content-Type": "application/json"}
    response = requests.post(DISCORD_API_POST_URL.format(client_id=client_id), json=asset_data, headers=headers)
    response.raise_for_status()

def fetch_track_info(lastfm_api_url: str, user: str, api_key: str) -> Dict[str, str]:
    """fetch track information from the last.fm API."""
    response = requests.get(lastfm_api_url.format(user=user, key=api_key))
    response.raise_for_status()
    return response.json()["recenttracks"]["track"][0]

def update_rpc_with_track(track_info: Dict[str, str], rpc: Presence) -> str:
    """update the RPC with the current track information."""
    global last_track_info, album_cache, replace

    track = track_info["name"]
    artist = track_info["artist"]["#text"]
    album = track_info["album"]["#text"]
    album_name = album.lower().translate(str.maketrans(replace))[:32]
    formatted_album = ''.join(str(ord(x) - 96) for x in album_name)[:32]

    if formatted_album not in album_cache:
        log(f"caching album: {album_name}...", Ansi.YELLOW)
        cover_img = "data:image/jpeg;base64," + base64.b64encode(requests.get(track_info["image"][1]["#text"]).content).decode("utf-8")

        if cover_img:
            log(f"converted {album}'s album image successfully!", Ansi.GREEN)
        else:
            log(f"{album}'s image failed to convert, or there is no image to convert.")

        try:
            post_discord_asset(config["client_id"], config["discord_token"], {"name": formatted_album, "image": cover_img, "type": 1})
            log(f"{album} sent to discord successfully (as {formatted_album})!", Ansi.GREEN)
            album_cache.append(formatted_album)
            save_album_cache(album_cache, "album_cache.p")
        except requests.exceptions.HTTPError as http_err:
            log(f"failed to post album to discord: {http_err}", Ansi.RED)

    if last_track_info != track:
        log(f"updating RPC with current track: {track}...", Ansi.YELLOW)
        last_track_info = track
        log("successfully set RPC!", Ansi.GREEN)

    rpc.update(
        details=track,
        state=f"by {artist}",
        large_image=formatted_album or None,
        small_image="lfm",
        small_text=f"{config['small_tooltip_text']}",
        large_text=album or None
    )

    return track

def initialize():
    """load everything useful to use that we won't need to load again."""
    global album_cache, replace, last_track_info
    album_cache = load_album_cache("album_cache.p")
    replace = load_replace_file("replace.json")
    last_track_info = None

def main():
    """main function to run the script."""
    initialize()

    lastfm_api_url = LASTFM_API_URL.format(user=config['lastfm_name'], key=config['lastfm_api_key'])

    if "lfm" not in album_cache:
        log("caching small image...", Ansi.YELLOW)
        try:
            post_discord_asset(config["client_id"], config["discord_token"], {"name": "lfm", "image": config["lfmimg"], "type": 1})
            album_cache.append("lfm")
            save_album_cache(album_cache, "album_cache.p")
            log("cached successfully!", Ansi.GREEN)
        except requests.exceptions.HTTPError as http_err:
            log(f"failed to post small image to Discord: {http_err}", Ansi.RED)
    else:
        log("small image is already cached. skipping...", Ansi.YELLOW)

    rpc = Presence(client_id=config["client_id"], pipe=0)
    rpc.connect()

    last_track_info = None

    while True:
        try:
            if not last_track_info:
                track_info = fetch_track_info(lastfm_api_url, config["lastfm_name"], config["lastfm_api_key"])
                last_track_info = update_rpc_with_track(track_info, rpc)

            time.sleep(0.3)
            track_info = fetch_track_info(lastfm_api_url, config["lastfm_name"], config["lastfm_api_key"])
            track = track_info["name"]

            if last_track_info != track:
                last_track_info = update_rpc_with_track(track_info, rpc)
        except requests.exceptions.RequestException as e:
            log(f"exception occurred during request: {e}", Ansi.RED)
        except Exception as e:
            log(f"unknown exception occurred: {e}", Ansi.RED)

if __name__ == '__main__':
    log("welcome to listening-to!\n")

    with open("config.json") as f:
        config = json.load(f)

    main()
