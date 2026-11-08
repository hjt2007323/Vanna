# G1 Vanna SQLite: after run

Generated: 20261107T133323Z

counts: {'cases': 29, 'meets_expectation': 29, 'rows_ok': 17, 'errors': 12, 'unsupported': 0}

| case | category | result | expectation |
|---|---|---|---|
| V0_normal_select | normal_read | 2 rows ['id', 'name', 'price'] | PASS |
| V1_leading_comment_select | query_compat | 2 rows ['id', 'name'] | PASS |
| V2_with_select | query_compat | 1 rows ['id', 'name'] | PASS |
| V3_values | query_compat | 2 rows ['column1', 'column2'] | PASS |
| V4_empty_result_columns | empty_result | 0 rows ['id', 'name'] | PASS |
| V4b_empty_table | empty_result | 0 rows ['id', 'note'] | PASS |
| V5_default_insert_commit | default_write | rows_affected=1 | PASS |
| V5b_default_update_commit | default_write | rows_affected=1 | PASS |
| V6_insert_returning | returning | 1 rows ['id', 'name'] | PASS |
| V6b_update_returning | returning | 1 rows ['id', 'price'] | PASS |
| V6c_returning_zero_rows | returning | 0 rows ['id'] | PASS |
| V7a_readonly_insert | read_only | error: DatabaseError: not authorized | PASS |
| V7b_readonly_cte_delete | read_only | error: DatabaseError: not authorized | PASS |
| V7c_readonly_attach | read_only | error: DatabaseError: not authorized | PASS |
| V7d_readonly_pragma_write | read_only | error: DatabaseError: not authorized | PASS |
| V7e_readonly_pragma_read | read_only | 3 rows ['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'] | PASS |
| V7f_readonly_ddl | read_only | error: DatabaseError: not authorized | PASS |
| V7g_readonly_load_extension | read_only | error: OperationalError: not authorized | PASS |
| V7h_readonly_vacuum_into | read_only | error: DatabaseError: authorization denied | PASS |
| V7i_readonly_journal_mode | read_only | error: DatabaseError: not authorized | PASS |
| V7j_readonly_reindex | read_only | error: DatabaseError: not authorized | PASS |
| V8a_space_hash_path_select | path | 2 rows ['id', 'name'] | PASS |
| V8b_space_hash_path_readonly | path | 2 rows ['id', 'name'] | PASS |
| V8c_readonly_missing_db | path | error: FileNotFoundError: read-only SQLite database does not exist: C:\Users\Asus\AppData\Local\Temp\g1-reproduce-8t_chg5j\after\V8c_readonly_missing_db\shop.db (read_only=True never creates a database) | PASS |
| V9_error_then_delete | lifecycle | error: OperationalError: no such table: table_that_does_not_exist | PASS |
| V10_empty_sql | compat | error: ValueError: SQL statement must not be empty | PASS |
| V11_delete_rows_affected | default_write | rows_affected=1 | PASS |
| V12_duplicate_column_names | compat | 1 rows ['k', 'k'] | PASS |
| V13_default_pragma_rows | compat | 3 rows ['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'] | PASS |
