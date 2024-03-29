import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import editdistance as edt
import json
import pickle
import random
import sqlite3
from nltk import word_tokenize
from util.constant import GPT_CHAT_MODELS, GPT_COMPLETION_MODELS, MAX_LENS, SET_OPS
from util.gpt import get_response


class PromptMaker:
    def __init__(self, args):
        with open(os.path.join('data', args.dataset, 'tables.json'), 'r', encoding='utf-8') as file:
            dbs = json.load(file)
        self.db_prompts = {}
        for db in dbs:
            db_id = db['db_id']
            tabs = db['table_names_original']
            cols = db['column_names_original']
            self.db_prompts[db_id] = {'tabs': tabs, 'cols': cols}
            for i in range(len(tabs)):
                self.db_prompts[db_id][tabs[i]] = {'text': '', 'contents': []}
                if args.api_doc:
                    self.db_prompts[db_id][tabs[i]]['text'] += f"# {tabs[i]}({', '.join([col[1] for col in cols if col[0] == i])})"
                else:
                    self.db_prompts[db_id][tabs[i]]['text'] += f'create table {tabs[i]} (\n'
                    for j in range(len(cols)):
                        if cols[j][0] == i:
                            self.db_prompts[db_id][tabs[i]]['text'] += f"    {cols[j][1]} {db['column_types'][j]}"
                            if args.pf == 'eoc':
                                if j in db['primary_keys']:
                                    self.db_prompts[db_id][tabs[i]]['text'] += ' primary key'
                                for fk in db['foreign_keys']:
                                    if fk[0] == j:
                                        self.db_prompts[db_id][tabs[i]]['text'] += f' references {tabs[cols[fk[1]][0]]}({cols[fk[1]][1]})'
                            self.db_prompts[db_id][tabs[i]]['text'] += ',\n'
                    if args.pf == 'eot':
                        pks = [cols[pk][1] for pk in db['primary_keys'] if cols[pk][0] == i]
                        if len(pks) > 0:
                            self.db_prompts[db_id][tabs[i]]['text'] += f"    primary key ({', '.join(pks)}),\n"
                        for fk in db['foreign_keys']:
                            if cols[fk[0]][0] == i:
                                self.db_prompts[db_id][tabs[i]]['text'] += f'    foreign key ({cols[fk[0]][1]}) references {tabs[cols[fk[1]][0]]}({cols[fk[1]][1]}),\n'
                    self.db_prompts[db_id][tabs[i]]['text'] = self.db_prompts[db_id][tabs[i]]['text'][:-2] + '\n)'
                db_path = os.path.join('data', args.dataset, 'database', db_id, db_id + '.sqlite')
                if args.content > 0 and os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = dict_factory
                    conn.text_factory = lambda x: str(x, 'utf-8', 'ignore')
                    cursor = conn.cursor()
                    self.db_prompts[db_id][tabs[i]]['contents'] = cursor.execute(f'SELECT * FROM {tabs[i]}').fetchall()
                    self.db_prompts[db_id][tabs[i]]['scores'] = [0.] * len(self.db_prompts[db_id][tabs[i]]['contents'])

    def update_db_content_scores(self, db_id, question, turn_num):
        cur_scores = {}
        for tab in self.db_prompts[db_id]['tabs']:
            cur_scores[tab] = []
            for i in range(len(self.db_prompts[db_id][tab]['scores'])):
                cur_scores[tab].append(0.)
                if turn_num > 0:
                    self.db_prompts[db_id][tab]['scores'][i] /= 2
                else:
                    self.db_prompts[db_id][tab]['scores'][i] = 0.
        tokens = word_tokenize(question)
        n_gram = 6
        while n_gram > 0:
            for i in range(len(tokens) - n_gram + 1):
                phrase = ' '.join(tokens[i:i + n_gram])
                for tab in self.db_prompts[db_id]['tabs']:
                    for j, record in enumerate(self.db_prompts[db_id][tab]['contents']):
                        for col in record:
                            cur_scores[tab][j] = max(cur_scores[tab][j], 1 - edt.eval(phrase, record[col]) / (len(phrase) + len(record[col])))
            n_gram -= 1
        for tab in self.db_prompts[db_id]['tabs']:
            for i in range(len(self.db_prompts[db_id][tab]['scores'])):
                self.db_prompts[db_id][tab]['scores'][i] += cur_scores[tab][i]

    def get_db_prompt(self, args, db_id):
        prompt = ''
        tabs = self.db_prompts[db_id]['tabs']
        cols = self.db_prompts[db_id]['cols']
        for i in range(len(tabs)):
            prompt += self.db_prompts[db_id][tabs[i]]['text'] + '\n'
            contents = self.db_prompts[db_id][tabs[i]]['contents']
            c_num = min(args.content, len(contents))
            if c_num > 0:
                scores = sorted(enumerate(self.db_prompts[db_id][tabs[i]]['scores']), key=lambda x: (-x[1], x[0]))
                prompt += '/*\n'
                prompt += f"{c_num} example row{'s' if c_num > 1 else ''} from table {tabs[i]}:\n"
                prompt += '\t'.join([col[1] for col in cols if col[0] == i]) + '\n'
                for item in scores[:c_num]:
                    prompt += '\t'.join([contents[item[0]][col[1]] for col in cols if col[0] == i]) + '\n'
                prompt += '*/\n'
        return prompt.strip()

    def get_prompt(self, args, db_id=None, interaction=[], shots=[]):
        def convert_editions_to_prompt(editions):
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
                else:
                    raise ValueError(f'unknown edit rule {edition[0]}')
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
                    if j == 0 and (i == 0 or shot['database_id'] != shots[i - 1]['database_id']):
                        prompt[-1]['content'] = 'Database schema:\n' + self.get_db_prompt(args, shot['database_id']) + '\n'
                    if args.coe:
                        prompt[-1]['content'] += f"Question {i + 1}-{j + 1}: {turn['utterance']}"
                        prompt.append({'role': 'assistant', 'content': "Let's think step by step.\n\n"})
                        if 'editions' in turn:
                            prompt[-1]['content'] += f"SQL {i + 1}-{j + 1} can be edited from SQL {i + 1}-{turn['prev_id'] + 1}.\n\n"
                            if 'edit_reason' in turn:
                                prompt[-1]['content'] += turn['edit_reason'] + '\n\n'
                            prompt[-1]['content'] += 'Therefore, following edit operations are used:\n\n'
                            prompt[-1]['content'] += convert_editions_to_prompt(turn['editions']) + '\n\n'
                        else:
                            prompt[-1]['content'] += f'SQL {i + 1}-{j + 1} can be written directly instead of being edited from previous SQL.\n\n'
                        prompt[-1]['content'] += f"So SQL {i + 1}-{j + 1} is:\n\n{turn['query']}"
                    else:
                        prompt[-1]['content'] += 'Question: ' + turn['utterance']
                        prompt.append({'role': 'assistant', 'content': turn['query']})
            if db_id and interaction:
                for j, turn in enumerate(interaction):
                    prompt.append({'role': 'user', 'content': ''})
                    if j == 0:
                        prompt[-1]['content'] = 'Database schema:\n' + self.get_db_prompt(args, db_id) + '\n'
                    prompt[-1]['content'] += f"Question{f' {len(shots) + 1}-{j + 1}' if args.coe else ''}: {turn['utterance']}"
                    if j < len(interaction) - 1:
                        prompt.append({'role': 'assistant', 'content': turn['query']})
        elif args.gpt in GPT_COMPLETION_MODELS:
            prompt = ''
            pass
        else:
            raise ValueError(f'unknown GPT model {args.gpt}')
        return prompt

    def get_prompt_edit_reason(self, args, bg_questions, prev_question, cur_question):
        if args.gpt in GPT_CHAT_MODELS:
            prompt = [
                {'role': 'system', 'content': 'You need to state the difference between the previous question and the current question.'},
                {'role': 'user', 'content': ''}
            ]
            for i, q in enumerate(bg_questions):
                prompt[-1]['content'] += f'Background question {i + 1}: {q}\n'
            prompt[-1]['content'] += f'Previous question: {prev_question}\nCurrent question: {cur_question}'
        elif args.gpt in GPT_COMPLETION_MODELS:
            prompt = ''
            pass
        else:
            raise ValueError(f'unknown GPT model {args.gpt}')
        return prompt

    def is_valid_shots(self, shots, args):
        for shot in shots:
            if len(shot['interaction']) == 0:
                return False
            for turn in shot['interaction']:
                if 'editions' in turn and len(turn['editions']) == 0:
                    return False
        prompt = self.get_prompt(args, shots=shots)
        prompt_len = len(prompt) if isinstance(prompt, str) else sum([len(message['content']) for message in prompt])
        return prompt_len < MAX_LENS[args.gpt]

    def get_edit_reasons_for_shots(self, shots, args):
        if not args.coe:
            return shots
        for shot in shots:
            interaction = shot['interaction']
            for i in range(len(interaction)):
                questions, cur_idx = [], i
                while 1:
                    questions.append(interaction[cur_idx]['utterance'])
                    if 'prev_id' not in interaction[cur_idx]:
                        break
                    cur_idx = interaction[cur_idx]['prev_id']
                if len(questions) > 1:
                    prompt = self.get_prompt_edit_reason(args, list(reversed(questions[2:])), questions[1], questions[0])
                    interaction[i]['edit_reason'] = get_response(prompt, args, 1000)
        return shots

    def get_static_shots(self, dataset, args):
        if args.static == 0:
            return []
        filename = os.path.join(args.log_path, 'shot.bin')
        if os.path.exists(filename):
            with open(filename, 'rb') as file:
                shots = pickle.load(file)
            return shots
        all_dbs, valid_dbs = set([example['database_id'] for example in dataset]), []
        for db in all_dbs:
            if sum([int(example['database_id'] == db) for example in dataset]) >= args.shot_per_db:
                valid_dbs.append(db)
        while 1:
            dbs, shots = random.sample(valid_dbs, args.db), []
            for db in dbs:
                shots += random.sample([example for example in dataset if example['database_id'] == db], args.shot_per_db)
            if self.is_valid_shots(shots, args):
                break
        print('Generating edit reasons ...')
        shots = self.get_edit_reasons_for_shots(shots, args)
        with open(filename, 'wb') as file:
            pickle.dump(shots, file)
        return shots


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = str(row[idx])
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
            'edit_reason': 'The current question asks for the number of items with black color.',
            'prev_id': 0
        }
    ]
    shots = [{'database_id': db_id, 'interaction': interaction} for _ in range(2)]
    print_prompt(prompt_maker.get_prompt(args, db_id, interaction, shots))
