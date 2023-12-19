import json
import logging
import select
import socket
import sys
import threading
import time
from typing import List, override

logging.basicConfig(level=logging.INFO,
                    format='%(name)s: %(message)s',
                    )

DEFAULT_SIGN = '.'


class CoordinateTakenException(Exception):
    pass


class InvalidShipSign(Exception):
    pass


class InconsistentCoordinatesException(Exception):
    pass


class Coordinate:
    def __init__(self, x: int, y: int):
        self.__x: int = x
        self.__y: int = y
        self.__damaged: bool = False

    def getX(self):
        return self.__x

    def getY(self):
        return self.__y

    def is_damaged(self):
        return self.__damaged

    def setDamaged(self):
        self.__damaged = True


class Ship:
    def __init__(self, name: str, sign: str, height: int, width: int):
        if len(sign) == 1 and sign != DEFAULT_SIGN:
            self.__name = name
            self.__height = height
            self.__width = width
            self.__sign: str = sign
        else:
            InvalidShipSign(f"Invalid ship sign ({sign})")

    def getName(self):
        return self.__name

    def getHeight(self):
        return self.__height

    def setHeight(self, height: int):
        self.__height = height

    def setWidth(self, width: int):
        self.__width = width

    def getWidth(self):
        return self.__width

    def getSign(self):
        return self.__sign


