import json
import pystray
import requests
import select
import socket
import threading
import time

from PIL import Image

class Node(object):
    node_types = {
        0: "Undefined",
        82: "ESP8266",
        32: "ESP32",
        33: "ESP32S2",
        34: "ESP32S3",
        35: "ESP32C3"
    }
    def __init__(self, data):
        self.ip = f"{data[2]}.{data[3]}.{data[4]}.{data[5]}"
        self.name = data[6:38].decode('utf-8')
        self.type = self.node_types[data[38]] if data[38] in self.node_types else data[38]
        self.id = data[39]
        self.version = data[40] | (data[41] << 8) | (data[42]<< 16) | (data[43] << 24)


class Discovery(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self._running = False
        self.nodes= {}
    def stop(self):
        self._running = False
    def run(self, *args, **kwargs):
        self._running = True
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        client.setblocking(0)
        #client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client.bind(("", 65506))
        socket_timeout = 0.5
        print("discover")
        while self._running:
            ready = select.select([client], [], [], socket_timeout)
            if ready[0]:
                data, addr = client.recvfrom(1024)
                token = data[0] # 255
                id = data[1] # 1
                if token == 255 and id == 1:
                    node = Node(data)
                    self.nodes[node.id] = node
                    print("msg")
                    print(data)
                    print(f"Name: {node.name} IP: {node.ip} Node: {node.type} {node.id} Version: {node.version}")

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
        self.discovery = Discovery()
        self.discovery.start()
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
        self.discovery.stop()
        icon.stop()
    def run(self):
        self.icon.run()


WTray("http://192.168.1.207").run()
