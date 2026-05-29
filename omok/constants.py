BOARD_SIZE = 19

EMPTY = 0
BLACK = 1
WHITE = 2
BLOCKED = 3

DIRECTIONS = (
    (0, 1),
    (1, 0),
    (1, 1),
    (1, -1),
)

COLOR_NAMES = {
    EMPTY: ".",
    BLACK: "B",
    WHITE: "W",
    BLOCKED: "X",
}

FIVE_OR_MORE = 100_000_000
OPEN_FOUR = 10_000_000
CLOSED_FOUR = 2_000_000
FOUR_THREE = 12_000_000
LEGAL_DOUBLE_THREE_THREAT = 900_000
CONNECTED_OPEN_THREE = 350_000
OPEN_THREE = CONNECTED_OPEN_THREE
BROKEN_OPEN_THREE = 250_000
FUTURE_FOUR_THREE_SETUP = 400_000
CLOSED_THREE = 20_000
OPEN_TWO = 2_000
CLOSED_TWO = 200
ILLEGAL_MOVE = -1_000_000_000

INF = 10**15


def opponent(color):
    if color == BLACK:
        return WHITE
    if color == WHITE:
        return BLACK
    raise ValueError(f"Invalid color: {color}")


def to_internal(pos):
    row, col = pos
    return BOARD_SIZE - row, col - 1


def to_external(pos):
    row, col = pos
    return BOARD_SIZE - row, col + 1