class Field:
    def __init__(self, height: int, width: int):
        self.__height: int = height
        self.__width: int = width
        self.__ships: List[dict[Ship, List[Coordinate]]] = []
        self.__grid: List[List[(Coordinate, str)]] = [
            [(Coordinate(x, y), DEFAULT_SIGN) for x in range(self.__width)] for y in range(self.__height)
        ]

    def getShips(self):
        return self.__ships

    def getHeight(self):
        return self.__height

    def getWidth(self):
        return self.__width

    def place_ship(self, ship: Ship, place_coordinates: tuple((int, int)), orientation: ['v', 'h']):
        # Validate coordinates
        if not (1 <= place_coordinates[0] < self.__width) or not (1 <= place_coordinates[1] < self.__height):
            raise InconsistentCoordinatesException(
                f"Coordinate out of bounds: ({place_coordinates[0]}, {place_coordinates[1]})")
        place_coordinates = (
            place_coordinates[0]-1, place_coordinates[1]-1
        )

        ship_coordinates = []
        if orientation == 'v':
            ship_height = ship.getHeight()
            ship_width = ship.getWidth()
            ship.setHeight(ship_width)
            ship.setWidth(ship_height)

        reserved_coordinates: List[Coordinate] = [
            coordinate
            for ship
            in self.__ships
            for coordinate
            in ship["coordinates"]

        ]
        counter = 0
        if place_coordinates[1] + ship.getWidth() <= self.__width and place_coordinates[0] + ship.getHeight() <= self.__height:
            for y in range(ship.getHeight()):
                for x in range(ship.getWidth()):
                    for reserved_coordinate in reserved_coordinates:
                        if y + place_coordinates[0] == reserved_coordinate.getX() and x + place_coordinates[1] == reserved_coordinate.getY():
                            raise CoordinateTakenException(
                                f"Coordinate ({y + place_coordinates[0]+1}, {x + place_coordinates[1]+1}) is already taken")

                    new_coordinate = Coordinate(
                        y + place_coordinates[0], x + place_coordinates[1]
                    )
                    counter += 1
                    self.__grid[x + place_coordinates[1]][y + place_coordinates[0]] = (
                        new_coordinate, ship.getSign()
                    )
                    ship_coordinates.append(new_coordinate)
        else:
           # Ship overflows the grid
            raise InconsistentCoordinatesException(
                f"Ship placement out of range: ({place_coordinates[0]}..{place_coordinates[0] + ship.getHeight()}, {place_coordinates[1]}..{place_coordinates[1] + ship.getWidth()})")
        # ship is clear to land
        self.__ships.append({
            "ship": ship,
            "coordinates": ship_coordinates
        })

    def hit_ship(self, hit_x: int, hit_y: int) -> bool:
        hit_counter = 0
        hit_x -= 1
        hit_y -= 1
        for ship in self.__ships:
            for index, coordinate in enumerate(ship["coordinates"]):
                x, y = coordinate.getX(), coordinate.getY()
                if (x, y) in [(hit_x - 1, hit_y + 1), (hit_x - 1, hit_y - 1), (hit_x + 1, hit_y - 1), (hit_x + 1, hit_y + 1), (hit_x, hit_y)]:
                    coordinate.setDamaged()
                    hit_counter += 1

        return hit_counter > 0

    @staticmethod
    def display_fields(player_field, opponent_field, show_opponent: bool = False):
        lines_counter = 0
        blue = "\033[94m"
        pink = "\033[95m"
        gray = "\033[90m"
        red = "\033[91m"
        green = "\033[92m"
        end_color = "\033[0m"

        print("\n\n----------------------------------------------------------------------------------------------------------------------------------------------------------\n\n")
        lines_counter += 1

        # Print player's x-axis coordinates
        print("\t    " + '    '.join(str(f"{pink}{i+1}{end_color}")
              for i in range(player_field.__width)), end="\t\t")

        # Print opponent's x-axis coordinates
        print("\t    " + '    '.join(str(f"{pink}{i+1}{end_color}")
              for i in range(opponent_field.__width)))

        lines_counter += 1

        # Print player's top border
        print(
            "\t  " + "".join(["-----" for _ in range(player_field.__width)]), end="\t\t")

        # Print opponent's top border
        print(
            "\t  " + "".join(["-----" for _ in range(opponent_field.__width)]))

        lines_counter += 1

        for y, (player_row, opponent_row) in enumerate(zip(player_field.__grid, opponent_field.__grid)):
            # Print player's y-axis coordinate with color
            print(f"{blue}{y+1}{end_color}\t |", end="")

            # Print player's grid
            for cell in player_row:
                sign = cell[1]
                if sign == DEFAULT_SIGN:
                    print(f"  {gray}{sign}{end_color}  ", end="")
                else:
                    if cell[0].is_damaged():
                        print(f"  {red}{sign}{end_color}  ", end="")
                    else:
                        print(f"  {green}{sign}{end_color}  ", end="")

            print("|", end="\t\t")

            # Print opponent's y-axis coordinate with color
            print(f"|{blue}{y+1}{end_color}\t |", end="")

            # Print opponent's grid
            for cell in opponent_row:
                sign = cell[1]
                if not show_opponent:
                    if cell[0].is_damaged():
                        print(f"  {red}{"¤"}{end_color}  ", end="")
                    else:
                        print(f"  {gray}{DEFAULT_SIGN}{end_color}  ", end="")
                else:
                    if sign == DEFAULT_SIGN:
                        print(f"  {gray}{sign}{end_color}  ", end="")
                    else:
                        if cell[0].is_damaged():
                            print(f"  {red}{sign}{end_color}  ", end="")
                        else:
                            print(f"  {green}{sign}{end_color}  ", end="")

            print("|\n")

        # Print the bottom borders for player and opponent
        print(
            "\t  " + "".join(["-----" for _ in range(player_field.__width)]), end="\t\t")
        print(
            "\t  " + "".join(["-----" for _ in range(opponent_field.__width)]), end="\n")

        print("\t\t\t\tYou", end="\t\t\t\t")
        print("\t\t\t\t\tOpponent")
        print("\n\n----------------------------------------------------------------------------------------------------------------------------------------------------------\n\n")

    def count_damaged_coordinates(self) -> int:
        counter = 0
        for ship in self.__ships:
            for coordinate in ship["coordinates"]:
                if coordinate.is_damaged():
                    counter += 1
        return counter

    def detect_ship_orientation(self, ship: Ship):
        x_axis = []
        y_axis = []
        for coordinate in ship["coordinates"]:
            x_axis.append(coordinate.getX())
            y_axis.append(coordinate.getY())

        min_x, max_x = min(x_axis), max(x_axis)
        min_y, max_y = min(y_axis), max(y_axis)
        if max_x - min_x > max_y - min_y:
            return 'h'
        else:
            return 'v'


