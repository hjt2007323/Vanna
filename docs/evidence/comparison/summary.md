# G1 Vanna SQLite: baseline vs after

Generated: 20261107T133325Z

| case | category | baseline | after | expectation (baseline / after) |
|---|---|---|---|---|
| V0_normal_select | normal_read | 2 rows ['id', 'name', 'price'] | 2 rows ['id', 'name', 'price'] | PASS / PASS |
| V1_leading_comment_select | query_compat | rows_affected=-1 | 2 rows ['id', 'name'] | FAIL / PASS |
| V2_with_select | query_compat | rows_affected=-1 | 1 rows ['id', 'name'] | FAIL / PASS |
| V3_values | query_compat | rows_affected=-1 | 2 rows ['column1', 'column2'] | FAIL / PASS |
| V4_empty_result_columns | empty_result | 0 rows [] | 0 rows ['id', 'name'] | FAIL / PASS |
| V4b_empty_table | empty_result | 0 rows [] | 0 rows ['id', 'note'] | FAIL / PASS |
| V5_default_insert_commit | default_write | rows_affected=1 | rows_affected=1 | PASS / PASS |
| V5b_default_update_commit | default_write | rows_affected=1 | rows_affected=1 | PASS / PASS |
| V6_insert_returning | returning | error: OperationalError: cannot commit transaction - SQL statements in progress | 1 rows ['id', 'name'] | FAIL / PASS |
| V6b_update_returning | returning | error: OperationalError: cannot commit transaction - SQL statements in progress | 1 rows ['id', 'price'] | FAIL / PASS |
| V6c_returning_zero_rows | returning | rows_affected=0 | 0 rows ['id'] | FAIL / PASS |
| V7a_readonly_insert | read_only | unsupported: TypeError | error: DatabaseError: not authorized | FAIL / PASS |
| V7b_readonly_cte_delete | read_only | unsupported: TypeError | error: DatabaseError: not authorized | FAIL / PASS |
| V7c_readonly_attach | read_only | unsupported: TypeError | error: DatabaseError: not authorized | FAIL / PASS |
| V7d_readonly_pragma_write | read_only | unsupported: TypeError | error: DatabaseError: not authorized | FAIL / PASS |
| V7e_readonly_pragma_read | read_only | unsupported: TypeError | 3 rows ['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'] | FAIL / PASS |
| V7f_readonly_ddl | read_only | unsupported: TypeError | error: DatabaseError: not authorized | FAIL / PASS |
| V7g_readonly_load_extension | read_only | unsupported: TypeError | error: OperationalError: not authorized | FAIL / PASS |
| V7h_readonly_vacuum_into | read_only | unsupported: TypeError | error: DatabaseError: authorization denied | FAIL / PASS |
| V7i_readonly_journal_mode | read_only | unsupported: TypeError | error: DatabaseError: not authorized | FAIL / PASS |
| V7j_readonly_reindex | read_only | unsupported: TypeError | error: DatabaseError: not authorized | FAIL / PASS |
| V8a_space_hash_path_select | path | 2 rows ['id', 'name'] | 2 rows ['id', 'name'] | PASS / PASS |
| V8b_space_hash_path_readonly | path | unsupported: TypeError | 2 rows ['id', 'name'] | FAIL / PASS |
| V8c_readonly_missing_db | path | unsupported: TypeError | error: FileNotFoundError: read-only SQLite database does not exist: C:\Users\Asus\AppData\Local\Temp\g1-reproduce-6_qi9c4s\after\V8c_readonly_missing_db\shop.db (read_only=True never creates a database) | FAIL / PASS |
| V9_error_then_delete | lifecycle | error: OperationalError: no such table: table_that_does_not_exist | error: OperationalError: no such table: table_that_does_not_exist | PASS / PASS |
| V10_empty_sql | compat | error: IndexError: list index out of range | error: ValueError: SQL statement must not be empty | PASS / PASS |
| V11_delete_rows_affected | default_write | rows_affected=1 | rows_affected=1 | PASS / PASS |
| V12_duplicate_column_names | compat | 1 rows ['k'] | 1 rows ['k', 'k'] | FAIL / PASS |
| V13_default_pragma_rows | compat | rows_affected=-1 | 3 rows ['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'] | FAIL / PASS |

baseline: {'cases': 29, 'meets_expectation': 7, 'rows_ok': 13, 'errors': 4, 'unsupported': 12}

after: {'cases': 29, 'meets_expectation': 29, 'rows_ok': 17, 'errors': 12, 'unsupported': 0}

cleanup: {'work_root': 'C:\\Users\\Asus\\AppData\\Local\\Temp\\g1-reproduce-6_qi9c4s', 'files_created': 54, 'removed': True, 'kept_by_request': False, 'remaining_entries': []}
