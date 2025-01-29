"""Main WTray module"""
import json
import select
import socket
import threading
import pystray
import requests
import time

from PIL import Image

class Node(object):
    """Class representing the node udp information"""
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
        type_id_state = data[38]
        self.state = type_id_state & 0x80 == 0x80
        type_id = type_id_state & 0x7F
        self.type = self.node_types[type_id] if type_id in self.node_types else type_id
        self.id = data[39]
        self.version = data[40] | (data[41] << 8) | (data[42]<< 16) | (data[43] << 24)
    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.ip == other.ip and self.name == other.name and self.state == other.state and self.type == other.type and self.id == other.id and self.version == other.version

class Discovery(threading.Thread):
    """Thread to listen to node udp messages"""
    def __init__(self):
        threading.Thread.__init__(self)
        self._running = False
        self._nodes= {}
    def stop(self):
        """Stop the thread"""
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
        print("discover start")
        t = time.time()
        sysinfo_timeout = 31 # sysinfo is sent over UDP every 30 seconds
        while self._running and time.time() - t < sysinfo_timeout:
            ready = select.select([client], [], [], socket_timeout)
            if ready[0]:
                data, addr = client.recvfrom(1024)
                msg_token = data[0] # 255
                msg_id = data[1] # 1
                if msg_token == 255 and msg_id == 1:
                    node = Node(data)
                    if node.id not in self._nodes:
                        print("new node")
                        self._nodes[node.id] = node
                        print(f"Name: {node.name} IP: {node.ip} Node: {node.type} {node.id} Version: {node.version} State: {node.state}")
                    if self._nodes[node.id] != node:
                        print("update node")
                        self._nodes[node.id] = node
                        print(f"Name: {node.name} IP: {node.ip} Node: {node.type} {node.id} Version: {node.version} State: {node.state}")
        self._running = False
        print("discover end")

class WTray(object):
    """WLED System Tray"""
    def __init__(self, url):
        self.discovery = Discovery()
        menu = pystray.Menu(
            pystray.MenuItem('discover', lambda icon, item: self.__discover()),
            pystray.MenuItem('nodes', pystray.Menu(lambda: (
                pystray.MenuItem(url, pystray.Menu(
                    pystray.MenuItem('info', lambda icon, item: self.__info(url)),
                    pystray.MenuItem('state', lambda icon, item: self.__state(url)),
                    pystray.MenuItem('effects', lambda icon, item: self.__effects(url)),
                    pystray.MenuItem('palettes', lambda icon, item: self.__palettes(url)),
                    pystray.MenuItem('on', lambda icon, item: self.__on(url)),
                    pystray.MenuItem('off', lambda icon, item: self.__off(url))
                ))
                for url in {url: None}
            ))),
            pystray.MenuItem('exit', lambda icon, item: self.__exit()))
        self.icon = pystray.Icon("WLED", Image.open("wtray/icon.ico"), menu=menu)
        self.__discover()
    def __get(self, url, path):
        headers = {"Content-Type": "application/json"}
        r = requests.get(f"{url}/json/{path}", headers=headers)
        print(r)
        print(r.json())
        return r.json()
    def __post(self, url, path, data):
        headers = {"Content-Type": "application/json"}
        r = requests.post(f"{url}/json/{path}", headers=headers, data=json.dumps(data))
        print(r)
        print(r.json())
        return r.json()
    def __discover(self):
        self.discovery.start()
    def __info(self, url):
        self.__get(url, "info")
    def __state(self, url):
        self.__get(url, "state")
    def __effects(self, url):
        self.__get(url, "effects")
    def __palettes(self, url):
        self.__get(url, "palettes")
    def __on(self, url):
        self.__post(url, "state", {"on": True})
    def __off(self, url):
        self.__post(url, "state", {"on": False})
    def __exit(self):
        self.discovery.stop()
        self.icon.stop()
    def run(self):
        """Run the application"""
        self.icon.run()


WTray("http://192.168.1.207").run()
