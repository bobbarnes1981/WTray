"""Main WTray module"""
import json
import logging
import select
import socket
import threading
import time
import pystray
import requests

from PIL import Image

logging.basicConfig(level=logging.INFO)

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
    def __str__(self):
        return f"Name: {self.name} IP: {self.ip} Node: {self.type} {self.id} Version: {self.version} State: {self.state}"

class Discovery(object):
    """Class to listen to node udp messages"""
    def __init__(self):
        threading.Thread.__init__(self)
        self._logger = logging.getLogger(Discovery.__name__)
        self._running = False
        self._nodes= {}
    def getNodes(self):
        """Get the discovered nodes"""
        return self._nodes
    def stop(self):
        """Stop the task"""
        self._running = False
    def start(self):
        """Start the task"""
        self._running = True
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        client.setblocking(0)
        #client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client.bind(("", 65506))
        socket_timeout = 0.5
        self._logger.info("discover start")
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
                        self._logger.info(f"[NEW] {node}")
                        self._nodes[node.id] = node
                    if self._nodes[node.id] != node:
                        self._logger.info(f"[UPDATE] {node}")
                        self._nodes[node.id] = node
        self._running = False
        self._logger.info("discover end")

class MenuItemWithTag(pystray.MenuItem):
    """Wrapper for MenuItem with tag assigned"""
    def __init__(self, text, action, checked=None, radio=False, default=False, visible=True, enabled=True, tag=None):
        pystray.MenuItem.__init__(self, text, action, checked, radio, default, visible, enabled)
        self.tag = tag

class WTray(object):
    """WLED System Tray"""
    def __init__(self):
        self._logger = logging.getLogger(WTray.__name__)
        self.discovery = Discovery()
        menu = pystray.Menu(
            pystray.MenuItem('discover', lambda icon, item: self.__discover()),
            pystray.MenuItem('nodes', pystray.Menu(lambda: (
                pystray.MenuItem(node.name, pystray.Menu(
                    MenuItemWithTag('info', self.__info, tag=node.ip),
                    MenuItemWithTag('state', self.__state, tag=node.ip),
                    MenuItemWithTag('effects', self.__effects, tag=node.ip),
                    MenuItemWithTag('palettes', self.__palettes, tag=node.ip),
                    MenuItemWithTag('on', self.__on, tag=node.ip),
                    MenuItemWithTag('off', self.__off, tag=node.ip)
                ))
                for id, node in self.discovery.getNodes().items()
            ))),
            pystray.MenuItem('exit', lambda icon, item: self.__exit()))
        self.icon = pystray.Icon("WLED", Image.open("wtray/icon.ico"), menu=menu)
        self.__discover()
    def __get(self, ip, path):
        headers = {"Content-Type": "application/json"}
        r = requests.get(f"http://{ip}/json/{path}", headers=headers)
        self._logger.info(r)
        self._logger.info(r.json())
        return r.json()
    def __post(self, ip, path, data):
        headers = {"Content-Type": "application/json"}
        r = requests.post(f"http://{ip}/json/{path}", headers=headers, data=json.dumps(data))
        self._logger.info(r)
        self._logger.info(r.json())
        return r.json()
    def __discover(self):
        threading.Thread(target=self.discovery.start).start()
        time.sleep(32)
        self.icon.update_menu()
    def __info(self, icon, item):
        self.__get(item.tag, "info")
    def __state(self, icon, item):
        self.__get(item.tag, "state")
    def __effects(self, icon, item):
        self.__get(item.tag, "effects")
    def __palettes(self, icon, item):
        self.__get(item.tag, "palettes")
    def __on(self, icon, item):
        self.__post(item.tag, "state", {"on": True})
    def __off(self, icon, item):
        self.__post(item.tag, "state", {"on": False})
    def __exit(self):
        self.discovery.stop()
        self.icon.stop()
    def run(self):
        """Run the application"""
        self.icon.run()


WTray().run()
