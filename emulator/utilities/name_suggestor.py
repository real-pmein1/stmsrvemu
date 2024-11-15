import random
import struct

import globalvars
from config import read_config

config = read_config()


def load_modifiers_from_files():
    file_paths = {
        config['configsdir'] + '/' + "suggestion_prepend.txt": [],
        config['configsdir'] + '/' + "suggestion_append.txt": []
    }

    for file_path, modifiers_list in file_paths.items():
        try:
            with open(file_path, 'r') as file:
                # Extend the modifiers_list with lines that do not start with '#' and are not empty
                modifiers_list.extend(line.strip() for line in file if line.strip() and not line.startswith('#'))
        except IOError as e:
            print(f"Failed to read {file_path}: {e}")  # It's better to log or handle the error

    if config["use_builtin_suggested_name_modifiers"].lower() == "true":
        globalvars.prepended_modifiers += [
                "mc", "cool", "star", "pro", "king", "ninja", "ace", "neo", "tech",
                "nova", "sky", "galaxy", "phantom", "Mr_", "elite", "shadow", "cyber",
                "quantum", "ethereal", "mystic", "wizard", "echo", "terra", "aqua",
                "pyro", "frost", "thunder", "drift", "flux", "banned", "dumb",
                "generic_", "gooey", "stinky", "raunchy", "putrid", "brother_",
                "nasty", "ultra", "mega", "super", "hyper", "dark", "chaos", "lucky",
                "quick", "sneaky", "crazy", "furious", "silent", "rapid", "chronic",
                "stormy", "wild", "ancient", "legendary", "ghost", "frosty", "the_phallic_",
                "hard", "crunchy", "ugly", "crunchy", "re", "slow", "chronic_", "creamy",
                "dubious_", "hide_the_kids_", "geriatric", "sleezy_", "pedo", "easy_"
            ]
        globalvars.appended_modifiers += [
                "erific", "dream", "_the_womanizer", "transvestinator",
                "_the_unlikable", "_the_terrible", "orama", "ler", "ing",
                "son",  "_jr",  "iffer", "ny", "y", "ji", "man", "zilla",
                "inator", "osaures", "ton", "ious", "zen", "wick", "core",
                "leigh", "wood", "smith", "max", "dex", "ley", "nator",
                "able", "stein", "knight", "_the_cog", "s_boner", "_the_pipelayer",
                "erbator", "_the_diddler", "s_johnson", "_is_a_nazi", "8--D",
                "phile"
            ]

    globalvars.prepended_modifiers += list(file_paths.keys())[0]
    globalvars.appended_modifiers += list(file_paths.keys())[1]


def similar_username_generator(base_username, number_of_usernames, database):
    suggestions = set()

    # Convert append_modifiers to a list if it's a set
    append_modifiers = list(globalvars.appended_modifiers)
    prepend_modifiers = list(globalvars.prepended_modifiers)
    while len(suggestions) < number_of_usernames:
        # Random username generation logic
        rand_prependmodifier = random.choice(prepend_modifiers)
        rand_appendmodified = random.choice(append_modifiers)
        action = random.choice(['append', 'prepend', 'both', 'none'])

        if action == 'append':
            new_username = base_username + rand_appendmodified
        elif action == 'prepend':
            new_username = rand_prependmodifier + base_username
        elif action == 'both':
            new_username = rand_prependmodifier + base_username + rand_appendmodified
        else:
            new_username = base_username

        # Apply leet speak and number appending
        new_username = randomize_username(new_username)
        if new_username == base_username:
            new_username = randomize_username(random.choice(prepend_modifiers) + new_username)


        while (database.check_username_exists(new_username)):
            new_username = randomize_username(new_username) + rand_appendmodified

        suggestions.add(new_username)

    # Convert set to the required dictionary format
    suggestedname = {}
    for i, name in enumerate(suggestions):
        key = struct.pack('<I', i)
        suggestedname[key] = name.encode('utf-8') + b'\x00'

    return suggestedname


def randomize_username(username):
    new_username_chars = list(username)
    leet_speak = {'a':'4', 'e':'3', 'i':'1', 'o':'0', 't':'7'}
    # Leet speak replacement (up to 4 letters)
    if random.choice([True, False]):
        eligible_positions = [i for i, char in enumerate(new_username_chars) if char in leet_speak]
        leet_positions = random.sample(eligible_positions, min(2, len(eligible_positions)))
        i = 0
        for pos in leet_positions:
            if random.choice([True, False]):
                new_username_chars[pos] = leet_speak[new_username_chars[pos]]
            i += 1
            if i >= 2:
                break

    # Append a random number at the end
    if random.choice([True, False]):
        num = str(random.randint(0, 9999))
        new_username_chars.append(num)

    return ''.join(new_username_chars)