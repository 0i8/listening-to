import time
import json
import base64
import pickle
import requests
from pypresence import Presence
from cmyui.logging import Ansi, log


def load_album_cache(file_path):
    try:
        with open(file_path, "rb") as f:
            album_cache = pickle.load(f)
    except FileNotFoundError:
        album_cache = []
        save_album_cache(album_cache, file_path)
    return album_cache


def save_album_cache(album_cache, file_path):
    with open(file_path, "wb") as f:
        pickle.dump(album_cache, f)


def post_discord_asset(client_id, discord_token, asset_data):
    discord_api_post_url = f"https://discord.com/api/v8/oauth2/applications/{client_id}/assets"
    headers = {"Authorization": discord_token, "Content-Type": "application/json"}
    response = requests.post(discord_api_post_url, json=asset_data, headers=headers)
    response.raise_for_status()


def fetch_track_info(lastfm_api_url, user, api_key):
    response = requests.get(lastfm_api_url.format(user=user, key=api_key))
    response.raise_for_status()
    return response.json()["recenttracks"]["track"][0]


def main():
    with open("config.json") as f:
        config = json.load(f)

    album_cache = load_album_cache("album_cache.p")
    replace = {}

    lastfm_api_url = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={config['lastfm_name']}&api_key={config['lastfm_api_key']}&format=json"
    discord_api_post_url = f"https://discord.com/api/v8/oauth2/applications/{config['client_id']}/assets"

    if "lfm" not in album_cache:
        log("caching small image...", Ansi.YELLOW)
        post_discord_asset(config["client_id"], config["discord_token"], {"name": "lfm", "image": config["lfmimg"], "type": 1})
        album_cache.append("lfm")
        save_album_cache(album_cache, "album_cache.p")
        log("cached successfully!", Ansi.GREEN)

    rpc = Presence(client_id=config["client_id"], pipe=0)
    rpc.connect()

    old_track = ""

    while True:
        try:
            track_info = fetch_track_info(lastfm_api_url, config["lastfm_name"], config["lastfm_api_key"])
            artist = track_info["artist"]["#text"]
            album = track_info["album"]["#text"]
            track = track_info["name"]
            album_name = album.lower().translate(str.maketrans(replace))[:32]
            formatted_album = ''.join(str(ord(x) - 96) for x in album_name)[:32]

            if formatted_album not in album_cache:
                log(f"caching album: {album_name}...", Ansi.YELLOW)
                cover_img = "data:image/jpeg;base64," + base64.b64encode(requests.get(track_info["image"][1]["#text"]).content).decode("utf-8")
                log(f"converted {album}'s album image successfully!", Ansi.GREEN)
                post_discord_asset(config["client_id"], config["discord_token"], {"name": formatted_album, "image": cover_img, "type": 1})
                log(f"{album} sent to discord correctly!", Ansi.GREEN)
                album_cache.append(formatted_album)
                save_album_cache(album_cache, "album_cache.p")
                log("cached successfully!", Ansi.GREEN)

            if old_track != track:
                log(f"updating RPC with current track: {track}...", Ansi.YELLOW)
                old_track = track
                log("successfully set RPC!", Ansi.GREEN)
                log("waiting for the next track...")

            rpc.update(details=track, state=f"by {artist}", large_image=formatted_album or None,
                       small_image="lfm", small_text=f"scrobbling on account {config['lastfm_name']}",
                       large_text=album_name or None)

            time.sleep(0.3)

        except requests.exceptions.HTTPError as http_err:
            log(f"HTTP error occurred: {http_err}", Ansi.RED)
        except requests.exceptions.RequestException as err:
            log(f"exception occurred during request: {err}", Ansi.RED)
        except Exception as e:
            log(f"unknown exception occurred: {e}", Ansi.RED)


if __name__ == '__main__':
    log("welcome to listening-to!\n")
    main()
