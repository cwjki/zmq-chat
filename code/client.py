import argparse
import curses
import threading
import time
import zmq

from curses import wrapper
from config import *

class ClientChat(object):

  def __init__(self, username, server_host, server_port, chat_pipe):
    self.username = username
    self.server_host = server_host
    self.server_port = server_port
    self.chat_pipe = chat_pipe
    self.context = zmq.Context()
    self.chat_sock = None
    self.poller = zmq.Poller()

  def connect_to_server(self):
    self.chat_sock = self.context.socket(zmq.REQ)
    connect_string = 'tcp://{}:{}'.format(self.server_host, self.server_port)
    self.chat_sock.connect(connect_string)

  def reconnect_to_server(self):
    self.poller.unregister(self.chat_sock)
    self.chat_sock.setsockopt(zmq.LINGER, 0)
    self.chat_sock.close()
    self.connect_to_server()
    self.register_with_poller()

  def register_with_poller(self):
    self.poller.register(self.chat_sock, zmq.POLLIN)

  def prompt_for_message(self):
    return self.chat_pipe.recv_string()

  def send_message(self, message):
    data = {
        'username': self.username,
        'message': message,
    }
    self.chat_sock.send_json(data)

  def get_reply(self):
    self.chat_sock.recv()

  def has_message(self):
    events = dict(self.poller.poll(3000))
    return events.get(self.chat_sock) == zmq.POLLIN

  def start_main_loop(self):
    self.connect_to_server()
    self.register_with_poller()

    while True:
      message = self.prompt_for_message()
      self.send_message(message)
      if self.has_message():
        self.get_reply()
      else:
        self.reconnect_to_server()

  def run(self):
    thread = threading.Thread(target=self.start_main_loop)
    thread.deamon = True
    thread.start()

class ClientDisplay(object):

  def __init__(self, server_host, server_port, display_pipe):
    self.server_host = server_host
    self.server_port = server_port
    self.context = zmq.Context()
    self.display_sock = None
    self.display_pipe = display_pipe
    self.poller = zmq.Poller()

  def connect_to_server(self):
    self.display_sock = self.context.socket(zmq.SUB)
    self.display_sock.setsockopt_string(zmq.SUBSCRIBE, '')
    connect_string = 'tcp://{}:{}'.format(self.server_host, self.server_port)
    self.display_sock.connect(connect_string)
    self.poller.register(self.display_sock, zmq.POLLIN)

  def get_update(self):
    data = self.display_sock.recv_json()
    username, message = data['username'], data['message']
    self.display_pipe.send_string('{}:{}'.format(username, message))

  def has_message(self):
    events = self.poller.poll()
    return self.display_sock in events

  def start_main_loop(self):
    self.connect_to_server()
    while True:
      self.get_update()

  def run(self):
    thread = threading.Thread(target=self.start_main_loop)
    thread.daemon = True
    thread.start()


def parse_args():
  parser = argparse.ArgumentParser(description='Run a chat client')

  # maybe make selection of username interactive
  parser.add_argument('username',
                      type=str,
                      help='your preferred username')
  parser.add_argument('--config-file',
                      type=str,
                      help='path to an alternate config file, defaults to zmqchat.cfg')

  return parser.parse_args()

def start_top_window(window, display):
  window_lines, window_cols = window.getmaxyx()
  bottom_line = window_lines - 1
  window.bkgd(curses.A_NORMAL, curses.color_pair(2))
  window.scrollok(1)
  while True:
    window.addstr(bottom_line, 1, display.recv_string())
    window.move(bottom_line, 1)
    window.scroll(1)
    window.refresh()

def start_bottom_window(window, chat_sender):
  window.bkgd(curses.A_NORMAL, curses.color_pair(2))
  window.clear()
  window.box()
  window.refresh()
  while True:
    window.clear()
    window.box()
    window.refresh()
    s = window.getstr(1, 1).decode('utf-8')
    if s is not None and s != "":
      chat_sender.send_string(s)

    time.sleep(0.005)

def main(stdscr):
  receiver = zmq.Context().instance().socket(zmq.PAIR)
  receiver.bind("inproc://clientchat")
  sender = zmq.Context().instance().socket(zmq.PAIR)
  sender.connect("inproc://clientchat")
  client = ClientChat(args.username, server_host, chat_port, receiver)
  client.run()

  display_receiver = zmq.Context().instance().socket(zmq.PAIR)
  display_receiver.bind("inproc://clientdisplay")
  display_sender = zmq.Context().instance().socket(zmq.PAIR)
  display_sender.connect("inproc://clientdisplay")

  display = ClientDisplay(server_host, display_port, display_sender)
  display.run()

  # curses set up
  stdscr = curses.initscr()

  curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
  curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
  # ensure that the user input is echoed to the screen
  curses.echo()
  curses.curs_set(0)

  window_height = curses.LINES
  window_width = curses.COLS
  division_line = int(window_height * 0.8)

  # instaniate two pads - one for displaying received messages
  # and one for showing the message the user is about to send off
  top_pad = stdscr.subpad(division_line, window_width, 0, 0)
  bottom_pad = stdscr.subpad(
      window_height - division_line, window_width, division_line, 0)

  top_thread = threading.Thread(
      target=start_top_window, args=(top_pad, display_receiver))
  top_thread.daemon = True
  top_thread.start()

  button_thread = threading.Thread(
      target=start_bottom_window, args=(bottom_pad, sender))
  button_thread.daemon = True
  button_thread.start()

  top_thread.join()
  button_thread.join()



args = parse_args()
wrapper(main)


