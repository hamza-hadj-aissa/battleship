import json
from random import randint
import socket
import sys
import threading
import logging
from time import sleep, time
from typing import List
from game import Field, Ship


logging.basicConfig(level=logging.INFO,
                    format='%(name)s: %(message)s',
                    )

MAX_DAMAGED_COORDINATES = 5
FIELD_HEIGHT = 10
FIELD_WIDTH = 10


class TooManyPlayersError(Exception):
    pass


class Socket_address():
    def __init__(self, ip, port):
        self.__ip = ip
        self.__port = port

    def getIp(self):
        return self.__ip

    def setIp(self, ip):
        self.__ip = ip

    def getPort(self):
        return self.__port

    def setPort(self, port):
        self.__port = port

    def __eq__(self, address):
        if isinstance(address, Socket_address):
            return self.getIp() == address.getIp() and self.getPort() == address.getPort()
        return False


class Client():
    def __init__(self, socket: socket.socket, address: Socket_address):
        self.__socket: socket = socket
        self.__address: Socket_address = address
        self.__field: Field = Field(FIELD_WIDTH, FIELD_HEIGHT)
        self.__blocking_event = threading.Event()

    def getSocket(self) -> socket.socket:
        return self.__socket

    def setSocket(self, socket):
        self.__socket = socket

    def getAddress(self):
        return self.__address

    def setAddress(self, address):
        self.__address = address

    def getField(self):
        return self.__field

    def setField(self, field: Field):
        self.__field = field

    def isPlacedShips(self):
        return len(self.getField().getShips()) != 0

    def getBlockingEvent(self):
        return self.__blocking_event

    def __eq__(self, client):
        if isinstance(client, Client):
            return client.getAddress() == self.__address
        return False


class Server:
    def __init__(self, server_address, close_event):
        self.host = server_address[0]
        self.port = server_address[1]
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__clients: List[Client] = list()
        self.games: List[Game] = list()
        self.close_event = close_event
        self.lock = threading.Lock()
        self.logger = logging.getLogger("Server")

    def getClients(self):
        return self.__clients

    def start(self):
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(4)
        self.logger.info(f"Listening on {self.host}:{self.port}")
        while not self.close_event.is_set():
            try:
                client_socket, client_address = self.server_socket.accept()
                self.logger.info(
                    f"Connection from client {
                        client_address[0]}:{client_address[1]}"
                )

                new_client = Client(
                    socket=client_socket,
                    address=client_address
                )
                with self.lock:
                    self.__clients.append(new_client)

                # # assign a thread for each new subscribed client
                client_handler = threading.Thread(
                    target=self.__handle_client, args=(new_client,)
                )
                client_handler.start()

                if len(self.__clients) % 2 == 0:
                    player1 = self.__clients[-2]
                    player2 = self.__clients[-1]
                    new_game = Game(self)
                    new_game.addPlayer(player1)
                    new_game.addPlayer(player2)
                    with self.lock:
                        self.games.append(new_game)
                    self.logger.info(
                        f"New game - Player {player1.getAddress()} VS {player2.getAddress()}")
                    new_game_thread = threading.Thread(
                        target=new_game.start_game
                    )
                    new_game_thread.start()

            except KeyboardInterrupt:
                self._close_server()
            except socket.error as e:
                if 'bad file descriptor' in str(e):
                    self.logger.error(
                        "Server socket is closed or shutdown..!")
                else:
                    self.logger.error(
                        f"Error accepting or handling new connections: {e}")

    # handle client
    def __handle_client(self, client: Client):
        try:
            time_interval = 3
            while not client.getBlockingEvent().is_set():
                client.getSocket().send(
                    json.dumps(
                        {
                            "type": "wait_for_opponent",
                            "message": f"Server << Waiting for your opponent to join.."
                        }
                    )
                    .encode()
                )
            # client.getBlockingEvent().wait()
                time_interval += 3
                sleep(time_interval)

            # client.getSocket().send("Server << Opponent has joined. Here we go!!".encode())
            client.getBlockingEvent().clear()
            client.getBlockingEvent().wait()

        except KeyboardInterrupt:
            self._close_server()
        except socket.error as e:
            # send a close signal to client's socket when ERROR
            self.logger.warning(f"Error handling client: {e}")
            # close connection with client on ERROR
            with self.lock:
                self.__clients.remove(client)

    def broadcast(self, message, clients: list[Client]):
        for client in clients:
            try:
                client.getSocket().send(message)
            except Exception as e:
                self.logger.error(f"Error broadcasting to client: {e}")
                # close connection with client on ERROR
                with self.lock:
                    self.__clients.remove(client)

    def delete_client_from_clients_list(self, client_to_delete: Client):
        return [client for client in self.__clients if client.getUsername() != client_to_delete.getUsername()]

    def _disconnect_client(self, client: Client):
        # close connection with client
        with self.lock:
            self.__clients.remove(client)
            self.logger.info(
                f"{client.getAddress()} has disconnected")

    def _close_server(self):
        self.logger.warning(
            f"Server is shutting down. Informing clients...")
        # send closing message to all subscribed clients
        for client in self.__clients:
            client_username = client.getUsername()
            try:
                self.logger.warning(
                    f"Informing client {client_username}...")
                # close connection from client side
                client_socket = client.getSocket()
                client_socket.send("close".encode())
                # close connection from server side
                client_socket.shutdown(socket.SHUT_RDWR)
                client_socket.close()
            except Exception as e:
                self.logger.error(
                    f"Error sending shutdown message to {client_username}: {e}")

        # clear clients list
        with self.lock:
            self.__clients.clear()

        try:
            # Close the server socket
            if not sys.stdin.closed:
                sys.stdin.close()
            self.server_socket.shutdown(socket.SHUT_RDWR)
            self.server_socket.close()
            self.close_event.set()
        except Exception as e:
            self.logger.error({e})
        self.logger.warning("Server has shut down.")


