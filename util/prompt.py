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
            for shot in shots:
                for i, turn in enumerate(shot['interaction']):
                    prompt.append({'role': 'user', 'content': ''})
                    if i == 0:
                        prompt[-1]['content'] = 'Database schema:\n' + self.db_prompts[shot['database_id']] + '\n'
                    prompt[-1]['content'] += 'Question: ' + turn['utterance']
                    prompt.append({'role': 'assistant', 'content': turn['query']})
            if db_id and interaction:
                for i, turn in enumerate(interaction):
                    prompt.append({'role': 'user', 'content': ''})
                    if i == 0:
                        prompt[-1]['content'] = 'Database schema:\n' + self.db_prompts[db_id] + '\n'
                    prompt[-1]['content'] += 'Question: ' + turn['utterance']
                    if i < len(interaction) - 1:
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
        {'utterance': 'List all items in Table.', 'query': 'SELECT * FROM Table'},
        {'utterance': 'List all black items in Table.', 'query': 'SELECT * FROM Table WHERE color = "black"'}
    ]
    shots = [{'database_id': db_id, 'interaction': interaction} for _ in range(2)]
    print_prompt(prompt_maker.get_prompt(args, db_id, interaction, shots))
