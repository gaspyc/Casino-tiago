from itertools import combinations
from collections import Counter

# Ranks mapping
RANK_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 11, 'Q': 12, 'K': 13, 'A': 14
}

# Evaluator Hand Ranks
HIGH_CARD = 0
PAIR = 1
TWO_PAIR = 2
THREE_OF_A_KIND = 3
STRAIGHT = 4
FLUSH = 5
FULL_HOUSE = 6
FOUR_OF_A_KIND = 7
STRAIGHT_FLUSH = 8

def parse_card(card_str: str):
    """
    Parses a card string like 'A♠' or '10♥' into a tuple (rank_value, suit)
    """
    if card_str == 'HIDDEN':
        return (0, '')
    
    # Manejar '10' que tiene 2 caracteres
    rank_str = card_str[:-1]
    suit = card_str[-1]
    return (RANK_VALUES.get(rank_str, 0), suit)

def evaluate_5_cards(cards):
    """
    Evaluates exactly 5 cards and returns a tuple (Hand Rank, [Tiebreaker Values])
    """
    # Sort cards by rank descending
    sorted_cards = sorted(cards, key=lambda x: x[0], reverse=True)
    ranks = [c[0] for c in sorted_cards]
    suits = [c[1] for c in sorted_cards]
    
    is_flush = len(set(suits)) == 1
    
    # Check straight
    is_straight = False
    if len(set(ranks)) == 5 and ranks[0] - ranks[4] == 4:
        is_straight = True
    # Special case: A, 5, 4, 3, 2 (wheel straight)
    elif ranks == [14, 5, 4, 3, 2]:
        is_straight = True
        ranks = [5, 4, 3, 2, 14] # Reorder so 5 is the highest card in the straight
    
    counts = Counter(ranks)
    count_values = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    
    # count_values = [(rank, count), ...]
    # Example for Full House (K, K, K, 2, 2) -> [(13, 3), (2, 2)]
    
    if is_straight and is_flush:
        return (STRAIGHT_FLUSH, ranks)
    
    if count_values[0][1] == 4:
        return (FOUR_OF_A_KIND, [count_values[0][0], count_values[1][0]])
        
    if count_values[0][1] == 3 and count_values[1][1] == 2:
        return (FULL_HOUSE, [count_values[0][0], count_values[1][0]])
        
    if is_flush:
        return (FLUSH, ranks)
        
    if is_straight:
        return (STRAIGHT, ranks)
        
    if count_values[0][1] == 3:
        return (THREE_OF_A_KIND, [count_values[0][0], count_values[1][0], count_values[2][0]])
        
    if count_values[0][1] == 2 and count_values[1][1] == 2:
        return (TWO_PAIR, [count_values[0][0], count_values[1][0], count_values[2][0]])
        
    if count_values[0][1] == 2:
        return (PAIR, [count_values[0][0], count_values[1][0], count_values[2][0], count_values[3][0]])
        
    return (HIGH_CARD, ranks)

def evaluate_hand(hole_cards: list, community_cards: list):
    """
    Evaluates the best 5-card combination out of 7 cards (2 hole + 5 community).
    Returns (Hand Rank, [Tiebreaker Values])
    """
    all_cards_str = hole_cards + community_cards
    if len(all_cards_str) < 5:
        return (HIGH_CARD, [])
        
    all_cards = [parse_card(c) for c in all_cards_str if c != 'HIDDEN']
    
    best_rank = -1
    best_tiebreaker = []
    
    # Test all 5-card combinations
    for combo in combinations(all_cards, 5):
        rank, tiebreaker = evaluate_5_cards(combo)
        if rank > best_rank:
            best_rank = rank
            best_tiebreaker = tiebreaker
        elif rank == best_rank:
            # Compare tiebreakers lexicographically
            if tiebreaker > best_tiebreaker:
                best_tiebreaker = tiebreaker
                
    return (best_rank, best_tiebreaker)

def format_hand_name(rank: int) -> str:
    names = {
        STRAIGHT_FLUSH: "Escalera de Color",
        FOUR_OF_A_KIND: "Poker",
        FULL_HOUSE: "Full House",
        FLUSH: "Color",
        STRAIGHT: "Escalera",
        THREE_OF_A_KIND: "Trío",
        TWO_PAIR: "Doble Par",
        PAIR: "Par",
        HIGH_CARD: "Carta Alta"
    }
    return names.get(rank, "Desconocido")
