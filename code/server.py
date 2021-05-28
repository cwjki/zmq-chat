import argparse
import zmq

from config import *
 
class Server(object):

  def __init__(self, chat_interface, chat_port, display_interface, display_port):
    self.chat_interface = chat_interface
    self.chat_port = chat_port
    self.display_interface = display_interface
    self.display_port = display_port
    self.context = zmq.Context()
    self.chat_sock = None
    self.display_sock = None
  
  def bind_ports(self):
    self.chat_sock = self.context.socket(zmq.REP)
    chat_bind_string = 'tcp://{}:{}'.format(self.chat_interface, self.chat_port)
    self.chat_sock.bind(chat_bind_string)

    self.display_sock = self.context.socket(zmq.PUB)
    display_bind_string = 'tcp://{}:{}'.format(self.display_interface, self.display_port)
    self.display_sock.bind(display_bind_string)

  def get_message_with_username(self):
    data = self.chat_sock.recv_json()
    print(data)
    username = data['username']
    message = data['message']
    return [username, message]

  def update_displays(self, username, message):
    data = {
      'username' : username,
      'message' : message,
    }
    self.chat_sock.send(b'\x00')
    self.display_sock.send_json(data)

  def start_main_loop(self):
    self.bind_ports()
    while True:
      username, message = self.get_message_with_username()
      self.update_displays(username, message)
  
def parse_args():
  parser = argparse.ArgumentParser()
  return parser.parse_args()


args = parse_args()
server = Server('*', chat_port, '*', display_port)
server.start_main_loop()

