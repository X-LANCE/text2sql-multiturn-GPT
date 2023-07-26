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
            'Conds': ['cond*', 'op'],
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
        def edit_ast_node(t_new, t_old, cur_field):
            if t_new is None and t_old is None:
                return set()
            if isinstance(t_new, AbstractSyntaxTree) and t_old is None:
                if cur_field == 'select*':
                    return {'AddSelectItem(' + edit_val_unit(t_new) + ')'}
                if cur_field == 'where':
                    result = set()
                    for t in t_new.constructor.sons['cond*']:
                        result.add('AddWhereCondition(' + edit_cond(t) + ')')
                    return result
                if t_new.constructor.name == 'Cond' and 'Simple.where' in track:
                    return {'AddWhereCondition(' + edit_cond(t_new) + ')'}
                if cur_field == 'groupBy':
                    result = set()
                    for col in t_new.constructor.sons['col*']:
                        result.add('AddGroupByColumn(' + col + ')')
                    if t_new.constructor.sons['having'] is not None:
                        raise ValueError('ADD')
                    return result
                if cur_field == 'orderBy':
                    result = 'AddOrderBy('
                    result += ', '.join([edit_val_unit(t) for t in t_new.constructor.sons['valUnit*']])
                    result += ', ' + ('ASC' if t_new.constructor.sons['asc'] else 'DESC')
                    if t_new.constructor.sons['limit']:
                        result += ', ' + str(t_new.constructor.sons['limit'])
                    result += ')'
                    return {result}
                raise ValueError('ADD')
            if t_new is None and isinstance(t_old, AbstractSyntaxTree):
                raise ValueError('DEL')
            if isinstance(t_new, AbstractSyntaxTree) and isinstance(t_old, AbstractSyntaxTree):
                return t_new.compare(t_old, track + [self.constructor.name + '.' + cur_field])
            if t_new != t_old:
                if self.constructor.name == 'ValUnit' and 'Simple.select*' in track:
                    return {'ChangeSelectItem(' + edit_val_unit(ast) + ', ' + edit_val_unit(self) + ')'}
                if self.constructor.name == 'Cond' and 'Simple.where' in track:
                    return {'ChangeWhereCondition(' + edit_cond(ast) + ', ' + edit_cond(self) + ')'}
                if self.constructor.name == 'Conds' and 'Simple.where' in track:
                    return set() if t_new is None or t_old is None else {'ChangeWhereLogicalOperator(' + t_new + ')'}
                raise ValueError('CHANGE')
            return set()

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
        editions = set()
        try:
            assert self.constructor.name == ast.constructor.name
            for field in self.constructor.fields:
                self_son, ast_son = self.constructor.sons[field], ast.constructor.sons[field]
                if isinstance(self_son, list):
                    for i in range(max(len(self_son), len(ast_son))):
                        if i >= len(self_son):
                            editions.update(edit_ast_node(None, ast_son[i], field))
                        elif i >= len(ast_son):
                            editions.update(edit_ast_node(self_son[i], None, field))
                        else:
                            editions.update(edit_ast_node(self_son[i], ast_son[i], field))
                else:
                    editions.update(edit_ast_node(self_son, ast_son, field))
        except Exception as e:
            print(e)
            os._exit(0)
        return editions

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
        if len(conds) > 1:
            for i in range(3, len(conds), 2):
                assert conds[i] == conds[i - 2]
            ast.constructor.sons['op'] = conds[1].upper()
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
