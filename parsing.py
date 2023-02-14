from trees import get_trees
from PFSTA import Node, PFSTA
from over_under import (assign_addresses, print_tree, get_right_sis, get_left_sis, get_address_list, 
                        get_node, star_nodes, tree_prob_via_over_no_order, tree_prob_via_under_no_order)
import signal, string


VERB_LABELS = ['VB', 'VBD', 'VBG', 'VBN', 'VBP']

p = PFSTA(  [0, 1, 2, 3, 4],
                {1: 1.0},
                {(0, 'WH', ()): 1.0,
                    (1, '*', (0, 4)): 0.097,
                    (1, '*', (1, 1)): 0.2239,
                    (1, '*', (2, 3)): 0.2612,
                    (1, 'C', ()): 0.4179,
                    (2, 'V', ()): 1.0,
                    (3, 'NP', ()): 1.0,
                    (4, '*', (2,)): 0.7222,    # unary branching for unlicensed V
                    (4, '*', (1, 4)): 0.2778})

def raw(t):
    return ''.join(ch for ch in str(t) if not ch.isupper() 
                                          and ch not in string.punctuation 
                                          and not ch.isnumeric())


def from_tuple(t):
    if not isinstance(t, tuple):
        return Node(t)
    if len(t) > 0:
        return Node(t[0], children=[from_tuple(x) for x in t[1:]])


def clean_labels(root):
    # V and NP need to be direct sisters, in order
    root.set_address('')
    assign_addresses(root)
    addresses = get_address_list(root)
    traces = []
    for a in addresses:
        n = get_node(root, a)
        if n.get_label() in VERB_LABELS:
            n.set_label('V')
            right_sis = get_right_sis(root, a)
            if len(right_sis) == 0 or right_sis[0].label != 'NP':
                n.set_label('C')
        elif n.get_label() == 'NP':
            left_sis = get_left_sis(root, a)
            if len(left_sis) == 0 or left_sis[len(left_sis)-1].label != 'V':
                n.set_label('C')
            else:
                for c in n.children:
                    if '-NONE-ABAR-WH' in c.label:
                        traces.append(c.children[0].label[-1])
                        n.set_label('trace')
        elif n.get_label() not in string.punctuation and 'WHNP' not in n.get_label():
            n.set_label('C')
    for a in addresses:
        n = get_node(root, a)
        if 'WHNP' in n.get_label() and n.get_label()[-1] in traces:
            n.set_label('WH')
        
def drop_punctuation(node): 
    if not node.children:
        return
    node.children = [child for child in node.children if child.label not in string.punctuation]
    for child in node.children:
        drop_punctuation(child)

def drop_traces(node): 
    if not node.children:
        return
    node.children = [child for child in node.children if child.label !='trace']
    for child in node.children:
        drop_traces(child)


def collapse_unary(node):
    if not node.children:
        return node
    if node.label in ['V', 'NP', 'WH', 'trace']:
        node.children = []
    elif len(node.children) == 1:
        return collapse_unary(node.children[0])
    else:
        for i, child in enumerate(node.children):
            node.children[i] = collapse_unary(child)
    return node


def binarize(node):
    if not node.children:
        return node
    left = node.children[0]
    right = node.children[1:]
    if len(node.children) == 1:
        return Node(label=node.label, children=[binarize(left)])
    elif len(node.children) == 2:
        return Node(label=node.label, children=[binarize(left), binarize(right[0])])
    elif len(node.children) > 2:
        # make V and NP children of one new node if they have sisters other than each other
        updated_children = []
        for i, c in enumerate(node.children): 
            if c.get_label() == 'NP' or c.get_label() == 'trace':
                new_node = Node(children=[node.children[i-1], c])
                updated_children.pop()
                updated_children.append(new_node)
            else:
                updated_children.append(c)
        left = updated_children[0]
        right = updated_children[1:]
        if len(updated_children) > 2:
            return Node(label=node.label, children=[binarize(left), binarize(Node(children=right))])
        else:
            return Node(label=node.label, children=[binarize(left), binarize(right[0])])


