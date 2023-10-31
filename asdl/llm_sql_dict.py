import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from asdl.asdl_ast import AbstractSyntaxTree
from eval.process_sql import Schema, get_schema, get_sql
from util.constant import SET_OPS


class LLMSQLDictMaker:
    def __init__(self, args):
        self.dataset = args.dataset
        with open(os.path.join('data', args.dataset, 'tables.json'), 'r', encoding='utf-8') as file:
            self.dbs = {db['db_id']: db for db in json.load(file)}

    def get_llm_sql_dict_from_sql(self, db_id, sql):
        llm_sql_dict = {
            'from': {
                'tables': [],
                'join': None
            },
            'select': [],
            'where': None,
            'group_by': {
                'columns': [],
                'having': None
            },
            'order_by': {
                'columns': [],
                'order': None
            },
            'limit': None,
            'intersect': None,
            'union': None,
            'except': None
        }
        db = self.dbs[db_id]

        def get_llm_conds_dict(conds):
            llm_conds_dict = {
                'conditions': [],
                'logical_operator': None
            }
            for cond in conds[0::2]:
                llm_conds_dict['conditions'].append(AbstractSyntaxTree.build_cond(cond, db).unparse())
            if len(conds) > 1:
                llm_conds_dict['logical_operator'] = conds[1].upper()
            return llm_conds_dict

        for tab_unit in sql['from']['table_units']:
            if tab_unit[0] == 'sql':
                llm_sql_dict['from']['tables'].append(AbstractSyntaxTree.build_sql(tab_unit[1], db).unparse())
            else:
                llm_sql_dict['from']['tables'].append(db['table_names_original'][tab_unit[1]])
        llm_sql_dict['from']['join'] = get_llm_conds_dict(sql['from']['conds'])
        for select_item in sql['select'][1]:
            val_unit = select_item[1]
            if val_unit[1][0] == 0:
                val_unit[1][0] = select_item[0]
            val_unit[1][2] |= sql['select'][0]
            llm_sql_dict['select'].append(AbstractSyntaxTree.build_val_unit(val_unit, db).unparse())
        llm_sql_dict['where'] = get_llm_conds_dict(sql['where'])
        for col_unit in sql['groupBy']:
            llm_sql_dict['group_by']['columns'].append(AbstractSyntaxTree.get_col_name(col_unit[1], db))
        llm_sql_dict['group_by']['having'] = get_llm_conds_dict(sql['having'])
        if sql['orderBy']:
            for val_unit in sql['orderBy'][1]:
                llm_sql_dict['order_by']['columns'].append(AbstractSyntaxTree.build_val_unit(val_unit, db).unparse())
            llm_sql_dict['order_by']['order'] = sql['orderBy'][0].upper()
        llm_sql_dict['limit'] = sql['limit']
        for set_op in SET_OPS:
            if sql[set_op]:
                llm_sql_dict[set_op] = AbstractSyntaxTree.build_sql(sql[set_op], db).unparse()
        return llm_sql_dict

    def get_query_from_llm_sql_dict(self, llm_sql_dict):
        query = 'SELECT ' + ', '.join(llm_sql_dict['select']) + ' FROM '
        if len(llm_sql_dict['from']['tables']) == 1 and llm_sql_dict['from']['tables'][0].lower().startswith('select '):
            query += '(' + llm_sql_dict['from']['tables'][0] + ')'
        else:
            query += ' JOIN '.join(llm_sql_dict['from']['tables'])
            if llm_sql_dict['from']['join']['conditions']:
                query += ' ON ' + (' ' + (llm_sql_dict['from']['join']['logical_operator'] or 'AND') + ' ').join(llm_sql_dict['from']['join']['conditions'])
        if llm_sql_dict['where']['conditions']:
            query += ' WHERE ' + (' ' + (llm_sql_dict['where']['logical_operator'] or 'AND') + ' ').join(llm_sql_dict['where']['conditions'])
        if llm_sql_dict['group_by']['columns']:
            query += ' GROUP BY ' + ', '.join(llm_sql_dict['group_by']['columns'])
            if llm_sql_dict['group_by']['having']['conditions']:
                query += ' HAVING ' + (' ' + (llm_sql_dict['group_by']['having']['logical_operator'] or 'AND') + ' ').join(llm_sql_dict['group_by']['having']['conditions'])
        if llm_sql_dict['order_by']['columns']:
            query += ' ORDER BY ' + ', '.join(llm_sql_dict['order_by']['columns']) + ' ' + (llm_sql_dict['order_by']['order'] or 'ASC')
        if llm_sql_dict['limit'] is not None:
            query += ' LIMIT ' + str(llm_sql_dict['limit'])
        for set_op in SET_OPS:
            if llm_sql_dict[set_op]:
                query += ' ' + set_op.upper() + ' ' + llm_sql_dict[set_op]
        return query

    def get_sql_from_query(self, db_id, query):
        def convert_name_to_id(name: str):
            name = name.lower().strip('_')
            if name == 'all':
                return 0
            tabs = self.dbs[db_id]['table_names_original']
            cols = self.dbs[db_id]['column_names_original']
            if name.find('.') < 0:
                for i, tab in enumerate(tabs):
                    if name == tab.lower():
                        return i
                raise ValueError('unknown table ' + name)
            for i, col in enumerate(cols):
                if name == tabs[col[0]].lower() + '.' + col[1].lower():
                    return i
            raise ValueError('unknown column ' + name)

        def normalize_sql(sql):
            for i in range(len(sql['from']['table_units'])):
                sql['from']['table_units'][i] = list(sql['from']['table_units'][i])
                if sql['from']['table_units'][i][0] == 'sql':
                    sql['from']['table_units'][i][1] = normalize_sql(sql['from']['table_units'][i][1])
                else:
                    sql['from']['table_units'][i][1] = convert_name_to_id(sql['from']['table_units'][i][1])
            sql['from']['conds'] = normalize_conds(sql['from']['conds'])
            sql['select'] = list(sql['select'])
            for i in range(len(sql['select'][1])):
                sql['select'][1][i] = list(sql['select'][1][i])
                sql['select'][1][i][1] = normalize_val_unit(sql['select'][1][i][1])
            sql['where'] = normalize_conds(sql['where'])
            for i in range(len(sql['groupBy'])):
                sql['groupBy'][i] = normalize_col_unit(sql['groupBy'][i])
            sql['having'] = normalize_conds(sql['having'])
            sql['orderBy'] = list(sql['orderBy'])
            if sql['orderBy']:
                for i in range(len(sql['orderBy'][1])):
                    sql['orderBy'][1][i] = normalize_val_unit(sql['orderBy'][1][i])
            for set_op in SET_OPS:
                if sql[set_op]:
                    sql[set_op] = normalize_sql(sql[set_op])
            return sql

        def normalize_conds(conds):
            for i in range(0, len(conds), 2):
                conds[i] = list(conds[i])
                conds[i][2] = normalize_val_unit(conds[i][2])
                for j in [3, 4]:
                    if isinstance(conds[i][j], dict):
                        conds[i][j] = normalize_sql(conds[i][j])
                    elif isinstance(conds[i][j], tuple):
                        conds[i][j] = normalize_col_unit(conds[i][j])
            return conds

        def normalize_val_unit(val_unit):
            val_unit = list(val_unit)
            val_unit[1] = normalize_col_unit(val_unit[1])
            if val_unit[0] > 0:
                val_unit[2] = normalize_col_unit(val_unit[2])
            return val_unit

        def normalize_col_unit(col_unit):
            col_unit = list(col_unit)
            col_unit[1] = convert_name_to_id(col_unit[1])
            return col_unit

        schema = Schema(get_schema(os.path.join('data', self.dataset, 'database', db_id, db_id + '.sqlite')))
        return normalize_sql(get_sql(schema, query))


if __name__ == '__main__':
    from util.arg import main_args

    args = main_args()
    llm_sql_dict_maker = LLMSQLDictMaker(args)
    db_id = input('db: ')
    query = input('sql: ')
    sql = llm_sql_dict_maker.get_sql_from_query(db_id, query)
    llm_sql_dict = llm_sql_dict_maker.get_llm_sql_dict_from_sql(db_id, sql)
    print(json.dumps(llm_sql_dict, ensure_ascii=False, indent=4))
    print(llm_sql_dict_maker.get_query_from_llm_sql_dict(llm_sql_dict))
