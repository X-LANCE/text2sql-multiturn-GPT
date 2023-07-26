import json
import os
from asdl.asdl import AbstractSyntaxTree

with open(os.path.join('data', 'sparc', 'dev.json'), 'r', encoding='utf-8') as file:
    data = json.load(file)
with open(os.path.join('data', 'sparc', 'tables.json'), 'r', encoding='utf-8') as file:
    dbs = {db['db_id']: db for db in json.load(file)}
for i, example in enumerate(data):
    print(i)
    print()
    db = dbs[example['database_id']]
    prev_ast, prev_sql = None, None
    for turn in example['interaction']:
        ast, sql = AbstractSyntaxTree.build_sql(turn['sql'], db), turn['query']
        if prev_ast:
            print(prev_sql)
            print(sql)
            print(ast.compare(prev_ast))
            print()
        prev_ast, prev_sql = ast, sql
