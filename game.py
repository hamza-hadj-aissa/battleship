from typing import List


DEFAULT_SIGN = '.'


class CoordinateTakenException(Exception):
    pass


class InvalidShipSign(Exception):
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
    def __init__(self, cordinates: List[Coordinate], sign: str):
        if len(sign) == 1 and sign != DEFAULT_SIGN:
            self.__cordinates: List[Coordinate] = cordinates
            self.__sign: str = sign
        else:
            InvalidShipSign(f"Invalid ship sign ({sign})")

    def getCoordinates(self):
        return self.__cordinates

    def getSign(self):
        return self.__sign


class Field:
    def __init__(self, height: int, width: int):
        self.__height: int = height
        self.__width: int = width
        self.__ships: List[Ship] = []
        self.__grid: List[List[(Coordinate, str)]] = [
            [(Coordinate(x, y), DEFAULT_SIGN) for x in range(self.__width)] for y in range(self.__height)
        ]

    def getHeight(self):
        return self.__height

    def getWidth(self):
        return self.__width

    def place_ship(self, ship: Ship):
        reserved_coordinates = [(coordinate.getX(), coordinate.getY(
        )) for ship in self.__ships for coordinate in ship.getCoordinates()]

        for coordinate in [coordinate for coordinate in ship.getCoordinates()]:
            x, y = coordinate.getX(), coordinate.getY()
            for reserved_x, reserved_y in reserved_coordinates:
                if x == reserved_x and y == reserved_y:
                    raise CoordinateTakenException(
                        f"Coordinates ({x+1}, {y+1}) are already taken"
                    )

        # ship is clear to land
        self.__ships.append(ship)

    def hit_ship(self, x: int, y: int) -> bool:
        hit_coordinate: Coordinate = Coordinate(x-1, y-1)
        for ship in self.__ships:
            for coordinate in [coordinate for coordinate in ship.getCoordinates()]:
                x, y = coordinate.getX(), coordinate.getY()
                if hit_coordinate.getX() == x and hit_coordinate.getY() == y:
                    coordinate.setDamaged()
                    return True
        return False

    def display_field(self):
        for ship in self.__ships:
            for coordinate in [coordinate for coordinate in ship.getCoordinates()]:
                x, y = coordinate.getX(), coordinate.getY()
                self.__grid[y][x] = (coordinate, ship.getSign())

        blue = "\033[94m"
        pink = "\033[95m"
        gray = "\033[90m"
        red = "\033[91m"
        green = "\033[92m"
        end_color = "\033[0m"

        # Print the x-axis coordinates
        print("\t    " + '    '.join(str(f"{pink}{i+1}{end_color}")
                                     for i in range(self.__width)))

        # Print the top border
        print("\t  " + "".join(["-----" for _ in range(self.__width)]))
        for y, row in enumerate(self.__grid):
            # Print the y-axis coordinate with color
            print(f"{blue}{y+1}{end_color}\t |", end="")
            for cell in row:
                sign = cell[1]
                if sign == DEFAULT_SIGN:
                    print(f"  {gray}{sign}{end_color}  ", end="")
                else:
                    if cell[0].is_damaged():
                        print(f"  {red}{sign}{end_color}  ", end="")
                    else:
                        print(f"  {green}{sign}{end_color}  ", end="")
            print("|\n")

        # Print the bottom border
        print("\t  " + "".join(["-----" for _ in range(self.__width)]))


if __name__ == "__main__":
    field = Field(10, 10)
    ship1 = Ship(
        [Coordinate(i, 2) for i in range(2, 7)],
        "X"
    )

    ship2 = Ship(
        [Coordinate(i, 5) for i in range(5, 8)],
        "#"
    )
    ship3 = Ship(
        [Coordinate(2, i) for i in range(5, 9)],
        "O"
    )

    try:
        field.place_ship(ship1)
        field.place_ship(ship2)
        field.place_ship(ship3)
        field.hit_ship(6, 6)
        field.hit_ship(3, 3)
        field.hit_ship(4, 3)
        field.hit_ship(5, 3)
        field.hit_ship(6, 3)

    except CoordinateTakenException as e:
        print({e})
    finally:
        field.display_field()
