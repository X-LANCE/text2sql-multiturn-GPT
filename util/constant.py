GPT_CHAT_MODELS = ['gpt-3.5-turbo', 'gpt-3.5-turbo-16k', 'gpt-4']

GPT_COMPLETION_MODELS = ['code-davinci-002', 'text-davinci-003']

MAX_LENS = {
    'gpt-3.5-turbo': 7000,
    'gpt-3.5-turbo-16k': 35000,
    'gpt-4': 14000,
    'code-davinci-002': 14000,
    'text-davinci-003': 7000
}

AGGS = [None, 'MAX', 'MIN', 'COUNT', 'SUM', 'AVG']

COND_OPS = [None, 'BETWEEN', '=', '>', '<', '>=', '<=', '!=', 'IN', 'LIKE', 'IS']

OPS = [None, '-', '+', '*', '/']

SET_OPS = ['intersect', 'union', 'except']

EDIT_RULES = [
    'EditIUE',
    'EditFromTable',
    'EditJoinCondition',
    'EditJoinLogicalOperator',
    'EditNestedFromClause',
    'EditSelectItem',
    'EditWhereCondition',
    'EditWhereLogicalOperator',
    'EditGroupByColumn',
    'EditHavingCondition',
    'EditHavingLogicalOperator',
    'EditOrderByItem',
    'EditOrder',
    'EditLimit'
]

SQL_DICT_INSTRUCTION = '''Each SQL query can be expressed as a SQL dict. Here are 2 examples.

SQL query 1:
SELECT T1.name, COUNT(*) FROM student as T1 JOIN student_course as T2 JOIN course as T3 ON T1.id = T2.sid AND t2.cid = T3.id WHERE T3.grade < 60 OR T3.grade > 90 GROUP BY T1.name HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC LIMIT 10

SQL dict 1:
sql = {
    "from": {
        "tables": [
            "student",
            "student_course",
            "course"
        ],
        "join": {
            "conditions": [
                "student.id = student_course.sid",
                "student_course.cid = course.id"
            ],
            "logical_operator": "AND"
        }
    },
    "select": [
        "student.name",
        "COUNT(*)"
    ],
    "where": {
        "conditions": [
            "course.grade < 60",
            "course.grade > 90"
        ],
        "logical_operator": "OR"
    },
    "group_by": {
        "columns": [
            "student.name"
        ],
        "having": {
            "conditions": [
                "COUNT(*) > 1"
            ],
            "logical_operator": null
        }
    },
    "order_by": {
        "columns": [
            "COUNT(*)"
        ],
        "order": "DESC"
    },
    "limit": 10,
    "intersect": null,
    "union": null,
    "except": null
}

SQL query 2:
SELECT id FROM course WHERE grade > 80 EXCEPT SELECT id FROM course WHERE grade > 90

SQL dict 2:
sql = {
    "from": {
        "tables": [
            "course"
        ],
        "join": {
            "conditions": [],
            "logical_operator": null
        }
    },
    "select": [
        "course.id"
    ],
    "where": {
        "conditions": [
            "course.grade > 80"
        ],
        "logical_operator": null
    },
    "group_by": {
        "columns": [],
        "having": {
            "conditions": [],
            "logical_operator": null
        }
    },
    "order_by": {
        "columns": [],
        "order": null
    },
    "limit": null,
    "intersect": null,
    "union": null,
    "except": "SELECT id FROM course WHERE grade > 90"
}'''
