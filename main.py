import time
import json
import base64
import pickle
import requests
from pypresence import Presence
from cmyui.logging import Ansi
from cmyui.logging import log

def main():
    try:
        with open("album_cache.p", "rb") as f:
            album_cache = pickle.load(f)
    except FileNotFoundError:
        album_cache = []
        with open("album_cache.p", "wb") as f:
            pickle.dump(album_cache, f)
    with open("config.json") as f:
        config = json.load(f)
    with open('replace.json') as content:
        replace = json.load(content)

    LASTFM_API_URL = f"http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks&user={config['lastfm_name']}&api_key={config['lastfm_api_key']}&format=json"
    DISCORD_API_POST_URL = f"https://discord.com/api/v8/oauth2/applications/{config['client_id']}/assets"

    if "lfm" in album_cache:
        log("small image found! skipping first cache process...", Ansi.YELLOW)
    else:
        log("attn: small image not found! caching...", Ansi.YELLOW)
        requests.post(DISCORD_API_POST_URL.format(client_id=config['client_id']),
                      json={"name": "lfm",
                            "image": config['lfmimg'],
                            "type": 1},
                      headers={"Authorization": config['discord_token'],
                               "content-type": "application/json"})
        album_cache.append("lfm")
        with open("album_cache.p", "wb") as f:
            pickle.dump(album_cache, f)
        log("cached successfully!", Ansi.GREEN)

    rpc = Presence(client_id=config['client_id'], pipe=0)
    rpc.connect()

    while True:
        try:
            trackinfo = requests.get(LASTFM_API_URL.format(user=config["lastfm_name"],
                                                           key=config["lastfm_api_key"])).json()
            trackinfo = trackinfo["recenttracks"]["track"][0]
            artist = trackinfo['artist']['#text']
            album = trackinfo["album"]["#text"]
            track = trackinfo["name"]
            album_name = album.translate(str.maketrans(replace)).lower()[:32]
            formatted_album = ''.join([str(ord(x) - 96) for x in album_name])[:32]
            
            if formatted_album not in album_cache:
                log(f"attn: {album_name} not found in album cache, caching...", Ansi.YELLOW)
                cover_img = "data:image/jpeg;base64," + str(base64.b64encode(requests.get(trackinfo["image"][1]["#text"]).content), "utf-8")
                log(f"converted {album} album image successfully!", Ansi.GREEN)
                requests.post(DISCORD_API_POST_URL.format(client_id=config["client_id"]),
                              json={"name": formatted_album,
                                    "image": cover_img,
                                    "type": 1},
                              headers={"Authorization": config["discord_token"],
                                       "content-type": "application/json"})
                log(f"{album} sent to discord correctly!", Ansi.GREEN)
                album_cache.append(formatted_album)
                with open("album_cache.p", "wb") as f:
                    pickle.dump(album_cache, f)
                log("cached succesfully!\n", Ansi.GREEN)

            rpc.update(details=f"{track}",
                       state=f"by {artist}",
                       large_image=formatted_album if formatted_album else None,
                       small_image="lfm",
                       small_text=f"scrobbling on account {config['lastfm_name']}",
                       large_text=album_name if album_name else None)
            
            old_track = ""

            if old_track not in track:
                log(f"attn: updating rpc with current track {trackinfo['name']}...", Ansi.YELLOW)
                old_track = trackinfo["name"]
                log("successfully set rpc!", Ansi.GREEN)
                log("waiting for next track...")

            time.sleep(0.3)

        except Exception as e:
            log(f"exception occurred: {e}", Ansi.RED)

if __name__ == '__main__':
    log("welcome to listening-to!\n")
    main()