class Game:
    id = 0

    def __init__(self, server: Server):
        self.players: List[Client] = list()
        self.gameServer = server
        self.lock = threading.Lock()
        self.game_close_event = threading.Event()
        self.logger = logging.getLogger("Game")
        Game.id += 1

    def start_game(self):
        player1, player2 = self.players
        players_coordinates = []
        # Start the battleship
        self.logger.info(
            f"Game Started {player1.getAddress()} VS {
                player2.getAddress()}"
        )
        # choose the player who is gonna launch the first hit randomly
        starting_client_turn = randint(0, 1)
        try:
            self.gameServer.broadcast(json.dumps(
                {
                    "type": "start_game",
                }
            ).encode(), [player1, player2]
            )
            # assign a thread for each player to retrieve their coordinates
            player1__handle_receive_coordinates = threading.Thread(
                target=self.__handle_receive_coordinates, args=(
                    player1, players_coordinates, starting_client_turn), daemon=True
            )
            player2__handle_receive_coordinates = threading.Thread(
                target=self.__handle_receive_coordinates, args=(
                    player2, players_coordinates, starting_client_turn), daemon=True
            )
            player1__handle_receive_coordinates.start()
            player2__handle_receive_coordinates.start()

            # wait for both threads to finish
            player1__handle_receive_coordinates.join()
            player2__handle_receive_coordinates.join()

            # send player's coordinates to the other player
            for player_coordinates in players_coordinates:
                coordinates_json = json.dumps(
                    player_coordinates["player_coordinates"]
                )
                if player_coordinates["player_index"] == 0:
                    self.gameServer.broadcast(
                        coordinates_json.encode(), [player2]
                    )
                else:
                    self.gameServer.broadcast(
                        coordinates_json.encode(), [player1]
                    )

            # assign a thread for each player to receive and forward attacks and attack statuses
            player1_attacks_handler = threading.Thread(
                target=self.___handle_client, args=(player1,))
            player2_attacks_handler = threading.Thread(
                target=self.___handle_client, args=(player2,))

            player1_attacks_handler.start()
            player2_attacks_handler.start()

            # wait for both threads to finish
            player1_attacks_handler.join()
            player2_attacks_handler.join()

            player1.getBlockingEvent().set()
            player2.getBlockingEvent().set()
            self.gameServer._disconnect_client(player1)
            self.gameServer._disconnect_client(player2)

            self.game_close_event.set()
            self.gameServer.games.remove(self)
            return
        except KeyboardInterrupt:
            self.gameServer._close_server()

    def addPlayer(self, player: Client):
        if len(self.players) < 2:
            self.logger.info(f"Adding new player to the game N°{self.id}")
            self.players.append(player)
        else:
            raise TooManyPlayersError(
                f"Number of players inside Game N°{self.id} exceeded")

    def ___handle_client(self, client: Client):
        # handle incoming messages for each client
        try:
            while not self.game_close_event.is_set():
                data = client.getSocket().recv(2048)
                if not data:
                    return
                else:
                    message = json.loads(data.decode())
                    message_type = message["type"]
                    if message_type == "attack":
                        self.logger.info(
                            f"Received attack coordinates from player {client.getAddress()}")
                        self.__handle_receive_attack(client, message)
                    elif message_type == "attack_status":
                        self.logger.info(
                            f"Received attack status from player {client.getAddress()}")
                        self.__handle_receive_attack_status(client, message)
                    elif message_type == "exit":
                        self.__handle_close(client)
        except socket.error as e:
            # send a close signal to client's socket when ERROR
            self.logger.warning(f"Error handling client: {e}")
            # close connection with client on ERROR
            with self.gameServer.lock:
                self.gameServer.getClients().remove(client)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Error: {e}")
        except KeyboardInterrupt:
            self.__handle_close(client)

    def __handle_receive_coordinates(self, client: Client, players_coordinates: list, starting_client_turn: int):
        try:
            client.getBlockingEvent().set()
            data = client.getSocket().recv(2048)
            print(data)
            message = json.loads(data.decode())
            if message["type"] == "coordinates":
                self.logger.info(
                    f"Received coordinates from player {client.getAddress()}")
                # place client's ships
                for ship in message["ships"]:
                    client.getField().place_ship(
                        ship=Ship(
                            ship["name"], ship["sign"], ship["height"], ship["width"]
                        ),
                        place_coordinates=(
                            ship["x_start"]+1, ship["y_start"]+1
                        ),
                        orientation=ship["orientation"]
                    )

                if self.gameServer.getClients().index(client) == starting_client_turn:
                    message["starting"] = 1
                else:
                    message["starting"] = 0
                players_coordinates.append(
                    {
                        "player_index": self.gameServer.getClients().index(client),
                        "player_coordinates": message
                    }
                )
            elif message["type"] == "exit":
                self.__handle_close(client)
            else:
                raise Exception(
                    f"Unexpected message received from player {client.getAddress()}")
        except json.JSONDecodeError:
            pass

    def __handle_receive_attack(self, client: Client, message):
        client_index = self.gameServer.getClients().index(client)
        opponent = self.gameServer.getClients()[1-client_index]
        opponent.getField().hit_ship(
            message["coordinate"]["x"], message["coordinate"]["y"]
        )
        opponent.getSocket().send(json.dumps(message).encode())

    def __handle_receive_attack_status(self, client: Client, message):
        client_index = self.gameServer.getClients().index(client)
        opponent = self.gameServer.getClients()[1-client_index]

        player_damaged_coordinates_count = client.getField().count_damaged_coordinates()
        opponent_damaged_coordinates_count = opponent.getField().count_damaged_coordinates()

        if player_damaged_coordinates_count >= MAX_DAMAGED_COORDINATES or opponent_damaged_coordinates_count >= MAX_DAMAGED_COORDINATES:
            player_is_win = int(player_damaged_coordinates_count <=
                                opponent_damaged_coordinates_count)
            opponent_is_win = int(
                opponent_damaged_coordinates_count <= player_damaged_coordinates_count)
            if player_is_win != opponent_is_win:
                client.getSocket().send(
                    json.dumps({
                        "type": "end_game",
                        "is_win": player_is_win,
                        "message": "You lost. Better luck next time :`(" if player_is_win == 0 else "Bravo. You win !!!",
                    }).encode()
                )
                opponent.getSocket().send(
                    json.dumps({
                        "type": "end_game",
                        "is_win": opponent_is_win,
                        "message": "You lost. Better luck next time :`(" if opponent_is_win == 0 else "Bravo. You win !!!",
                        "attack_status": message
                    }).encode()
                )
                self.logger.info(f"{client.getAddress()} VS {opponent.getAddress(
                )} --> {client.getAddress() if player_is_win else opponent.getAddress()} has won the battle")
                return

        opponent.getSocket().send(json.dumps(message).encode())
        client.getSocket().send(
            json.dumps(
                {
                    "type": "launch_hit"
                }
            ).encode()
        )

    def __handle_close(self, client: Client):
        client_index = self.gameServer.getClients().index(client)
        opponent = self.gameServer.getClients()[
            1 - client_index]
        opponent.getSocket().send(
            json.dumps(
                {
                    "type": "end_game",
                    "is_win": int(True),
                    "message": "Your opponent has quit the game. You win :)"
                }
            ).encode()
        )
        self.gameServer._disconnect_client(client)

    def __eq__(self, game):
        if isinstance(game, Game):
            return game.id == self.id
        return False


if __name__ == "__main__":
    close_event = threading.Event()

    server = Server(("127.0.0.1", 12345), close_event)
    start_thread = threading.Thread(target=server.start)
    try:
        start_thread.start()
        # waiting for the closing flag
        server.close_event.wait()
    except KeyboardInterrupt:
        close_event.set()
        logging.warning("Server has shut down.")
    finally:
        logging.info(f"Exiting...")