class Player:
    def __init__(self, field: Field):
        self.__field = field

    def getField(self):
        return self.__field

    def prompt_ship_placement(self, ship: Ship):
        while True:
            try:
                x = int(
                    input(
                        f"Enter the starting X-coordinate (1-{self.__field.getWidth()}): ")
                )
                y = int(
                    input(
                        f"Enter the starting Y-coordinate (1-{self.__field.getHeight()}): ")
                )
                orientation = input("Enter orientation (h/v): ").lower()

                if 1 <= x < self.__field.getWidth() and 1 <= y < self.__field.getHeight():
                    self.__field.place_ship(ship, (x, y), orientation)
                    break
                else:
                    print("Invalid coordinates. Please try again.")
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except Exception as e:
                print(f"Error: {e}. Please enter valid input.")

    def prompt_hit_coordinate(self) -> tuple[int, int]:
        while True:
            try:
                x = int(
                    input(
                        f"Enter the hit's X-coordinate (1-{
                            self.getField().getWidth()}): "
                    )
                )
                y = int(
                    input(
                        f"Enter the hit's Y-coordinate (1-{self.getField().getHeight()}): ")
                )
                if 1 <= x < self.getField().getWidth() and 1 <= y < self.getField().getHeight():
                    return x, y
                else:
                    self.logger.info(
                        "Invalid coordinates. Please try again."
                    )
            except Exception as e:
                print(f"Error: {e}. Please enter valid input.")


