from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox

from omok.ai import OmokAI
from omok.board import Board
from omok.constants import BLACK, BOARD_SIZE, WHITE, opponent, to_external, to_internal
from omok.rules import RuleEngine


CELL_SIZE = 30
MARGIN = 42
STONE_RADIUS = 12
CANVAS_SIZE = MARGIN * 2 + CELL_SIZE * (BOARD_SIZE - 1)


def parse_cells(text):
    if not text.strip():
        return []
    cells = []
    for part in text.split(","):
        row_col = part.strip().split()
        if len(row_col) != 2:
            raise ValueError("좌표는 '행 열' 형식이어야 합니다.")
        cells.append((int(row_col[0]), int(row_col[1])))
    return cells


class OmokGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Omok AI")

        self.board = None
        self.ai = None
        self.rules = RuleEngine()
        self.ai_color = BLACK
        self.human_color = WHITE
        self.selected = None
        self.human_turn = False
        self.game_over = False

        self.blocked_var = tk.StringVar(value="3 3, 10 12, 15 7")
        self.ai_color_var = tk.StringVar(value="black")
        self.status_var = tk.StringVar(value="금수 좌표와 AI 색상을 선택한 뒤 게임을 시작하세요.")
        self.selection_var = tk.StringVar(value="선택: 없음")

        self._build_layout()
        self._draw_board()

    def _build_layout(self):
        top = tk.Frame(self.root)
        top.pack(padx=10, pady=8, fill=tk.X)

        tk.Label(top, text="금수 좌표 3개").pack(side=tk.LEFT)
        tk.Entry(top, textvariable=self.blocked_var, width=28).pack(side=tk.LEFT, padx=6)

        tk.Label(top, text="AI 색상").pack(side=tk.LEFT, padx=(10, 2))
        tk.Radiobutton(top, text="흑", variable=self.ai_color_var, value="black").pack(side=tk.LEFT)
        tk.Radiobutton(top, text="백", variable=self.ai_color_var, value="white").pack(side=tk.LEFT)
        tk.Button(top, text="게임 시작", command=self.start_game).pack(side=tk.LEFT, padx=8)

        self.canvas = tk.Canvas(self.root, width=CANVAS_SIZE, height=CANVAS_SIZE, bg="#d9a441")
        self.canvas.pack(padx=10, pady=4)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        bottom = tk.Frame(self.root)
        bottom.pack(padx=10, pady=8, fill=tk.X)
        self.place_button = tk.Button(bottom, text="착수", command=self.place_selected, state=tk.DISABLED)
        self.place_button.pack(side=tk.LEFT)
        tk.Label(bottom, textvariable=self.selection_var).pack(side=tk.LEFT, padx=12)

        tk.Label(self.root, textvariable=self.status_var, anchor="w").pack(padx=10, pady=(0, 10), fill=tk.X)

    def start_game(self):
        try:
            blocked = self._read_blocked_cells()
        except ValueError as exc:
            messagebox.showerror("금수 좌표 오류", str(exc))
            return

        self.ai_color = BLACK if self.ai_color_var.get() == "black" else WHITE
        self.human_color = opponent(self.ai_color)
        self.board = Board(blocked_cells=blocked)
        self.ai = OmokAI(color=self.ai_color, blocked_cells=blocked, time_limit=3.0)
        self.selected = None
        self.game_over = False
        self.human_turn = self.human_color == BLACK
        self._update_place_button()
        self._draw_board()

        if self.ai_color == BLACK:
            self.status_var.set("AI 차례입니다. 계산 중...")
            self.root.after(100, self.run_ai_turn)
        else:
            self.status_var.set("당신 차례입니다. 둘 칸을 클릭으로 선택한 뒤 착수 버튼을 누르세요.")

    def _read_blocked_cells(self):
        cells = parse_cells(self.blocked_var.get())
        if len(cells) != 3:
            raise ValueError("금수 좌표는 정확히 3개 입력해야 합니다.")
        if len(set(cells)) != 3:
            raise ValueError("금수 좌표가 중복되었습니다.")
        for row, col in cells:
            if not (1 <= row <= BOARD_SIZE and 1 <= col <= BOARD_SIZE):
                raise ValueError("좌표는 1~19 범위여야 합니다.")
        return cells

    def on_canvas_click(self, event):
        if not self.board or self.game_over or not self.human_turn:
            return
        cell = self._event_to_cell(event)
        if cell is None:
            return
        r, c = cell
        if not self.board.is_empty(r, c):
            self.status_var.set("빈 칸만 선택할 수 있습니다.")
            return
        self.selected = (r, c)
        row, col = to_external(self.selected)
        self.selection_var.set(f"선택: ({row}, {col})")
        self.status_var.set("선택한 칸에 두려면 착수 버튼을 누르세요.")
        self._update_place_button()
        self._draw_board()

    def place_selected(self):
        if not self.selected or not self.board or not self.ai or self.game_over:
            return
        r, c = self.selected
        if not self.rules.is_legal_move(self.board, r, c, self.human_color):
            self.status_var.set("그 위치에는 둘 수 없습니다. 다른 칸을 선택하세요.")
            return

        self.board.place(r, c, self.human_color)
        row, col = to_external((r, c))
        self.ai.notify_opponent_move(row, col)
        self.selected = None
        self.selection_var.set("선택: 없음")
        self._draw_board()

        if self._finish_if_needed(r, c, self.human_color, "당신이 이겼습니다."):
            return

        self.human_turn = False
        self._update_place_button()
        self.status_var.set("AI 차례입니다. 계산 중...")
        self.root.after(100, self.run_ai_turn)

    def run_ai_turn(self):
        if not self.board or not self.ai or self.game_over:
            return

        self.root.update_idletasks()
        started_at = time.time()
        row, col = self.ai.choose_move()
        elapsed = time.time() - started_at
        r, c = to_internal((row, col))
        self.board.place(r, c, self.ai_color)
        self._draw_board()

        if self._finish_if_needed(r, c, self.ai_color, f"AI가 이겼습니다. 계산 시간: {elapsed:.2f}초"):
            return

        self.human_turn = True
        self.status_var.set(
            f"AI 착수: ({row}, {col}), 계산 시간: {elapsed:.2f}초. 이제 당신 차례입니다."
        )
        self._update_place_button()

    def _finish_if_needed(self, r, c, color, message):
        if self.rules.check_win(self.board, r, c, color):
            self.game_over = True
            self.human_turn = False
            self.status_var.set(message)
            self._update_place_button()
            return True
        if not any(self.board.legal_empty_cells()):
            self.game_over = True
            self.human_turn = False
            self.status_var.set("무승부입니다.")
            self._update_place_button()
            return True
        return False

    def _draw_board(self):
        self.canvas.delete("all")
        for i in range(BOARD_SIZE):
            x = MARGIN + i * CELL_SIZE
            y = MARGIN + i * CELL_SIZE
            self.canvas.create_line(MARGIN, y, CANVAS_SIZE - MARGIN, y, fill="#24160b")
            self.canvas.create_line(x, MARGIN, x, CANVAS_SIZE - MARGIN, fill="#24160b")
            self.canvas.create_text(MARGIN - 22, y, text=str(BOARD_SIZE - i), fill="#24160b")
            self.canvas.create_text(x, CANVAS_SIZE - MARGIN + 22, text=str(i + 1), fill="#24160b")

        for r, c in ((3, 3), (3, 9), (3, 15), (9, 3), (9, 9), (9, 15), (15, 3), (15, 9), (15, 15)):
            x, y = self._cell_center(r, c)
            self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#24160b", outline="")

        if not self.board:
            return

        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                x, y = self._cell_center(r, c)
                if self.board.is_blocked(r, c):
                    self.canvas.create_text(x, y, text="✕", fill="#b00020", font=("Arial", 17, "bold"))
                elif self.board.get(r, c) == BLACK:
                    self.canvas.create_oval(
                        x - STONE_RADIUS,
                        y - STONE_RADIUS,
                        x + STONE_RADIUS,
                        y + STONE_RADIUS,
                        fill="#111111",
                        outline="#000000",
                    )
                elif self.board.get(r, c) == WHITE:
                    self.canvas.create_oval(
                        x - STONE_RADIUS,
                        y - STONE_RADIUS,
                        x + STONE_RADIUS,
                        y + STONE_RADIUS,
                        fill="#f8f8f8",
                        outline="#222222",
                        width=2,
                    )

        if self.selected:
            x, y = self._cell_center(*self.selected)
            self.canvas.create_rectangle(x - 15, y - 15, x + 15, y + 15, outline="#0066ff", width=3)

    def _event_to_cell(self, event):
        c = round((event.x - MARGIN) / CELL_SIZE)
        r = round((event.y - MARGIN) / CELL_SIZE)
        if not (0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE):
            return None
        x, y = self._cell_center(r, c)
        if abs(event.x - x) > CELL_SIZE // 2 or abs(event.y - y) > CELL_SIZE // 2:
            return None
        return r, c

    def _cell_center(self, r, c):
        return MARGIN + c * CELL_SIZE, MARGIN + r * CELL_SIZE

    def _update_place_button(self):
        state = tk.NORMAL if self.human_turn and self.selected and not self.game_over else tk.DISABLED
        self.place_button.configure(state=state)


def main():
    root = tk.Tk()
    OmokGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
