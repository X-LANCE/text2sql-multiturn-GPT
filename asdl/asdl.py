import os
from util.constant import AGGS, COND_OPS, OPS, SET_OPS


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
            'Simple': ['select*', 'from', 'where', 'groupBy', 'orderBy', 'limit'],
            'From': ['tab*', 'join'],
            'Conds': ['cond*', 'op'],
            'Cond': ['valUnit', 'op', 'val1', 'val2'],
            'GroupBy': ['col*', 'having'],
            'OrderBy': ['valUnit*', 'asc'],
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
                if cur_field in SET_OPS:
                    return {('EditIUE', cur_field, 'right', t_new.unparse())}
                if cur_field == 'select*':
                    return {('EditSelectItem', '-', t_new.unparse())}
                if cur_field == 'join':
                    result = set()
                    for son in t_new.constructor.sons['cond*']:
                        result.add(('EditJoinCondition', '-', son.unparse()))
                    return result
                if t_new.constructor.name == 'Cond' and 'From.join' in track:
                    return {('EditJoinCondition', '-', t_new.unparse())}
                if cur_field == 'where':
                    result = set()
                    for son in t_new.constructor.sons['cond*']:
                        result.add(('EditWhereCondition', '-', son.unparse()))
                    return result
                if t_new.constructor.name == 'Cond' and 'Simple.where' in track:
                    return {('EditWhereCondition', '-', t_new.unparse())}
                if cur_field == 'groupBy':
                    result = set()
                    for son in t_new.constructor.sons['col*']:
                        result.add(('EditGroupByColumn', '-', son))
                    if t_new.constructor.sons['having']:
                        for son in t_new.constructor.sons['having'].constructor.sons['cond*']:
                            result.add(('EditHavingCondition', '-', son.unparse()))
                    return result
                if cur_field == 'having':
                    result = set()
                    for son in t_new.constructor.sons['cond*']:
                        result.add(('EditHavingCondition', '-', son.unparse()))
                    return result
                if t_new.constructor.name == 'Cond' and 'GroupBy.having' in track:
                    return {('EditHavingCondition', '-', t_new.unparse())}
                if cur_field == 'orderBy':
                    result = set()
                    for son in t_new.constructor.sons['valUnit*']:
                        result.add(('EditOrderByItem', '-', son.unparse()))
                    result.add(('EditOrder', 'ASC' if t_new.constructor.sons['asc'] else 'DESC'))
                    return result
                if t_new.constructor.name == 'ValUnit' and 'Simple.orderBy' in track:
                    return {('EditOrderByItem', '-', t_new.unparse())}
                raise ValueError('ADD')
            if t_new is None and isinstance(t_old, AbstractSyntaxTree):
                if cur_field in SET_OPS:
                    return {('EditIUE', cur_field, 'right', '-')}
                if t_old.constructor.name == 'ValUnit' and cur_field == 'select*':
                    return {('EditSelectItem', t_old.unparse(), '-')}
                if cur_field == 'join':
                    result = set()
                    for son in t_old.constructor.sons['cond*']:
                        result.add(('EditJoinCondition', son.unparse(), '-'))
                    return result
                if self.constructor.name == 'Conds' and 'From.join' in track:
                    return {('EditJoinCondition', t_old.unparse(), '-')}
                if cur_field == 'where':
                    result = set()
                    for son in t_old.constructor.sons['cond*']:
                        result.add(('EditWhereCondition', son.unparse(), '-'))
                    return result
                if self.constructor.name == 'Conds' and 'Simple.where' in track:
                    return {('EditWhereCondition', t_old.unparse(), '-')}
                if cur_field == 'groupBy':
                    result = set()
                    for son in t_old.constructor.sons['col*']:
                        result.add(('EditGroupByColumn', son, '-'))
                    if t_old.constructor.sons['having']:
                        for son in t_old.constructor.sons['having'].constructor.sons['cond*']:
                            result.add(('EditHavingCondition', son.unparse(), '-'))
                    return result
                if cur_field == 'having':
                    result = set()
                    for son in t_old.constructor.sons['cond*']:
                        result.add(('EditHavingCondition', son.unparse(), '-'))
                    return result
                if self.constructor.name == 'Conds' and 'GroupBy.having' in track:
                    return {('EditHavingCondition', t_old.unparse(), '-')}
                if cur_field == 'orderBy':
                    result = set()
                    for son in t_old.constructor.sons['valUnit*']:
                        result.add(('EditOrderByItem', son.unparse(), '-'))
                    return result
                if t_old.constructor.name == 'ValUnit' and 'Simple.orderBy' in track:
                    return {('EditOrderByItem', t_old.unparse(), '-')}
                raise ValueError('DELETE')
            if isinstance(t_new, AbstractSyntaxTree) and isinstance(t_old, AbstractSyntaxTree):
                if t_new.constructor.name == 'Complete' and t_old.constructor.name == 'From':
                    return {('EditNestedFromClause', t_new.unparse())}
                if t_new.constructor.name == 'From' and t_old.constructor.name == 'Complete':
                    return {('EditNestedFromClause', '-')}
                result = t_new.compare(t_old, track + [self.constructor.name + '.' + cur_field])
                if 'EditValUnit' in result:
                    result.remove('EditValUnit')
                    if self.constructor.name == 'Cond':
                        if 'From.join' in track:
                            result.add(('EditJoinCondition', ast.unparse(), self.unparse()))
                        elif 'Simple.where' in track:
                            result.add(('EditWhereCondition', ast.unparse(), self.unparse()))
                        elif 'GroupBy.having' in track:
                            result.add(('EditHavingCondition', ast.unparse(), self.unparse()))
                return result
            if t_new != t_old:
                if self.constructor.name == 'ValUnit' and 'Simple.select*' in track:
                    return {('EditSelectItem', ast.unparse(), self.unparse())}
                if cur_field == 'tab*':
                    return {('EditFromTable', t_old if t_old else '-', t_new if t_new else '-')}
                if self.constructor.name == 'Cond' and 'From.join' in track:
                    return {('EditJoinCondition', ast.unparse(), self.unparse())}
                if self.constructor.name == 'Conds' and 'From.join' in track:
                    return set() if t_new is None or t_old is None else {('EditJoinLogicalOperator', t_new)}
                if self.constructor.name == 'Cond' and 'Simple.where' in track:
                    return {('EditWhereCondition', ast.unparse(), self.unparse())}
                if self.constructor.name == 'Conds' and 'Simple.where' in track:
                    return set() if t_new is None or t_old is None else {('EditWhereLogicalOperator', t_new)}
                if cur_field == 'col*':
                    return {('EditGroupByColumn', t_old if t_old else '-', t_new if t_new else '-')}
                if self.constructor.name == 'Cond' and 'GroupBy.having' in track:
                    return {('EditHavingCondition', ast.unparse(), self.unparse())}
                if self.constructor.name == 'Conds' and 'GroupBy.having' in track:
                    return set() if t_new is None or t_old is None else {('EditHavingLogicalOperator', t_new)}
                if self.constructor.name == 'ValUnit' and ('From.join' in track or 'Simple.where' in track or 'GroupBy.having' in track):
                    return {'EditValUnit'}
                if self.constructor.name == 'ValUnit' and 'Simple.orderBy' in track:
                    return {('EditOrderByItem', ast.unparse(), self.unparse())}
                if cur_field == 'asc':
                    return {('EditOrder', 'ASC' if t_new else 'DESC')}
                if cur_field == 'limit':
                    return {('EditLimit', '-' if t_old is None else str(t_old), '-' if t_new is None else str(t_new))}
                raise ValueError('CHANGE')
            return set()

        assert isinstance(ast, AbstractSyntaxTree)
        assert self.constructor.name == ast.constructor.name
        editions = set()
        try:
            if self.constructor.name == 'Complete':
                for set_op in SET_OPS:
                    if self.constructor.sons[set_op] and len(self.constructor.sons[set_op].compare(ast)) == 0:
                        return {('EditIUE', set_op, 'left', self.constructor.sons['sqlUnit'].unparse())}
                    if ast.constructor.sons[set_op] and len(ast.constructor.sons[set_op].compare(self)) == 0:
                        return {('EditIUE', set_op, 'left', '-')}
                if ' FROM (' + ast.unparse() + ')' in self.unparse():
                    return {('TakeAsNestedFromClause',)}
                if ' FROM (' + self.unparse() + ')' in ast.unparse():
                    return {('OnlyRetainNestedFromClause',)}
                for cond_op in COND_OPS[1:]:
                    if ' ' + cond_op + ' (' + ast.unparse() + ')' in self.unparse():
                        return {('TakeAsNestedCondition', cond_op)}
                    if ' ' + cond_op + ' (' + self.unparse() + ')' in ast.unparse():
                        return {('OnlyRetainNestedCondition',)}
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
        while 1:
            e_list, e_num = list(editions), len(editions)
            for edit_rule in ['EditSelectItem', 'EditFromTable', 'EditJoinCondition', 'EditWhereCondition', 'EditHavingCondition']:
                new_edition = None
                for i in range(len(e_list)):
                    for j in range(len(e_list)):
                        try:
                            old_change_item, new_change_item = e_list[i][1], e_list[i][2]
                            delete_item, add_item = e_list[j][1], e_list[j][2]
                            assert e_list[i][0] == edit_rule and e_list[j][0] == edit_rule
                            assert old_change_item != '-' and new_change_item != '-'
                        except:
                            continue
                        if add_item == old_change_item and delete_item == '-':
                            old_id1, old_id2, new_edition = i, j, (edit_rule, '-', new_change_item)
                            break
                        if delete_item == new_change_item and add_item == '-':
                            old_id1, old_id2, new_edition = i, j, (edit_rule, old_change_item, '-')
                            break
                    if new_edition:
                        break
                if new_edition:
                    e_list.pop(max(old_id1, old_id2))
                    e_list.pop(min(old_id1, old_id2))
                    e_list.append(new_edition)
            editions = set(e_list)
            if len(editions) == e_num:
                break
        return editions

    def unparse(self):
        if self.constructor.name == 'Complete':
            result = self.constructor.sons['sqlUnit'].unparse()
            for set_op in SET_OPS:
                if self.constructor.sons[set_op]:
                    result += ' ' + set_op.upper() + ' ' + self.constructor.sons[set_op].unparse()
        elif self.constructor.name == 'Simple':
            result = 'SELECT ' + ', '.join([son.unparse() for son in self.constructor.sons['select*']])
            if self.constructor.sons['from'].constructor.name == 'From':
                result += ' ' + self.constructor.sons['from'].unparse()
            else:
                result += ' FROM (' + self.constructor.sons['from'].unparse() + ')'
            if self.constructor.sons['where']:
                result += ' WHERE ' + self.constructor.sons['where'].unparse()
            if self.constructor.sons['groupBy']:
                result += ' ' + self.constructor.sons['groupBy'].unparse()
            if self.constructor.sons['orderBy']:
                result += ' ' + self.constructor.sons['orderBy'].unparse()
            if self.constructor.sons['limit'] is not None:
                result += ' LIMIT ' + str(self.constructor.sons['limit'])
        elif self.constructor.name == 'From':
            result = 'FROM ' + ' JOIN '.join(self.constructor.sons['tab*'])
            if self.constructor.sons['join']:
                result += ' ON ' + self.constructor.sons['join'].unparse()
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
        for set_op in SET_OPS:
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
        ast.constructor.sons['select*'].sort(key=lambda x: x.unparse())
        ast.constructor.sons['from'] = AbstractSyntaxTree.build_from(sql_unit['from'], db)
        if sql_unit['where']:
            ast.constructor.sons['where'] = AbstractSyntaxTree.build_conds(sql_unit['where'], db)
        if sql_unit['groupBy']:
            ast.constructor.sons['groupBy'] = AbstractSyntaxTree.build_group_by(sql_unit['groupBy'], sql_unit['having'], db)
        if sql_unit['orderBy']:
            ast.constructor.sons['orderBy'] = AbstractSyntaxTree.build_order_by(sql_unit['orderBy'], db)
        ast.constructor.sons['limit'] = sql_unit['limit']
        return ast

    @staticmethod
    def build_from(from_clause, db):
        if from_clause['table_units'][0][0].lower() == 'sql':
            assert len(from_clause['table_units']) == 1
            return AbstractSyntaxTree.build_sql(from_clause['table_units'][0][1], db)
        ast = AbstractSyntaxTree('From')
        for tab_unit in from_clause['table_units']:
            ast.constructor.sons['tab*'].append(db['table_names_original'][tab_unit[1]])
        ast.constructor.sons['tab*'].sort()
        if from_clause['conds']:
            ast.constructor.sons['join'] = AbstractSyntaxTree.build_conds(from_clause['conds'], db)
        return ast

    @staticmethod
    def build_conds(conds, db):
        ast = AbstractSyntaxTree('Conds')
        for cond in conds[0::2]:
            ast.constructor.sons['cond*'].append(AbstractSyntaxTree.build_cond(cond, db))
        ast.constructor.sons['cond*'].sort(key=lambda x: x.unparse())
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
        if isinstance(cond[3], list) and ast.constructor.sons['op'] == '=' and ast.constructor.sons['valUnit'].unparse() > ast.constructor.sons['val1']:
            assert ast.constructor.sons['valUnit'].constructor.sons['agg'] is None
            assert not ast.constructor.sons['valUnit'].constructor.sons['distinct']
            assert ast.constructor.sons['valUnit'].constructor.sons['op'] is None
            assert ast.constructor.sons['valUnit'].constructor.sons['col2'] is None
            ast.constructor.sons['valUnit'].constructor.sons['col1'], ast.constructor.sons['val1'] = ast.constructor.sons['val1'], ast.constructor.sons['valUnit'].constructor.sons['col1']
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
    def build_order_by(order_by, db):
        ast = AbstractSyntaxTree('OrderBy')
        for val_unit in order_by[1]:
            ast.constructor.sons['valUnit*'].append(AbstractSyntaxTree.build_val_unit(val_unit, db))
        ast.constructor.sons['asc'] = (order_by[0].lower() == 'asc')
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
