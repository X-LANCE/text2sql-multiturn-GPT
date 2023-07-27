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
                if cur_field == 'intersect':
                    return {'AddIntersect(' + t_new.unparse() + ')'}
                if cur_field == 'union':
                    return {'AddUnion(' + t_new.unparse() + ')'}
                if cur_field == 'except':
                    return {'AddExcept(' + t_new.unparse() + ')'}
                if cur_field == 'select*':
                    return {'AddSelectItem(' + t_new.unparse() + ')'}
                if cur_field == 'from':
                    return {'AddNestedFromClause(' + t_new.unparse() + ')'}
                if cur_field == 'where':
                    result = set()
                    for son in t_new.constructor.sons['cond*']:
                        result.add('AddWhereCondition(' + edit_cond(son) + ')')
                    return result
                if t_new.constructor.name == 'Cond' and 'Simple.where' in track:
                    return {'AddWhereCondition(' + edit_cond(t_new) + ')'}
                if cur_field == 'groupBy':
                    result = set()
                    for son in t_new.constructor.sons['col*']:
                        result.add('AddGroupByColumn(' + son + ')')
                    if t_new.constructor.sons['having']:
                        for son in t_new.constructor.sons['having'].constructor.sons['cond*']:
                            result.add('AddHavingCondition(' + edit_cond(son) + ')')
                    return result
                if cur_field == 'having':
                    result = set()
                    for son in t_new.constructor.sons['cond*']:
                        result.add('AddHavingCondition(' + edit_cond(son) + ')')
                    return result
                if t_new.constructor.name == 'Cond' and 'GroupBy.having' in track:
                    return {'AddHavingCondition(' + edit_cond(t_new) + ')'}
                if cur_field == 'orderBy':
                    return {'AddOrderBy(' + edit_order_by(t_new) + ')'}
                if t_new.constructor.name == 'ValUnit' and 'Simple.orderBy' in track:
                    return {'AddOrderByItem(' + t_new.unparse() + ')'}
                raise ValueError('ADD')
            if t_new is None and isinstance(t_old, AbstractSyntaxTree):
                if cur_field == 'intersect':
                    return {'DeleteIntersect'}
                if cur_field == 'union':
                    return {'DeleteUnion'}
                if cur_field == 'except':
                    return {'DeleteExcept'}
                if t_old.constructor.name == 'ValUnit' and cur_field == 'select*':
                    return {'DeleteSeleteItem(' + t_old.unparse() + ')'}
                if cur_field == 'from':
                    return {'DeleteNestedFromClause'}
                if cur_field == 'where':
                    return {'DeleteWhere'}
                if self.constructor.name == 'Conds' and 'Simple.where' in track:
                    return {'DeleteWhereCondition(' + edit_cond(t_old) + ')'}
                if cur_field == 'groupBy':
                    return {'DeleteGroupBy'}
                if cur_field == 'having':
                    return {'DeleteHaving'}
                if self.constructor.name == 'Conds' and 'GroupBy.having' in track:
                    return {'DeleteHavingCondition(' + edit_cond(t_old) + ')'}
                if cur_field == 'orderBy':
                    return {'DeleteOrderBy'}
                if t_old.constructor.name == 'ValUnit' and 'Simple.orderBy' in track:
                    return {'DeleteOrderByItem(' + t_old.unparse() + ')'}
                raise ValueError('DELETE')
            if isinstance(t_new, AbstractSyntaxTree) and isinstance(t_old, AbstractSyntaxTree):
                result = t_new.compare(t_old, track + [self.constructor.name + '.' + cur_field])
                if 'ChangeValUnit' in result:
                    result.remove('ChangeValUnit')
                    if self.constructor.name == 'Cond':
                        if 'Simple.where' in track:
                            result.add('ChangeWhereCondition(' + edit_cond(ast) + ', ' + edit_cond(self) + ')')
                        elif 'GroupBy.having' in track:
                            result.add('ChangeHavingCondition(' + edit_cond(ast) + ', ' + edit_cond(self) + ')')
                return result
            if t_new != t_old:
                if self.constructor.name == 'ValUnit' and 'Simple.select*' in track:
                    return {'ChangeSelectItem(' + ast.unparse() + ', ' + self.unparse() + ')'}
                if self.constructor.name == 'Cond' and 'Simple.where' in track:
                    return {'ChangeWhereCondition(' + edit_cond(ast) + ', ' + edit_cond(self) + ')'}
                if self.constructor.name == 'ValUnit' and ('Simple.where' in track or 'GroupBy.having' in track):
                    return {'ChangeValUnit'}
                if self.constructor.name == 'Conds' and 'Simple.where' in track:
                    return set() if t_new is None or t_old is None else {'ChangeWhereLogicalOperator(' + t_new + ')'}
                if cur_field == 'col*':
                    if t_old is None:
                        return {'AddGroupByColumn(' + t_new + ')'}
                    if t_new is None:
                        return {'DeleteGroupByColumn(' + t_old + ')'}
                    return {'ChangeGroupByColumn(' + t_old + ', ' + t_new + ')'}
                if self.constructor.name == 'Cond' and 'GroupBy.having' in track:
                    return {'ChangeHavingCondition(' + edit_cond(ast) + ', ' + edit_cond(self) + ')'}
                if self.constructor.name == 'Conds' and 'GroupBy.having' in track:
                    return set() if t_new is None or t_old is None else {'ChangeHavingLogicalOperator(' + t_new + ')'}
                if self.constructor.name == 'ValUnit' and 'Simple.orderBy' in track:
                    return {'ChangeOrderByItem(' + ast.unparse() + ', ' + self.unparse() + ')'}
                if cur_field == 'asc':
                    return {'ChangeOrder(' + ('ASC' if t_new else 'DESC') + ')'}
                if cur_field == 'limit':
                    if t_old is None:
                        return {'AddLimit(' + str(t_new) + ')'}
                    if t_new is None:
                        return {'DeleteLimit'}
                    return {'ChangeLimit(' + str(t_new) + ')'}
                raise ValueError('CHANGE')
            return set()

        def edit_cond(t: AbstractSyntaxTree):
            assert t.constructor.name == 'Cond'
            s = t.constructor.sons['valUnit'].unparse() + ', '
            s += t.constructor.sons['op'] + ', '
            if isinstance(t.constructor.sons['val1'], AbstractSyntaxTree):
                s += t.constructor.sons['val1'].unparse()
            else:
                s += str(t.constructor.sons['val1'])
            if t.constructor.sons['val2'] is not None:
                s += ', ' + str(t.constructor.sons['val2'])
            return s

        def edit_order_by(t: AbstractSyntaxTree):
            assert t.constructor.name == 'OrderBy'
            s = ', '.join([son.unparse() for son in t.constructor.sons['valUnit*']])
            s += ', ' + ('ASC' if t.constructor.sons['asc'] else 'DESC')
            if t.constructor.sons['limit'] is not None:
                s += ', ' + str(t.constructor.sons['limit'])
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

    def unparse(self):
        if self.constructor.name == 'Complete':
            result = self.constructor.sons['sqlUnit'].unparse()
            for set_op in ['intersect', 'union', 'except']:
                if self.constructor.sons[set_op]:
                    result += ' ' + set_op.upper() + ' ' + self.constructor.sons[set_op].unparse()
        elif self.constructor.name == 'Simple':
            result = 'SELECT ' + ', '.join([son.unparse() for son in self.constructor.sons['select*']])
            if self.constructor.sons['from']:
                result += ' FROM (' + self.constructor.sons['from'].unparse() + ')'
            if self.constructor.sons['where']:
                result += ' WHERE ' + self.constructor.sons['where'].unparse()
            if self.constructor.sons['groupBy']:
                result += ' ' + self.constructor.sons['groupBy'].unparse()
            if self.constructor.sons['orderBy']:
                result += ' ' + self.constructor.sons['orderBy'].unparse()
        elif self.constructor.name == 'Conds':
            conds = []
            for son in self.constructor.sons['cond*']:
                conds.append(son.unparse())
            if self.constructor.sons['op']:
                result = (' ' + self.constructor.sons['op'] + ' ').join(conds)
            else:
                assert len(conds) == 1
                result = conds[0]
        elif self.constructor.name == 'Cond':
            result = self.constructor.sons['valUnit'].unparse() + ' ' + self.constructor.sons['op'] + ' '
            if isinstance(self.constructor.sons['val1'], AbstractSyntaxTree):
                result += '(' + self.constructor.sons['val1'].unparse() + ')'
            else:
                result += str(self.constructor.sons['val1'])
            if self.constructor.sons['val2'] is not None:
                result += ' AND ' + str(self.constructor.sons['val2'])
        elif self.constructor.name == 'GroupBy':
            result = 'GROUP BY ' + ', '.join(self.constructor.sons['col*'])
            if self.constructor.sons['having']:
                result += ' HAVING ' + self.constructor.sons['having'].unparse()
        elif self.constructor.name == 'OrderBy':
            result = 'ORDER BY ' + ', '.join([son.unparse() for son in self.constructor.sons['valUnit*']])
            result += ' ' + ('ASC' if self.constructor.sons['asc'] else 'DESC')
            if self.constructor.sons['limit'] is not None:
                result += ' LIMIT ' + str(self.constructor.sons['limit'])
        elif self.constructor.name == 'ValUnit':
            result = self.constructor.sons['col1']
            if self.constructor.sons['op']:
                result += ' ' + self.constructor.sons['op'] + ' ' + self.constructor.sons['col2']
            if self.constructor.sons['distinct']:
                result = 'DISTINCT ' + result
            if self.constructor.sons['agg']:
                result = self.constructor.sons['agg'] + '(' + result + ')'
        else:
            raise ValueError('unknown constructor ' + self.constructor.name)
        return result

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
            ast.constructor.sons['op'] = conds[1].upper()
        return ast

    @staticmethod
    def build_cond(cond, db):
        def get_value(val):
            if isinstance(val, dict):
                return AbstractSyntaxTree.build_sql(val, db)
            if isinstance(val, list):
                assert val[0] == 0 and not val[2]
                return AbstractSyntaxTree.get_col_name(val[1], db)
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