class Client:
    def __init__(self, host, port, close_event, player: Player, opponent: Player):
        self.host = host
        self.port = port
        self.__player = player
        self.__opponent = opponent
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.close_event = close_event
        self.send_signal = threading.Event()
        self.logger = logging.getLogger("Socket")

    def getPlayer(self):
        return self.__player

    def getOpponent(self):
        return self.__opponent

    @override
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
                        decoded_message = json.loads(message.decode())
                        if (decoded_message["type"] == "close"):
                            self._close_socket()
                        elif decoded_message["type"] == "wait_for_opponent":
                            self.logger.info(decoded_message["message"])
                        elif decoded_message["type"] == "start_game":
                            client.prompt_and_send_player_ship_informationss(
                                default_ships
                            )
                        elif decoded_message["type"] == "coordinates":
                            self.__handle_receiving_ships_coordinates(
                                self.__opponent, decoded_message
                            )
                            if decoded_message["starting"] == 1:
                                self.logger.info(
                                    "The first hit is yours...")
                                x, y = self.__player.prompt_hit_coordinate()
                                self.server_socket.send(
                                    json.dumps(
                                        {
                                            "type": "attack",
                                            "coordinate": {
                                                "x": x,
                                                "y": y
                                            }
                                        }
                                    ).encode()
                                )
                            else:
                                self.logger.info(
                                    "The first hit is for your opponent.., waiting for him to launch a missile")
                        elif decoded_message["type"] == "attack":
                            self.__handle_receive_attack(
                                self.__player,
                                (
                                    decoded_message["coordinate"]["x"],
                                    decoded_message["coordinate"]["y"]
                                )
                            )

                        elif decoded_message["type"] == "attack_status":
                            self.__handle_receive_attack_status(
                                self.__opponent,
                                (
                                    decoded_message["coordinate"]["x"],
                                    decoded_message["coordinate"]["y"]
                                )
                            )
                        elif decoded_message["type"] == "launch_hit":
                            self.__handle_lauch_hit()
                        elif decoded_message["type"] == "end_game":
                            self.__handle_end_game(decoded_message)
                        else:
                            self.logger.info(decoded_message)
            except KeyboardInterrupt:
                self._close_connection_from_client("exit")
                break
            except socket.error as e:
                self.logger.error(f"Error connecting to the server: {e}")
                self._close_socket()
                break

    def __handle_receiving_ships_coordinates(self, client: Player, message):
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
        self.logger.info(
            "Opponenet's ships have been placed. The war has began")

    def __handle_receive_attack(self, client: Player, coordinate: tuple[int, int]):
        x, y = coordinate
        status: bool = client.getField().hit_ship(x, y)
        self.server_socket.send(
            json.dumps(
                {
                    "type": "attack_status",
                    "status": int(status),
                    "coordinate": {
                        "x": x,
                        "y": y
                    }
                }
            ).encode()
        )
        Field.display_fields(
            self.__player.getField(), self.__opponent.getField()
        )

    def __handle_receive_attack_status(self, opponent: Player, coordinate: tuple[int, int]):
        hit_x, hit_y = coordinate
        status: bool = opponent.getField().hit_ship(hit_x, hit_y)
        Field.display_fields(
            self.__player.getField(), opponent.getField()
        )
        if status == 1:
            self.logger.info("Target was hit!!")
        else:
            self.logger.info("Target was not hit :(")
        self.logger.info(
            "Opponenet's turn, waiting for him to launch a missile"
        )

    def __handle_lauch_hit(self):
        x, y = self.__player.prompt_hit_coordinate()
        self.server_socket.send(
            json.dumps(
                {
                    "type": "attack",
                    "coordinate": {
                        "x": x,
                        "y": y
                    }
                }
            ).encode()
        )

    def __handle_end_game(self, message):
        red = "\033[91m"
        green = "\033[92m"
        end_color = "\033[0m"
        if "attack_status" in message and message["attack_status"] is not None:
            x, y = (
                message["attack_status"]["coordinate"]["x"],
                message["attack_status"]["coordinate"]["y"]
            )
            self.__opponent.getField().hit_ship(x, y)
        Field.display_fields(
            self.__player.getField(), self.__opponent.getField(), show_opponent=True
        )
        if message["is_win"] == 1:
            self.logger.info(f"{green}{message["message"]}{end_color}")
        else:
            self.logger.info(
                f"{red}{message["message"]}{end_color}")
        self._close_connection_from_client("close")

    def prompt_and_send_player_ship_informationss(self, default_ships: List[Ship]):
        try:
            Field.display_fields(
                self.__player.getField(), Field(10, 10))
            for ship in default_ships:
                self.__player.prompt_ship_placement(ship)
                Field.display_fields(
                    self.__player.getField(), Field(10, 10))

            player_ships_informations = []
            for ship in self.__player.getField().getShips():
                orientation = self.__player.getField().detect_ship_orientation(ship)
                if orientation == "v":
                    player_ships_informations.append(
                        {
                            "name": ship["ship"].getName(),
                            "sign": ship["ship"].getSign(),
                            "width": ship["ship"].getHeight(),
                            "height": ship["ship"].getWidth(),
                            "x_start": min([coordinate.getX() for coordinate in ship["coordinates"]]),
                            "y_start": min([coordinate.getY() for coordinate in ship["coordinates"]]),
                            "orientation": orientation
                        }
                    )
                else:
                    player_ships_informations.append(
                        {
                            "name": ship["ship"].getName(),
                            "sign": ship["ship"].getSign(),
                            "height": ship["ship"].getHeight(),
                            "width": ship["ship"].getWidth(),
                            "x_start": min([coordinate.getX() for coordinate in ship["coordinates"]]),
                            "y_start": min([coordinate.getY() for coordinate in ship["coordinates"]]),
                            "orientation": orientation
                        }
                    )
            self.server_socket.send(json.dumps(
                {
                    "type": "coordinates",
                    "ships": player_ships_informations
                }
            ).encode()
            )
            self.logger.info(
                "Waiting for the opponent to place his ships..")
        except KeyboardInterrupt:
            self._close_connection_from_client("exit")
            return

    def _close_connection_from_client(self, message):
        try:
            self.logger.info("Closing connection with the server..")
            self.server_socket.send(json.dumps({"type": message}).encode())
        except socket.error as e:
            self.logger.error(f"Error connecting to the server{e}")
            pass
        finally:
            self._close_socket()

    def _close_socket(self):
        try:
            self.server_socket.shutdown(socket.SHUT_RDWR)
            self.server_socket.close()
            self.close_event.set()
            self.logger.info("Connection closed")
        except socket.error:
            pass


default_ships: List[Ship] = [
    Ship("BB-67", "X", 6, 2),
    Ship("FTR-88", "#", 4, 2),
    Ship("MO201", "o", 3, 2),
]

if __name__ == "__main__":
    close_event = threading.Event()
    client = Client(
        "127.0.0.1", 12345,
        close_event,
        Player(Field(10, 10)), Player(Field(10, 10))
    )
    try:
        client.connect()
        receive_thread = threading.Thread(
            target=client.receive_messages,
            daemon=True
        )
        receive_thread.start()

        close_event.wait()
    except KeyboardInterrupt:
        client._close_connection_from_client("exit")
        exit(0)
