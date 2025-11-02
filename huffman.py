from sys import byteorder


class Node:
    def __init__(self, left, right, character, frequency):
        self.left = left  # node to the left of the node
        self.right = right  # node to the right of the node
        self.character = character  # what character(s) this node represents
        self.frequency = frequency  # how many times this character appears
        self.directionFromParent = ''  # 1 = right, 0 = left


def calculate_direction(node, direction,
                        direction_dict=None):  # recursive function that calculates direction for every node
    if direction_dict is None:
        direction_dict = {}
    total_direction = direction + node.directionFromParent
    if node.left is not None:
        direction_dict = calculate_direction(node.left, total_direction, direction_dict)
    if node.right is not None:
        direction_dict = calculate_direction(node.right, total_direction, direction_dict)
    if node.left is None and node.right is None:
        direction_dict[node.character] = total_direction
    return direction_dict


def merge_sort(lst):
    if len(lst) == 1:
        return lst
    centre = len(lst) // 2

    left = merge_sort(lst[:centre])
    right = merge_sort(lst[centre:])
    new = []
    while len(left) > 0 and len(right) > 0:
        if left[0].frequency < right[0].frequency:
            new.append(left[0])
            left.pop(0)
        else:
            new.append(right[0])
            right.pop(0)
    new += left + right
    return new


def calculate_frequency(data):
    character_count = {i: 0 for i in range(256)}
    for i in data:  # making a dictionary of every character and how many times they appear
        character_count[i] += 1

    return character_count


def form_tree(unparented_nodes):
    """Takes a list of unparented nodes and creates parent nodes for the two most frequent ones, and repeats until only one
     node remains which is the root of a tree"""
    while len(unparented_nodes) != 1:
        unparented_nodes = merge_sort(unparented_nodes)
        left = unparented_nodes[0]
        right = unparented_nodes[1]
        left.directionFromParent = "0"
        right.directionFromParent = "1"
        parent_node = Node(left, right, left.character + right.character, left.frequency + right.frequency)
        unparented_nodes.remove(left)
        unparented_nodes.remove(right)
        unparented_nodes.append(parent_node)
    return unparented_nodes


def chunks(data, n):  # Yield successive n-sized chunks from data.
    for i in range(0, len(data), n):
        yield data[i:i + n]


def encode(data, character_direction, block_size):  # replaces each character in data with its direction
    output = []

    output.append(bin(block_size)[2:].zfill(16))       # appends block-size to output in 16 bits
    data = chunks(data, block_size)
    for block in data:
        size = 0
        for char in block:
            size += len(character_direction[char])
        if size/8 >= len(block):  # if the compressed data would be larger than the pure block, don't compress
            output.append('1')
            for char in block:
                output.append(bin(char)[2:].zfill(8))
        else:
            output.append('0')
            for char in block:

                output.append(character_direction[char])

    return ''.join(output)


def compress(data, block_size=1000):
    character_count = calculate_frequency(data)

    unparented_nodes = [Node(None, None, character, character_count[character]) for character in character_count]

    unparented_nodes = form_tree(unparented_nodes)
    character_direction = calculate_direction(unparented_nodes[0], '')
    encoded_data = encode(data, character_direction, block_size)

    for k in character_direction.keys():           # sets all unused characters to 0, instead of really long bitstrings
        if character_count[k] == 0:
            character_direction[k] = '0'

    # creates an ordered list of the values, as the keys are no longer needed if it is ordered
    character_direction = sorted(character_direction.items(), key=lambda kv: kv[0])


    codebook = gamma([int('1' + v, 2) for k,v in character_direction])   # encodes codebook with gamma coding
    finaldata = '1' + codebook + encoded_data       # inserts 1 at beginning so that leading 0s are not stripped
    finaldata = int(finaldata, 2).to_bytes((len(finaldata) + 7) // 8, byteorder=byteorder)  # converts bits to bytes
    return finaldata


def decompress(compressed_data):
    if len(compressed_data) == 0:
        return 0
    compressed_data = bin(int.from_bytes(compressed_data, byteorder=byteorder))[2:]
    compressed_data = compressed_data[1:]     # removes 1 that was inserted so that leading zeros wouldn't be stripped

    character_direction, data = gammadecode(compressed_data)

    block_size = int(data[0:16], 2)  # finds block size
    data = data[16:]

    root_node = Node(None, None, None, None)
    for code in character_direction.items():    # rebuilding huffman tree from codebook
        if code[1] == '0':     # character is never used, no need to be inserted into tree
            continue
        current_node = root_node
        for i in code[1]:
            if i == '0':     # it is left of its parent
                if current_node.left is not None:   # if child on the left already exists
                    current_node = current_node.left
                else:
                    current_node.left = Node(None, None, None, None)
                    current_node = current_node.left
                    current_node.directionFromParent = '0'
            elif i == '1':        # it is right of its parent
                if current_node.right is not None:   # if child on the right already exists
                    current_node = current_node.right
                else:
                    current_node.right = Node(None, None, None, None)
                    current_node = current_node.right
                    current_node.directionFromParent = '1'
        current_node.character = code[0]
    decoded_output = []
    current_node = root_node
    i = 0

    while i < len(data):
        if data[i] == '1':           # pure block
            i += 1
            block = data[i:i + (block_size * 8)]

            block = chunks(block, 8)
            for char in block:
                decoded_output.append(int(char, 2))

            i += (block_size * 8)

        elif data[i] == '0':            # encoded block
            i += 1

            char_count = 0
            while char_count < block_size and i < len(data):
                try:
                    if data[i] == '1':
                        current_node = current_node.right
                        i += 1
                    elif data[i] == '0':
                        current_node = current_node.left
                        i += 1
                    if current_node.character is not None:
                        decoded_output.append(current_node.character)

                        current_node = root_node
                        char_count += 1
                except AttributeError:
                    return 0

    return bytes(decoded_output)


def gamma(data):
    """gamma coding allows variable length encoding, so numbers can be stored without a predefined number of bits for
     each value"""
    output = []
    for n in data:
        nbin = bin(n)[2:]
        length = len(nbin)
        output.append(((length-1) * '0') + nbin)
    return ''.join(output)


def gammadecode(data):
    output = []
    n = 0
    i = 0
    while len(output) < 256:
        if data[i] == '0':
            n += 1
            i += 1
        else:
            num = 2**n
            num += int(data[i+1:i+n+1], 2)
            output.append(num)
            i += n + 1
            n = 0
    output = [bin(i)[3:] for i in output]
    output = {i: output[i] for i in range(256)}
    return output, data[i:]
