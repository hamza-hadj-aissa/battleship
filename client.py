import socket
import threading
import sys
import select
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(name)s: %(message)s',
                    )


class Client:
    def __init__(self, host, port, close_event):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.close_event = close_event
        self.logger = logging.getLogger("Socket")

    def connect(self):
        connection = self.server_socket.connect_ex((self.host, self.port))
        if connection == 0:
            self.logger.info(f"Connected to server on {self.host}:{self.port}")
        else:
            self.logger.error(
                f"Connection failed to server on {self.host}:{self.port}")
            self.close_event.set()
            sys.exit()

    def receive_messages(self):
        while not self.close_event.is_set():
            sockets_list = [sys.stdin, self.server_socket]
            try:
                read_sockets, write_socket, error_socket = select.select(
                    sockets_list, [], [])
                for socks in read_sockets:
                    if socks == self.server_socket:
                        message = socks.recv(4096)
                        decoded_message = message.decode()
                        if (decoded_message == "close"):
                            self._close_connection_from_server()
                        else:
                            self.messages_logger.info(message.decode().strip())
            except socket.error as e:
                self.logger.error(f"Error connecting to the server: {e}")

    def send_message(self):
        while not self.close_event.is_set() and not sys.stdin.closed:
            try:
                message = sys.stdin.readline()
                if len(message) > 0:
                    if message.strip() == "close":
                        self._close_connection_from_client()
                    else:
                        self.server_socket.send(message.encode())
            except Exception as e:
                if {e} == "I/O operation on closed file":
                    self.logger.error({e})
        self.logger.info("Connection closed..!")

    def _close_connection_from_server(self):
        self.logger.warning("Closing connection...")
        self.server_socket.shutdown(socket.SHUT_RDWR)
        self.server_socket.close()
        self.close_event.set()

    def _close_connection_from_client(self):
        self.logger.warning("Closing connection...")
        try:
            self.server_socket.send("close".encode())
        except socket.error as e:
            self.logger.error(f"Error connecting to the server{e}")
            pass
        finally:
            self.server_socket.shutdown(socket.SHUT_RDWR)
            self.server_socket.close()
            self.close_event.set()


if __name__ == "__main__":
    # address = input("IP Address: ")
    # port = input("Port: ")
    close_event = threading.Event()

    client = Client("127.0.0.1", 12345, close_event)
    client.connect()

    send_thread = threading.Thread(
        target=client.send_message)
    receive_thread = threading.Thread(target=client.receive_messages)

    send_thread.start()
    receive_thread.start()

    close_event.wait()

    print("Press <Enter> to exit...")
