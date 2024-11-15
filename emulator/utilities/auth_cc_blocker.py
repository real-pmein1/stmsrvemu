def is_card_blocked(card_number, block_rules):
    # Check for direct card number block
    if card_number in block_rules.get('card_numbers', []):
        return True

    # Check for group blocks
    for group in block_rules.get('groups', []):
        if card_number.startswith(group):
            return True

    # Check for card type blocks
    card_type = get_card_type(card_number)
    if card_type in block_rules.get('card_types', []):
        return True

    return False

def get_card_type(card_number):
    # Dummy implementation - should be replaced with actual logic
    if card_number.startswith('4'):
        return 'Visa'
    elif card_number.startswith('5'):
        return 'MasterCard'
    # Add other card types as needed
    return 'Unknown'

def load_block_rules(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        block_rules = {
            'card_numbers': [],
            'groups': [],
            'card_types': []
        }
        for line in lines:
            line = line.strip()
            if line.startswith('#'):  # Skip comments
                continue
            if line.startswith('CARD:'):
                block_rules['card_numbers'].append(line.split(':')[1])
            elif line.startswith('GROUP:'):
                block_rules['groups'].append(line.split(':')[1])
            elif line.startswith('TYPE:'):
                block_rules['card_types'].append(line.split(':')[1])
        return block_rules