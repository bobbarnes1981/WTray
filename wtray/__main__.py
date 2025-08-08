"""Main WTray module"""
import json
import logging
import select
import socket
import threading
import time
import os
import pickle
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
    def __init__(self, discovered_func):
        self._discovered_func = discovered_func
        self._logger = logging.getLogger(Discovery.__name__)
        self._running = False
        self._nodes= {}
    def get_sorted_nodes(self):
        """Get the discovered nodes"""
        return sorted((self._nodes.values()), key=lambda n: n.name)
    def set_nodes(self, nodes):
        """Set the nodes"""
        for node in nodes:
            self.__append_node(node)
    def __append_node(self, node):
        if node.id not in self._nodes:
            self._logger.info("[NEW] %s", node)
            self._nodes[node.id] = node
        if self._nodes[node.id] != node:
            self._logger.info("[UPDATE] %s", node)
            self._nodes[node.id] = node
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
                self._logger.info("Received from: %s", addr)
                msg_token = data[0] # 255
                msg_id = data[1] # 1
                if msg_token == 255 and msg_id == 1:
                    node = Node(data)
                    self.__append_node(node)
                    self._discovered_func()
        self._running = False
        self._discovered_func()
        self._logger.info("discover end")

class MenuItemWithTag(pystray.MenuItem):
    """Wrapper for MenuItem with tag assigned"""
    def __init__(self, text, action, checked=None, radio=False, default=False, visible=True, enabled=True, tag=None):
        pystray.MenuItem.__init__(self, text, action, checked, radio, default, visible, enabled)
        self.tag = tag

class WTray(object):
    """WLED System Tray"""
    config_cache = "nodes.bin"
    def __init__(self):
        self._logger = logging.getLogger(WTray.__name__)
        self.discovery = Discovery(self.__discovered)
        self._timeout = 5
        nodes = []
        if os.path.isfile(self.config_cache):
            with open(self.config_cache, 'rb') as config:
                nodes = pickle.load(config)
        self.discovery.set_nodes(nodes)
    
        #menu = pystray.Menu(
        #    pystray.MenuItem('Discover', self.__click_discover()),
        #    pystray.MenuItem('Nodes', pystray.Menu(lambda: (
        #        pystray.MenuItem(node.name, pystray.Menu(
        #            MenuItemWithTag('Info', self.__click_info, tag=node.ip),
        #            MenuItemWithTag('State', self.__click_state, tag=node.ip),
        #            MenuItemWithTag('Effects', self.__click_effects, tag=node.ip),
        #            MenuItemWithTag('Palettes', self.__click_palettes, tag=node.ip),
        #            MenuItemWithTag('On', self.__click_on, tag=node.ip),
        #            MenuItemWithTag('Off', self.__click_off, tag=node.ip)
        #        ))
        #        for node in self.discovery.get_sorted_nodes()
        #    ))),
        #    pystray.MenuItem('Exit', self.__click_exit()))

        menu = pystray.Menu(lambda: (n for n in self.__get_menu_items()))

        self.icon = pystray.Icon("WLED", Image.open("wtray/icon.ico"), menu=menu)
        self.__discover()

    def __get_menu_items(self):
        dis = [pystray.MenuItem('Discover', self.__click_discover)]
        nodes = [(pystray.MenuItem(node.name, pystray.Menu(
                MenuItemWithTag('Info', self.__click_info, tag=node.ip),
                MenuItemWithTag('State', self.__click_state, tag=node.ip),
                MenuItemWithTag('Effects', self.__click_effects, tag=node.ip),
                MenuItemWithTag('Palettes', self.__click_palettes, tag=node.ip),
                MenuItemWithTag('On', self.__click_on, tag=node.ip),
                MenuItemWithTag('Off', self.__click_off, tag=node.ip)
            ))) for node in self.discovery.get_sorted_nodes()]
        ex = [pystray.MenuItem('Exit', self.__click_exit)]
        return dis + nodes + ex
    def __get(self, ip, path):
        headers = {"Content-Type": "application/json"}
        r = requests.get(f"http://{ip}/json/{path}", headers=headers, timeout=self._timeout)
        self._logger.info(r)
        self._logger.info(r.json())
        return r.json()
    def __post(self, ip, path, data):
        headers = {"Content-Type": "application/json"}
        r = requests.post(f"http://{ip}/json/{path}", headers=headers, data=json.dumps(data), timeout=self._timeout)
        self._logger.info(r)
        self._logger.info(r.json())
        return r.json()
    def __discovered(self):
        self.icon.update_menu()
        with open(self.config_cache, 'wb') as config:
            pickle.dump(self.discovery.get_sorted_nodes(), config, pickle.HIGHEST_PROTOCOL)

    def __click_discover(self, icon, item):
        self.__discover()
    def __click_info(self, icon, item):
        self.__get(item.tag, "info")
    def __click_state(self, icon, item):
        self.__get(item.tag, "state")
    def __click_effects(self, icon, item):
        self.__get(item.tag, "effects")
    def __click_palettes(self, icon, item):
        self.__get(item.tag, "palettes")
    def __click_on(self, icon, item):
        self.__post(item.tag, "state", {"on": True})
    def __click_off(self, icon, item):
        self.__post(item.tag, "state", {"on": False})
    def __click_exit(self, icon, item):
        self.__exit()

    def __discover(self):
        threading.Thread(target=self.discovery.start).start()
    def __exit(self):
        self.discovery.stop()
        self.icon.stop()

    def run(self):
        """Run the application"""
        self.icon.run()

WTray().run()
