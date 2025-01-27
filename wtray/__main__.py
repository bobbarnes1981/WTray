import json
import pystray
import requests

from PIL import Image

class WTray(object):
    def __init__(self, url):
        self.url = url
        self.state = False
        menu = pystray.Menu(
            pystray.MenuItem('checked', self.__checked, checked=lambda item: self.state),
            pystray.MenuItem('info', self.__info),
            pystray.MenuItem('state', self.__state),
            pystray.MenuItem('effects', self.__effects),
            pystray.MenuItem('palettes', self.__palettes),
            pystray.MenuItem('on', self.__on),
            pystray.MenuItem('off', self.__off),
            pystray.MenuItem('exit', self.__exit))
        self.icon = pystray.Icon("WLED", Image.open("wtray/icon.ico"), menu=menu)
    def __checked(self, icon, item):
        self.state = not self.state
    def __get(self, path):
        headers = {"Content-Type": "application/json"}
        r = requests.get(f"{self.url}/json/{path}", headers=headers)
        print(r)
        print(r.json())
        return r.json()
    def __post(self, path, data):
        headers = {"Content-Type": "application/json"}
        r = requests.post(f"{self.url}/json/{path}", headers=headers, data=json.dumps(data))
        print(r)
        print(r.json())
        return r.json()
    def __info(self, icon, item):
        self.__get("info")
    def __state(self, icon, item):
        self.__get("state")
    def __effects(self, icon, item):
        self.__get("effects")
    def __palettes(self, icon, item):
        self.__get("palettes")
    def __on(self, icon, item):
        self.__post("state", {"on": True})
    def __off(self, icon, item):
        self.__post("state", {"on": False})
    def __exit(self, icon, item):
        icon.stop()
    def run(self):
        self.icon.run()


WTray("http://192.168.1.207").run()
