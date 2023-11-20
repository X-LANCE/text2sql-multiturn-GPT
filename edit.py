import json
import os
import pickle
from asdl.asdl import AbstractSyntaxTree
from util.arg import edit_args
from util.constant import EDIT_RULES


def get_editions_weight(editions):
    return sum([len(' '.join(edition).split()) for edition in editions])


args = edit_args()
with open(os.path.join('data', args.dataset, 'train.json'), 'r', encoding='utf-8') as file:
    dataset = json.load(file)
with open(os.path.join('data', args.dataset, 'tables.json'), 'r', encoding='utf-8') as file:
    dbs = {db['db_id']: db for db in json.load(file)}
for example in dataset:
    db, interaction = dbs[example['database_id']], example['interaction']
    example['edit_rules'] = set()
    for i in range(len(interaction)):
        ast = AbstractSyntaxTree.build_sql(interaction[i]['sql'], db)
        for j in range(i):
            editions = ast.compare(AbstractSyntaxTree.build_sql(interaction[j]['sql'], db))
            if len(editions) <= 3 and ('editions' not in interaction[i] or get_editions_weight(editions) <= get_editions_weight(interaction[i]['editions'])):
                interaction[i]['editions'], interaction[i]['prev_id'] = editions, j
        if 'editions' in interaction[i]:
            interaction[i]['editions'] = sorted(list(interaction[i]['editions']), key=lambda x: EDIT_RULES.index(x[0]))
            example['edit_rules'].update([edition[0] for edition in interaction[i]['editions']])
with open(os.path.join('data', args.dataset, 'train.bin'), 'wb') as file:
    pickle.dump(dataset, file)
