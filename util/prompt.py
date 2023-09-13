import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import pickle
import random
import sqlite3
from util.constant import GPT_CHAT_MODELS, GPT_COMPLETION_MODELS, MAX_LENS, SET_OPS


class PromptMaker:
    def __init__(self, args):
        with open(os.path.join('data', args.dataset, 'tables.json'), 'r', encoding='utf-8') as file:
            dbs = json.load(file)
        self.db_prompts = {}
        for db in dbs:
            db_id = db['db_id']
            tabs = db['table_names_original']
            cols = db['column_names_original']
            self.db_prompts[db_id] = ''
            for i in range(len(tabs)):
                if args.api_doc:
                    self.db_prompts[db_id] += f"# {tabs[i]}({', '.join([col[1] for col in cols if col[0] == i])})\n"
                else:
                    self.db_prompts[db_id] += f'create table {tabs[i]} (\n'
                    for j in range(len(cols)):
                        if cols[j][0] == i:
                            self.db_prompts[db_id] += f"    {cols[j][1]} {db['column_types'][j]}"
                            if args.pf == 'eoc':
                                if j in db['primary_keys']:
                                    self.db_prompts[db_id] += ' primary key'
                                for fk in db['foreign_keys']:
                                    if fk[0] == j:
                                        self.db_prompts[db_id] += f' references {tabs[cols[fk[1]][0]]}({cols[fk[1]][1]})'
                            self.db_prompts[db_id] += ',\n'
                    if args.pf == 'eot':
                        pks = [cols[pk][1] for pk in db['primary_keys'] if cols[pk][0] == i]
                        if len(pks) > 0:
                            self.db_prompts[db_id] += f"    primary key ({', '.join(pks)}),\n"
                        for fk in db['foreign_keys']:
                            if cols[fk[0]][0] == i:
                                self.db_prompts[db_id] += f'    foreign key ({cols[fk[0]][1]}) references {tabs[cols[fk[1]][0]]}({cols[fk[1]][1]}),\n'
                    self.db_prompts[db_id] = self.db_prompts[db_id][:-2] + '\n)\n'
                db_path = os.path.join('data', args.dataset, 'database', db_id, db_id + '.sqlite')
                if args.content > 0 and os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = dict_factory
                    cursor = conn.cursor()
                    db_contents = cursor.execute(f'SELECT * FROM {tabs[i]} LIMIT {args.content}').fetchall()
                    self.db_prompts[db_id] += '/*\n'
                    self.db_prompts[db_id] += f"{len(db_contents)} example row{'s' if len(db_contents) > 1 else ''} from table {tabs[i]}:\n"
                    self.db_prompts[db_id] += '\t'.join([col[1] for col in cols if col[0] == i]) + '\n'
                    for record in db_contents:
                        self.db_prompts[db_id] += '\t'.join([str(record[col[1]]) for col in cols if col[0] == i]) + '\n'
                    self.db_prompts[db_id] += '*/\n'
            if args.api_doc and args.pf != 'no':
                self.db_prompts[db_id] += f"# primary keys = [{', '.join([tabs[cols[pk][0]] + '.' + cols[pk][1] for pk in db['primary_keys']])}]\n"
                self.db_prompts[db_id] += f"# foreign keys = [{', '.join([tabs[cols[fk[0]][0]] + '.' + cols[fk[0]][1] + ' = ' + tabs[cols[fk[1]][0]] + '.' + cols[fk[1]][1] for fk in db['foreign_keys']])}]\n"
            self.db_prompts[db_id] = self.db_prompts[db_id][:-1]

    def get_prompt(self, args, db_id=None, interaction=[], shots=[]):
        def convert_editions_to_prompt(editions):
            if editions[0][0] == 'TakeAsNestedFromClause':
                assert len(editions[0]) == 1
                return 'Take the previous SQL as the nested FROM clause for the current SQL.'
            if editions[0][0] == 'OnlyRetainNestedFromClause':
                assert len(editions[0]) == 1
                return 'Retain the nested FROM clause in the previous SQL as the current SQL.'
            if editions[0][0] == 'TakeAsNestedCondition':
                assert len(editions[0]) == 2
                return f'Take the previous SQL as the nested condition for the current SQL. The comparison operator {editions[0][1]} is used.'
            if editions[0][0] == 'OnlyRetainNestedCondition':
                assert len(editions[0]) == 1
                return 'Retain the nested condition in the previous SQL as the current SQL.'

            def linearize(clause):
                if len(clause) == 1:
                    clause.append('no change is needed')
                return '\n- '.join(clause)

            from_clause = ['FROM clause:']
            select_clause = ['SELECT clause:']
            where_clause = ['WHERE clause:']
            group_by_clause = ['GROUP BY clause:']
            order_by_clause = ['ORDER BY clause:']
            limit_clause = ['LIMIT clause:']
            iue_clause = ['INTERSECT/UNION/EXCEPT:']
            for edition in editions:
                if edition[0] == 'EditFromTable':
                    assert len(edition) == 3
                    if edition[1] == '-':
                        from_clause.append('add table ' + edition[2])
                    elif edition[2] == '-':
                        from_clause.append('remove table ' + edition[1])
                    else:
                        from_clause.append(f'change table {edition[1]} to {edition[2]}')
                elif edition[0] == 'EditJoinCondition':
                    assert len(edition) == 3
                    if edition[1] == '-':
                        from_clause.append('add JOIN condition ' + edition[2])
                    elif edition[2] == '-':
                        from_clause.append('remove JOIN condition ' + edition[1])
                    else:
                        from_clause.append(f'change JOIN condition {edition[1]} to {edition[2]}')
                elif edition[0] == 'EditJoinLogicalOperator':
                    assert len(edition) == 2 and edition[1] in ['AND', 'OR']
                    from_clause.append('change JOIN logical operator to ' + edition[1])
                elif edition[0] == 'EditNestedFromClause':
                    assert len(edition) == 2
                    if edition[1] == '-':
                        from_clause.append('remove the nested FROM clause')
                    else:
                        from_clause.append(f'add the SQL ({edition[1]}) as the nested FROM clause')
                elif edition[0] == 'EditSelectItem':
                    assert len(edition) == 3
                    if edition[1] == '-':
                        select_clause.append('add ' + edition[2])
                    elif edition[2] == '-':
                        select_clause.append('remove ' + edition[1])
                    else:
                        select_clause.append(f'change {edition[1]} to {edition[2]}')
                elif edition[0] == 'EditWhereCondition':
                    assert len(edition) == 3
                    if edition[1] == '-':
                        where_clause.append('add WHERE condition ' + edition[2])
                    elif edition[2] == '-':
                        where_clause.append('remove WHERE condition ' + edition[1])
                    else:
                        where_clause.append(f'change WHERE condition {edition[1]} to {edition[2]}')
                elif edition[0] == 'EditWhereLogicalOperator':
                    assert len(edition) == 2 and edition[1] in ['AND', 'OR']
                    where_clause.append('change WHERE logical operator to ' + edition[1])
                elif edition[0] == 'EditGroupByColumn':
                    assert len(edition) == 3
                    if edition[1] == '-':
                        group_by_clause.append('add column ' + edition[2])
                    elif edition[2] == '-':
                        group_by_clause.append('remove column ' + edition[1])
                    else:
                        group_by_clause.append(f'change column {edition[1]} to {edition[2]}')
                elif edition[0] == 'EditHavingCondition':
                    assert len(edition) == 3
                    if edition[1] == '-':
                        group_by_clause.append('add HAVING condition ' + edition[2])
                    elif edition[2] == '-':
                        group_by_clause.append('remove HAVING condition ' + edition[1])
                    else:
                        group_by_clause.append(f'change HAVING condition {edition[1]} to {edition[2]}')
                elif edition[0] == 'EditHavingLogicalOperator':
                    assert len(edition) == 2 and edition[1] in ['AND', 'OR']
                    group_by_clause.append('change HAVING logical operator to ' + edition[1])
                elif edition[0] == 'EditOrderByItem':
                    assert len(edition) == 3
                    if edition[1] == '-':
                        order_by_clause.append('add ' + edition[2])
                    elif edition[2] == '-':
                        order_by_clause.append('remove ' + edition[1])
                    else:
                        order_by_clause.append(f'change {edition[1]} to {edition[2]}')
                elif edition[0] == 'EditOrder':
                    assert len(edition) == 2 and edition[1] in ['ASC', 'DESC']
                    order_by_clause.append('change order to ' + edition[1])
                elif edition[0] == 'EditLimit':
                    assert len(edition) == 3
                    if edition[1] == '-':
                        limit_clause.append('add LIMIT ' + edition[2])
                    elif edition[2] == '-':
                        limit_clause.append('remove LIMIT ' + edition[1])
                    else:
                        limit_clause.append(f'change LIMIT {edition[1]} to {edition[2]}')
                elif edition[0] == 'EditIUE':
                    assert len(edition) == 4 and edition[1] in SET_OPS and edition[2] in ['left', 'right']
                    if edition[3] == '-':
                        iue_clause.append(f'remove the SQL on the {edition[2]} side of the keyword {edition[1].upper()}')
                    else:
                        iue_clause.append(f'{edition[1].upper()}: add the SQL ({edition[3]}) on the {edition[2]} side')
            return '\n'.join([
                linearize(from_clause),
                linearize(select_clause),
                linearize(where_clause),
                linearize(group_by_clause),
                linearize(order_by_clause),
                linearize(limit_clause),
                linearize(iue_clause)
            ])

        if args.gpt in GPT_CHAT_MODELS:
            prompt = [{'role': 'system', 'content': 'Given the database schema, you need to translate the question into the SQL query.'}]
            for i, shot in enumerate(shots):
                for j, turn in enumerate(shot['interaction']):
                    prompt.append({'role': 'user', 'content': ''})
                    if j == 0:
                        prompt[-1]['content'] = 'Database schema:\n' + self.db_prompts[shot['database_id']] + '\n'
                    if args.coe:
                        prompt[-1]['content'] += f"Question {i + 1}-{j + 1}: {turn['utterance']}"
                        prompt.append({'role': 'assistant', 'content': "Let's think step by step.\n"})
                        if 'editions' in turn:
                            prompt[-1]['content'] += f"SQL {i + 1}-{j + 1} can be edited from SQL {i + 1}-{turn['prev_id'] + 1}.\nFollowing edit operations are used:\n"
                            prompt[-1]['content'] += convert_editions_to_prompt(turn['editions']) + '\n'
                        else:
                            prompt[-1]['content'] += f'SQL {i + 1}-{j + 1} can be written directly instead of being edited from previous SQL.\n'
                        prompt[-1]['content'] += f"So SQL {i + 1}-{j + 1} is:\n{turn['query']}"
                    else:
                        prompt[-1]['content'] += 'Question: ' + turn['utterance']
                        prompt.append({'role': 'assistant', 'content': turn['query']})
            if db_id and interaction:
                for j, turn in enumerate(interaction):
                    prompt.append({'role': 'user', 'content': ''})
                    if j == 0:
                        prompt[-1]['content'] = 'Database schema:\n' + self.db_prompts[db_id] + '\n'
                    prompt[-1]['content'] += f"Question{f' {len(shots) + 1}-{j + 1}' if args.coe else ''}: {turn['utterance']}"
                    if j < len(interaction) - 1:
                        prompt.append({'role': 'assistant', 'content': turn['query']})
        elif args.gpt in GPT_COMPLETION_MODELS:
            prompt = ''
            pass
        else:
            raise ValueError(f'unknown GPT model {args.gpt}')
        return prompt

    def is_valid_shots(self, shots, args):
        for shot in shots:
            for turn in shot['interaction']:
                if 'editions' in turn and len(turn['editions']) == 0:
                    return False
        prompt = self.get_prompt(args, shots=shots)
        prompt_len = len(prompt) if isinstance(prompt, str) else sum([len(message['content']) for message in prompt])
        return prompt_len < MAX_LENS[args.gpt]

    def get_shots(self, dataset, args):
        if args.shot_num == 0:
            return []
        while 1:
            shots = set()
            while len(shots) < args.shot_num:
                shots.add(random.randint(0, len(dataset) - 1))
            shots = [dataset[id] for id in shots]
            if self.is_valid_shots(shots, args):
                return shots

    def get_coe_shots(self, dataset, args):
        if args.shot_num == 0:
            return []
        filename = os.path.join(args.log_path, 'shot.bin')
        if os.path.exists(filename):
            with open(filename, 'rb') as file:
                shots = pickle.load(file)
            return shots
        while 1:
            shots = set()
            while len(shots) < args.shot_num:
                shots.add(random.randint(0, len(dataset) - 1))
            shots = [dataset[id] for id in shots]
            if not self.is_valid_shots(shots, args):
                continue
            edit_rules = set()
            for shot in shots:
                edit_rules |= shot['edit_rules']
            if 'EditIUE' in edit_rules and 'TakeAsNestedCondition' in edit_rules:
                break
        with open(filename, 'wb') as file:
            pickle.dump(shots, file)
        return shots


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


if __name__ == '__main__':
    from util.arg import main_args

    def print_prompt(prompt):
        if isinstance(prompt, str):
            print(prompt)
        else:
            for message in prompt:
                print('role:', message['role'])
                print('content:')
                print(message['content'])
                print()

    args = main_args()
    print('log path:', args.log_path)
    prompt_maker = PromptMaker(args)
    db_id = input('db: ')
    interaction = [
        {
            'utterance': 'List all items in Table.',
            'query': 'SELECT * FROM Table'
        },
        {
            'utterance': 'Count all black items in Table.',
            'query': 'SELECT COUNT(*) FROM Table WHERE color = "black"',
            'editions': [('EditSelectItem', '*', 'COUNT(*)'), ('EditWhereCondition', '-', 'Table.color = "black"')],
            'prev_id': 0
        }
    ]
    shots = [{'database_id': db_id, 'interaction': interaction} for _ in range(2)]
    print_prompt(prompt_maker.get_prompt(args, db_id, interaction, shots))
