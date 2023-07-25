import os
from util.constant import AGGS, COND_OPS, OPS


class ASDLConstructor:
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields
        self.sons = {field: [] if field.endswith('*') else None for field in fields}

    def __repr__(self):
        return self.name + '(' + ', '.join(self.fields) + ')'

    @staticmethod
    def get_constructor(name):
        fields = {
            'Complete': ['sqlUnit', 'intersect', 'union', 'except'],
            'Simple': ['select*', 'from', 'where', 'groupBy', 'orderBy'],
            'Conds': ['cond*', 'op*'],
            'Cond': ['valUnit', 'op', 'val1', 'val2'],
            'GroupBy': ['col*', 'having'],
            'OrderBy': ['valUnit*', 'asc', 'limit'],
            'ValUnit': ['agg', 'distinct', 'op', 'col1', 'col2']
        }
        return ASDLConstructor(name, fields[name])


class AbstractSyntaxTree:
    def __init__(self, name):
        self.constructor = ASDLConstructor.get_constructor(name)

    def __repr__(self):
        def indent(s):
            return '\n'.join(['    ' + i for i in s.split('\n')])

        result = str(self.constructor)
        for field in self.constructor.fields:
            if self.constructor.sons[field] is not None:
                result += '\n- ' + field
                if isinstance(self.constructor.sons[field], list):
                    for son in self.constructor.sons[field]:
                        result += '\n' + indent(str(son))
                else:
                    result += '\n' + indent(str(self.constructor.sons[field]))
        return result

    def compare(self, ast, track=[]):
        def edit_cond(t: AbstractSyntaxTree):
            assert t.constructor.name == 'Cond'
            s = edit_val_unit(t.constructor.sons['valUnit']) + ', '
            s += t.constructor.sons['op'] + ', '
            s += t.constructor.sons['val1']
            if t.constructor.sons['val2'] is not None:
                s += ', ' + t.constructor.sons['val2']
            return s

        def edit_val_unit(t: AbstractSyntaxTree):
            assert t.constructor.name == 'ValUnit'
            s = t.constructor.sons['col1']
            if t.constructor.sons['op']:
                s += ' ' + t.constructor.sons['op'] + ' ' + t.constructor.sons['col2']
            if t.constructor.sons['distinct']:
                s = 'DISTINCT ' + s
            if t.constructor.sons['agg']:
                s = t.constructor.sons['agg'] + '(' + s + ')'
            return s

        assert isinstance(ast, AbstractSyntaxTree)
        editions = []
        try:
            assert self.constructor.name == ast.constructor.name
            for field in self.constructor.fields:
                self_son, ast_son = self.constructor.sons[field], ast.constructor.sons[field]
                if self_son is None and ast_son is None:
                    continue
                if self_son is not None and ast_son is None:
                    if field == 'where':
                        for sub_t in self_son.constructor.sons['cond*']:
                            editions.append('AddWhereCondition(' + edit_cond(sub_t) + ')')
                        continue
                    raise ValueError('ADD!')
                if self_son is None and ast_son is not None:
                    raise ValueError('DEL!')
                if isinstance(self_son, list):
                    if len(self_son) > len(ast_son):
                        raise ValueError('ADD!')
                    if len(self_son) < len(ast_son):
                        raise ValueError('DEL!')
                    for i in range(len(self_son)):
                        if type(self_son[i]) != type(ast_son[i]):
                            raise ValueError('CHANGE!')
                        if isinstance(self_son[i], AbstractSyntaxTree):
                            sub_editions = self_son[i].compare(ast_son[i], track + [self.constructor.name + '.' + field])
                            if sub_editions != 'OK':
                                editions += sub_editions
                        elif self_son[i] != ast_son[i]:
                            raise ValueError('CHANGE!')
                elif type(self_son) != type(ast_son):
                    raise ValueError('CHANGE!')
                elif isinstance(self_son, AbstractSyntaxTree):
                    sub_editions = self_son.compare(ast_son, track + [self.constructor.name + '.' + field])
                    if sub_editions != 'OK':
                        editions += sub_editions
                elif self_son != ast_son:
                    if self.constructor.name == 'ValUnit' and 'Simple.select*' in track:
                        editions.append('ChangeSelectItem(' + edit_val_unit(ast) + ', ' + edit_val_unit(self) + ')')
                        break
                    raise ValueError('CHANGE!')
        except Exception as e:
            print(e)
            print()
            print(ast)
            print()
            print(self)
            os._exit(0)
        return editions if editions else 'OK'

    @staticmethod
    def build_sql(sql, db):
        ast = AbstractSyntaxTree('Complete')
        ast.constructor.sons['sqlUnit'] = AbstractSyntaxTree.build_sql_unit(sql, db)
        for set_op in ['intersect', 'union', 'except']:
            if sql[set_op]:
                ast.constructor.sons[set_op] = AbstractSyntaxTree.build_sql(sql[set_op], db)
        return ast

    @staticmethod
    def build_sql_unit(sql_unit, db):
        ast = AbstractSyntaxTree('Simple')
        for select_item in sql_unit['select'][1]:
            val_unit = select_item[1]
            if val_unit[1][0] == 0:
                val_unit[1][0] = select_item[0]
            val_unit[1][2] |= sql_unit['select'][0]
            ast.constructor.sons['select*'].append(AbstractSyntaxTree.build_val_unit(val_unit, db))
        if sql_unit['from']['table_units'][0][0].lower() == 'sql':
            ast.constructor.sons['from'] = AbstractSyntaxTree.build_sql(sql_unit['from']['table_units'][0][1], db)
        if sql_unit['where']:
            ast.constructor.sons['where'] = AbstractSyntaxTree.build_conds(sql_unit['where'], db)
        if sql_unit['groupBy']:
            ast.constructor.sons['groupBy'] = AbstractSyntaxTree.build_group_by(sql_unit['groupBy'], sql_unit['having'], db)
        if sql_unit['orderBy']:
            ast.constructor.sons['orderBy'] = AbstractSyntaxTree.build_order_by(sql_unit['orderBy'], sql_unit['limit'], db)
        return ast

    @staticmethod
    def build_conds(conds, db):
        ast = AbstractSyntaxTree('Conds')
        for cond in conds[0::2]:
            ast.constructor.sons['cond*'].append(AbstractSyntaxTree.build_cond(cond, db))
        for op in conds[1::2]:
            ast.constructor.sons['op*'].append(op.upper())
        return ast

    @staticmethod
    def build_cond(cond, db):
        def get_value(val):
            if isinstance(val, dict):
                return AbstractSyntaxTree.build_sql(val, db)
            if isinstance(val, float) and int(val) == val:
                return int(val)
            return val

        ast = AbstractSyntaxTree('Cond')
        ast.constructor.sons['valUnit'] = AbstractSyntaxTree.build_val_unit(cond[2], db)
        ast.constructor.sons['op'] = ('NOT ' if cond[0] else '') + COND_OPS[cond[1]]
        ast.constructor.sons['val1'] = get_value(cond[3])
        ast.constructor.sons['val2'] = get_value(cond[4])
        return ast

    @staticmethod
    def build_group_by(group_by, having, db):
        ast = AbstractSyntaxTree('GroupBy')
        for col_unit in group_by:
            ast.constructor.sons['col*'].append(AbstractSyntaxTree.get_col_name(col_unit[1], db))
        if having:
            ast.constructor.sons['having'] = AbstractSyntaxTree.build_conds(having, db)
        return ast

    @staticmethod
    def build_order_by(order_by, limit, db):
        ast = AbstractSyntaxTree('OrderBy')
        for val_unit in order_by[1]:
            ast.constructor.sons['valUnit*'].append(AbstractSyntaxTree.build_val_unit(val_unit, db))
        ast.constructor.sons['asc'] = (order_by[0].lower() == 'asc')
        ast.constructor.sons['limit'] = limit
        return ast

    @staticmethod
    def build_val_unit(val_unit, db):
        ast = AbstractSyntaxTree('ValUnit')
        ast.constructor.sons['agg'] = AGGS[val_unit[1][0]]
        ast.constructor.sons['distinct'] = val_unit[1][2]
        ast.constructor.sons['op'] = OPS[val_unit[0]]
        ast.constructor.sons['col1'] = AbstractSyntaxTree.get_col_name(val_unit[1][1], db)
        if val_unit[2]:
            ast.constructor.sons['col2'] = AbstractSyntaxTree.get_col_name(val_unit[2][1], db)
        return ast

    @staticmethod
    def get_col_name(col_id, db):
        if col_id == 0:
            return '*'
        tab_name = db['table_names_original'][db['column_names_original'][col_id][0]]
        col_name = db['column_names_original'][col_id][1]
        return tab_name + '.' + col_name
