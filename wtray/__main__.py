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
            pystray.MenuItem('status', self.__status),
            pystray.MenuItem('on', self.__on),
            pystray.MenuItem('off', self.__off),
            pystray.MenuItem('exit', self.__exit))
        self.icon = pystray.Icon("WLED", Image.open("wtray/icon.ico"), menu=menu)
    def __checked(self, icon, item):
        self.state = not self.state
    def __status(self, icon, item):
        headers = {"Content-Type": "application/json"}
        r = requests.get(f"{self.url}/json/state", headers=headers)
        print(r.json())
    def __on(self, icon, item):
        headers = {"Content-Type": "application/json"}
        r = requests.post(f"{self.url}/json/state", headers=headers, data=json.dumps({"on": True}))
        print(r)
        print(r.json())
    def __off(self, icon, item):
        headers = {"Content-Type": "application/json"}
        r = requests.post(f"{self.url}/json/state", headers=headers, data=json.dumps({"on": False}))
        print(r.json())
    def __exit(self, icon, item):
        icon.stop()
    def run(self):
        self.icon.run()


WTray("http://192.168.1.207").run()
