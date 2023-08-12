import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import random
import sqlite3
from util.constant import GPT_CHAT_MODELS, GPT_COMPLETION_MODELS, MAX_LENS


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
        if args.gpt in GPT_CHAT_MODELS:
            prompt = [{'role': 'system', 'content': 'Given the database schema, you need to translate the question into the SQL query.'}]
            if args.coe:
                prompt[0]['content'] += '\nYou can use following operations to edit SQL:'
                prompt[0]['content'] += '\n1. EditIUE(intersect/union/except, left/right, SQL): Append SQL to the left/right side of the previous SQL with intersect/union/except keyword. Delete the left/right side of the previous SQL with intersect/union/except keyword if SQL is "-".'
                prompt[0]['content'] += '\n2. EditFromTable(oldTable, newTable): Replace oldTable with newTable in the FROM clause. Add newTable into the FROM clause if oldTable is "-". Delete oldTable from the FROM clause if newTable is "-".'
                prompt[0]['content'] += '\n3. EditJoinCondition(oldCondition, newCondition): Replace oldCondition with newCondition in the ON clause. Add newCondition into the ON clause if oldCondition is "-". Delete oldCondition from the ON clause if newCondition is "-".'
                prompt[0]['content'] += '\n4. EditJoinLogicalOperator(and/or): Edit the logical operator in the ON clause.'
                prompt[0]['content'] += '\n5. EditNestedFromClause(SQL): Edit the nested FROM clause with SQL. Delete the nested FROM clause if SQL is "-".'
                prompt[0]['content'] += '\n6. EditSelectItem(oldItem, newItem): Replace oldItem with newItem in the SELECT clause. Add newItem into the SELECT clause if oldItem is "-". Delete oldItem from the SELECT clause if newItem is "-".'
                prompt[0]['content'] += '\n7. EditWhereCondition(oldCondition, newCondition): Replace oldCondition with newCondition in the WHERE clause. Add newCondition into the WHERE clause if oldCondition is "-". Delete oldCondition from the WHERE clause if newCondition is "-".'
                prompt[0]['content'] += '\n8. EditWhereLogicalOperator(and/or): Edit the logical operator in the WHERE clause.'
                prompt[0]['content'] += '\n9. EditGroupByColumn(oldColumn, newColumn): Replace oldColumn with newColumn in the GROUP BY clause. Add newColumn into the GROUP BY clause if oldColumn is "-". Delete oldColumn from the GROUP BY clause if newColumn is "-".'
                prompt[0]['content'] += '\n10. EditHavingCondition(oldCondition, newCondition): Replace oldCondition with newCondition in the HAVING clause. Add newCondition into the HAVING clause if oldCondition is "-". Delete oldCondition from the HAVING clause if newCondition is "-".'
                prompt[0]['content'] += '\n11. EditHavingLogicalOperator(and/or): Edit the logical operator in the HAVING clause.'
                prompt[0]['content'] += '\n12. EditOrderByItem(oldItem, newItem): Replace oldItem with newItem in the ORDER BY clause. Add newItem into the ORDER BY clause if oldItem is "-". Delete oldItem from the ORDER BY clause if newItem is "-".'
                prompt[0]['content'] += '\n13. EditOrder(asc/desc): Edit the order in the ORDER BY clause.'
                prompt[0]['content'] += '\n14. EditLimit(oldLimit, newLimit): Replace oldLimit with newLimit in the LIMIT clause. Add newLimit into the LIMIT clause if oldLimit is "-". Delete oldLimit from the LIMIT clause if newLimit is "-".'
                prompt[0]['content'] += '\n15. TakeAsNestedFromClause: Take the previous SQL as the nested FROM clause for the current SQL.'
                prompt[0]['content'] += '\n16. OnlyRetainNestedFromClause: Retain the nested FROM clause in the previous SQL as the current SQL.'
                prompt[0]['content'] += '\n17. TakeAsNestedCondition: Take the previous SQL as the nested condition for the current SQL.'
                prompt[0]['content'] += '\n18. OnlyRetainNestedCondition: Retain the nested condition in the previous SQL as the current SQL.'
            for i, shot in enumerate(shots):
                for j, turn in enumerate(shot['interaction']):
                    prompt.append({'role': 'user', 'content': ''})
                    if j == 0:
                        prompt[-1]['content'] = 'Database schema:\n' + self.db_prompts[shot['database_id']] + '\n'
                    if args.coe:
                        prompt[-1]['content'] += f"Question {i + 1}-{j + 1}: {turn['utterance']}"
                        prompt.append({'role': 'assistant'})
                        if 'editions' in turn:
                            prompt[-1]['content'] = f"SQL {i + 1}-{j + 1} can be edited from SQL {i + 1}-{turn['prev_id'] + 1}. Following operations are used:\n"
                            prompt[-1]['content'] += '\n'.join(turn['editions']) + '\n'
                        else:
                            prompt[-1]['content'] = f"SQL {i + 1}-{j + 1} can be written directly instead of being edited from previous SQL.\n"
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
        best_shots, max_edit_rule_num, valid_cnt = None, -1, 0
        while valid_cnt < 3:
            shots = set()
            while len(shots) < args.shot_num:
                shots.add(random.randint(0, len(dataset) - 1))
            shots = [dataset[id] for id in shots]
            if not self.is_valid_shots(shots, args):
                continue
            valid_cnt += 1
            edit_rules = set()
            for shot in shots:
                edit_rules |= shot['edit_rules']
            if len(edit_rules) > max_edit_rule_num:
                best_shots, max_edit_rule_num = shots, len(edit_rules)
        return best_shots


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
            'editions': ['EditSelectItem(*, COUNT(*))', 'EditWhereCondition(-, Table.color = "black")'],
            'prev_id': 0
        }
    ]
    shots = [{'database_id': db_id, 'interaction': interaction} for _ in range(2)]
    print_prompt(prompt_maker.get_prompt(args, db_id, interaction, shots))
