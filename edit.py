import json
import os
import pickle
from asdl.asdl import AbstractSyntaxTree
from util.arg import edit_args


def get_editions_weight(editions):
    return sum([len(edition.split()) for edition in editions])


args = edit_args()
with open(os.path.join('data', args.dataset, 'train.json'), 'r', encoding='utf-8') as file:
    dataset = json.load(file)
with open(os.path.join('data', args.dataset, 'tables.json'), 'r', encoding='utf-8') as file:
    dbs = {db['db_id']: db for db in json.load(file)}
for example in dataset:
    db, interaction = dbs[example['database_id']], example['interaction']
    example['edit_rules'] = set()
    for i in range(1, len(interaction)):
        ast, interaction[i]['editions'] = AbstractSyntaxTree.build_sql(interaction[i]['sql'], db), None
        for j in range(i):
            editions = ast.compare(AbstractSyntaxTree.build_sql(interaction[j]['sql'], db))
            if interaction[i]['editions'] is None or get_editions_weight(editions) <= get_editions_weight(interaction[i]['editions']):
                interaction[i]['editions'], interaction[i]['prev_id'] = editions, j
        example['edit_rules'].update([edition if edition.find('(') < 0 else edition[:edition.find('(')] for edition in interaction[i]['editions']])
with open(os.path.join('data', args.dataset, 'train.bin'), 'wb') as file:
    pickle.dump(dataset, file)