def timeout_handler(signum, frame):
    raise TimeoutError("Computation timed out.")


def test_binarize():
    tree1 = Node('*')
    tree1.children = [Node('V'), Node('NP'), Node('C')]
    tree1.set_address('')
    assign_addresses(tree1)
    print_tree(tree1)
    print('binarize')
    binary_tree = binarize(tree1)
    binary_tree.set_address('')
    assign_addresses(binary_tree)
    print_tree(binary_tree)

def test_collapse():
    tree1 = Node('*')
    tree1.children = [Node('*')]
    tree1.children[0].children = [Node('V'), Node('NP'), Node('C'), Node('V'), Node('NP')]
    tree1.set_address('')
    assign_addresses(tree1)
    print_tree(tree1)
    print('collapse')
    collapsed = collapse_unary(tree1)
    collapsed.set_address('')
    assign_addresses(collapsed)
    print_tree(collapsed)


def parse(n):
    bank = []
    f = open('CHILDESTreebank/brown-adam.parsed', "r")
    trees = get_trees(f)
    for i, t in enumerate(trees[:n]):
        if 'FRAG' not in str(t) and 'WHNP' in str(t): 
            tuple_tree = from_tuple(t)              # convert from tuple to tree
            clean_labels(tuple_tree)                # rewrite V w/o NP sister as C, only WHs with traces
            drop_punctuation(tuple_tree)            # drop punctuation
            tree = collapse_unary(tuple_tree)       # collapse unary branches (w/ same label) and complex V,NP
            star_nodes(tree)                        # star all inner nodes
            tree = binarize(tree)                   # binarize tree
            drop_traces(tree)                       # drop traces
            tree.set_address('')                    # set addresses
            assign_addresses(tree)
            bank.append(tree)
    return bank


def test_parse(n):
    timeouts = []
    zeros = []
    f = open('CHILDESTreebank/brown-adam.parsed', "r")
    trees = get_trees(f)
    print(len(trees))
    for i, t in enumerate(trees[:n]):
        # if 'FRAG' not in str(t): 
        print(i, t)
        print('-')
        tuple_tree = from_tuple(t)              # convert from tuple to tree
        print(raw(t))
        # print('original tree')                # print original tree
        # tuple_tree.set_address('')
        # assign_addresses(tuple_tree)
        # print_tree(tuple_tree)
        # print('-')

        clean_labels(tuple_tree)                # rewrite V w/o NP sister as C, only WHs with traces
        drop_punctuation(tuple_tree)

        tree = collapse_unary(tuple_tree)      # collapse unary branches (w/ same label) and complex V,NP
    
        

        tree.set_address('')
        assign_addresses(tree)
        star_nodes(tree)                        # star all inner nodes

        print('collapsed tree')
        print_tree(tree)
        print('-')


        print('binarized tree')
        tree = binarize(tree)                   # binarize tree
        drop_traces(tree)
        tree.set_address('')
        assign_addresses(tree)
        print_tree(tree)
        print('-')

        time_limit = 60                         # set the time limit in seconds
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(time_limit)
        try:
            prob = tree_prob_via_over_no_order(p, tree)
            # print(tree_prob_via_under_no_order(p, tree))
        except TimeoutError as e:
            print(e)
            timeouts.append((i,t))
            continue
        else:
            print('over prob:', prob)
        finally:
            signal.alarm(0)

        # assert prob != 0                        # make sure all trees are possible with goal PFSTA
        if prob == 0:
            zeros.append((i))
        print('--\n')

    print('Timed out on: ', len(timeouts), '\n', timeouts)
    print('Zeros on: ', len(zeros), '\n', zeros)

# parse(1000)
# test_binarize()
# test_collapse()
