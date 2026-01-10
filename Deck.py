import random

# Suits encoded as:
# 0 = Hearts, 1 = Diamonds, 2 = Clubs, 3 = Spades

class Deck:
    def __init__(self):
        # Card = (rank, suit)
        self.cards = [(rank, suit) for rank in range(1, 14) for suit in range(4)]
        self.shuffle()

    def shuffle(self):
        random.shuffle(self.cards)

    def draw(self):
        return self.cards.pop()


def hand_value(hand: list) -> int:
    """
    Calculates total value of a hand
    """
    total = 0
    for rank, _ in hand:
        if rank == 1:
            total += 11
        elif rank >= 10:
            total += 10
        else:
            total += rank

    return total

def format_card(rank, suit_idx):
    suits = ['♥', '♦', '♣', '♠']
    rank_str = {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}.get(rank, str(rank))
    return f"[{rank_str}{suits[suit_idx]}]"